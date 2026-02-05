"""
Dashboard API for JarlPM
Provides command center data: at-risk initiatives, KPIs, recent activity.
"""
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc

from db import get_db
from db.models import Epic, EpicSnapshot, ProductDeliveryContext, ScopePlan
from db.feature_models import Feature
from db.user_story_models import UserStory
from routes.auth import get_current_user_id

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ============================================
# CONSTANTS
# ============================================

DEFAULT_POINTS_PER_DEV_PER_SPRINT = 8


# ============================================
# RESPONSE MODELS
# ============================================

class AtRiskInitiative(BaseModel):
    """Initiative that needs attention"""
    epic_id: str
    title: str
    total_points: int
    two_sprint_capacity: int
    delta: int
    assessment: str  # at_risk or overloaded
    stories_count: int


class FocusInitiative(BaseModel):
    """Initiative for focus list"""
    epic_id: str
    title: str
    must_have_points: int
    total_points: int
    current_stage: str
    updated_at: datetime


class PortfolioKPIs(BaseModel):
    """Portfolio-level metrics"""
    active_initiatives: int
    completed_30d: int
    total_points_in_flight: int
    two_sprint_capacity: int
    capacity_utilization_pct: float  # e.g., 140.0 means 140%


class ActivityEvent(BaseModel):
    """Recent activity event"""
    event_type: str  # created, archived, restored, scope_plan_saved, epic_locked
    epic_id: str
    title: str
    timestamp: datetime
    details: Optional[str] = None


class DashboardResponse(BaseModel):
    """Complete dashboard data"""
    at_risk_initiatives: List[AtRiskInitiative]
    focus_list: List[FocusInitiative]
    kpis: PortfolioKPIs
    recent_activity: List[ActivityEvent]
    has_llm_configured: bool
    has_capacity_configured: bool


# ============================================
# HELPER FUNCTIONS
# ============================================

async def get_delivery_context(user_id: str, session: AsyncSession) -> dict:
    """Get user's delivery context"""
    ctx_q = select(ProductDeliveryContext).where(
        ProductDeliveryContext.user_id == user_id
    )
    ctx_result = await session.execute(ctx_q)
    ctx = ctx_result.scalar_one_or_none()
    
    num_devs = ctx.num_developers if ctx and ctx.num_developers else 0
    points_per_dev = ctx.points_per_dev_per_sprint if ctx and ctx.points_per_dev_per_sprint else DEFAULT_POINTS_PER_DEV_PER_SPRINT
    
    sprint_capacity = num_devs * points_per_dev
    two_sprint_capacity = sprint_capacity * 2
    
    return {
        "num_developers": num_devs,
        "points_per_dev_per_sprint": points_per_dev,
        "sprint_capacity": sprint_capacity,
        "two_sprint_capacity": two_sprint_capacity,
    }


async def get_initiative_points(epic_id: str, session: AsyncSession) -> dict:
    """Get total points and breakdown by priority for an initiative"""
    story_q = (
        select(
            UserStory.story_id,
            UserStory.story_points,
            UserStory.story_priority,
        )
        .join(Feature, UserStory.feature_id == Feature.feature_id)
        .where(Feature.epic_id == epic_id)
    )
    
    result = await session.execute(story_q)
    stories = result.fetchall()
    
    total_points = 0
    must_have = 0
    
    for story in stories:
        points = story.story_points or 0
        total_points += points
        
        if story.story_priority == "must-have":
            must_have += points
    
    return {
        "total_points": total_points,
        "must_have_points": must_have,
        "stories_count": len(stories),
    }


def calculate_assessment(delta: int, sprint_capacity: int) -> str:
    """Calculate delivery assessment"""
    if delta >= 0:
        return "on_track"
    elif abs(delta) <= sprint_capacity * 0.25:
        return "at_risk"
    else:
        return "overloaded"


# ============================================
# ENDPOINTS
# ============================================

@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Get complete dashboard data for the command center view.
    """
    user_id = await get_current_user_id(request, session)
    
    # Get delivery context
    ctx = await get_delivery_context(user_id, session)
    two_sprint_capacity = ctx["two_sprint_capacity"]
    sprint_capacity = ctx["sprint_capacity"]
    has_capacity = ctx["num_developers"] > 0
    
    # Get all active (non-archived) initiatives
    epics_q = select(Epic).where(
        Epic.user_id == user_id,
        Epic.is_archived == False
    ).order_by(Epic.updated_at.desc())
    
    epics_result = await session.execute(epics_q)
    epics = epics_result.scalars().all()
    
    # Build at-risk and focus lists
    at_risk_initiatives = []
    focus_list = []
    total_points_in_flight = 0
    
    for epic in epics:
        points_data = await get_initiative_points(epic.epic_id, session)
        total_points = points_data["total_points"]
        total_points_in_flight += total_points
        
        delta = two_sprint_capacity - total_points if has_capacity else 0
        assessment = calculate_assessment(delta, sprint_capacity) if has_capacity else "on_track"
        
        # Add to at-risk list if needed
        if assessment in ["at_risk", "overloaded"]:
            at_risk_initiatives.append(AtRiskInitiative(
                epic_id=epic.epic_id,
                title=epic.title,
                total_points=total_points,
                two_sprint_capacity=two_sprint_capacity,
                delta=delta,
                assessment=assessment,
                stories_count=points_data["stories_count"]
            ))
        
        # Add to focus list (all non-locked epics)
        if epic.current_stage != "epic_locked":
            focus_list.append(FocusInitiative(
                epic_id=epic.epic_id,
                title=epic.title,
                must_have_points=points_data["must_have_points"],
                total_points=total_points,
                current_stage=epic.current_stage,
                updated_at=epic.updated_at
            ))
    
    # Sort at-risk by delta (worst first)
    at_risk_initiatives.sort(key=lambda x: x.delta)
    
    # Sort focus list by must-have points desc, then updated_at desc (most urgent + most recent first)
    focus_list.sort(key=lambda x: (-x.must_have_points, -x.updated_at.timestamp()))
    focus_list = focus_list[:5]
    
    # Calculate KPIs
    completed_30d_q = select(func.count(Epic.id)).where(
        Epic.user_id == user_id,
        Epic.current_stage == "epic_locked",
        Epic.locked_at >= datetime.now(timezone.utc) - timedelta(days=30)
    )
    completed_result = await session.execute(completed_30d_q)
    completed_30d = completed_result.scalar() or 0
    
    capacity_utilization = (total_points_in_flight / two_sprint_capacity * 100) if two_sprint_capacity > 0 else 0
    
    kpis = PortfolioKPIs(
        active_initiatives=len(epics),
        completed_30d=completed_30d,
        total_points_in_flight=total_points_in_flight,
        two_sprint_capacity=two_sprint_capacity,
        capacity_utilization_pct=round(capacity_utilization, 1)
    )
    
    # Build recent activity (from epics and scope plans)
    recent_activity = []
    
    # Recent epic events (created, archived, locked)
    for epic in epics[:10]:
        # Add creation event
        recent_activity.append(ActivityEvent(
            event_type="created",
            epic_id=epic.epic_id,
            title=epic.title,
            timestamp=epic.created_at,
            details=None
        ))
        
        # Add locked event if applicable
        if epic.current_stage == "epic_locked" and epic.locked_at:
            recent_activity.append(ActivityEvent(
                event_type="epic_locked",
                epic_id=epic.epic_id,
                title=epic.title,
                timestamp=epic.locked_at,
                details=None
            ))
    
    # Recent scope plans
    scope_plans_q = select(ScopePlan).where(
        ScopePlan.user_id == user_id
    ).order_by(ScopePlan.updated_at.desc()).limit(5)
    scope_plans_result = await session.execute(scope_plans_q)
    scope_plans = scope_plans_result.scalars().all()
    
    for plan in scope_plans:
        # Get epic title
        epic_q = select(Epic.title).where(Epic.epic_id == plan.epic_id)
        epic_result = await session.execute(epic_q)
        epic_title = epic_result.scalar() or "Unknown"
        
        recent_activity.append(ActivityEvent(
            event_type="scope_plan_saved",
            epic_id=plan.epic_id,
            title=epic_title,
            timestamp=plan.updated_at,
            details=f"Deferred {plan.deferred_points} pts"
        ))
    
    # Sort by timestamp and limit
    recent_activity.sort(key=lambda x: x.timestamp, reverse=True)
    recent_activity = recent_activity[:10]
    
    # Check if LLM is configured (simplified check)
    from db.models import LLMProviderConfig
    llm_q = select(func.count(LLMProviderConfig.id)).where(
        LLMProviderConfig.user_id == user_id,
        LLMProviderConfig.is_active == True
    )
    llm_result = await session.execute(llm_q)
    has_llm = (llm_result.scalar() or 0) > 0
    
    return DashboardResponse(
        at_risk_initiatives=at_risk_initiatives,
        focus_list=focus_list,
        kpis=kpis,
        recent_activity=recent_activity,
        has_llm_configured=has_llm,
        has_capacity_configured=has_capacity
    )
