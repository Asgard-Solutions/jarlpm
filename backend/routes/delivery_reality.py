"""
Delivery Reality Routes for JarlPM
Compute capacity, feasibility, and recommended scope cuts for initiatives.

Turns JarlPM from "initiative CRUD" into a senior-PM assistant.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from db import get_db
from db.models import Epic, ProductDeliveryContext
from db.feature_models import Feature
from db.user_story_models import UserStory
from routes.auth import get_current_user_id

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delivery-reality", tags=["delivery-reality"])


# ============================================
# CONSTANTS & DEFAULTS
# ============================================

DEFAULT_POINTS_PER_DEV_PER_SPRINT = 8
PRIORITY_ORDER = {
    "nice-to-have": 0,
    "should-have": 1,
    "must-have": 2,
    None: 1,  # Default to should-have
}


class DeliveryAssessment(str, Enum):
    """Initiative delivery assessment status"""
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OVERLOADED = "overloaded"


# ============================================
# RESPONSE MODELS
# ============================================

class DeliveryContextSummary(BaseModel):
    """Delivery context configuration"""
    num_developers: int = 0
    num_qa: Optional[int] = 0
    sprint_cycle_length: int = 14
    points_per_dev_per_sprint: int = DEFAULT_POINTS_PER_DEV_PER_SPRINT
    sprint_capacity: int = 0
    two_sprint_capacity: int = 0
    delivery_methodology: Optional[str] = None
    delivery_platform: Optional[str] = None


class StatusBreakdown(BaseModel):
    """Count of initiatives by assessment status"""
    on_track: int = 0
    at_risk: int = 0
    overloaded: int = 0


class DeliverySummaryResponse(BaseModel):
    """Global delivery reality summary"""
    delivery_context: DeliveryContextSummary
    total_points_all_active_initiatives: int = 0
    total_active_initiatives: int = 0
    status_breakdown: StatusBreakdown


class StoryForDeferral(BaseModel):
    """Story recommended for deferral"""
    story_id: str
    title: Optional[str] = None
    story_text: str
    points: int
    priority: Optional[str] = None
    feature_title: Optional[str] = None


class InitiativeDeliveryReality(BaseModel):
    """Per-initiative delivery reality assessment"""
    epic_id: str
    title: str
    total_points: int
    two_sprint_capacity: int
    delta: int
    assessment: str
    recommended_defer: List[StoryForDeferral] = []
    deferred_points: int = 0
    new_total_points: int = 0
    new_delta: int = 0
    # Additional context
    total_stories: int = 0
    must_have_points: int = 0
    should_have_points: int = 0
    nice_to_have_points: int = 0


class InitiativeListItem(BaseModel):
    """Initiative summary for global list view"""
    epic_id: str
    title: str
    total_points: int
    two_sprint_capacity: int
    delta: int
    assessment: str
    stories_count: int = 0


class DeliveryRealityListResponse(BaseModel):
    """List of initiatives with delivery reality"""
    delivery_context: DeliveryContextSummary
    initiatives: List[InitiativeListItem]


# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_assessment(delta: int, sprint_capacity: int) -> str:
    """
    Calculate delivery assessment based on delta.
    
    - on_track: delta >= 0 (under capacity)
    - at_risk: delta < 0 but within 25% of sprint capacity
    - overloaded: significantly over capacity
    """
    if delta >= 0:
        return DeliveryAssessment.ON_TRACK.value
    elif abs(delta) <= sprint_capacity * 0.25:
        return DeliveryAssessment.AT_RISK.value
    else:
        return DeliveryAssessment.OVERLOADED.value


def get_stories_to_defer(
    stories: List[dict],
    points_to_cut: int
) -> tuple[List[dict], int]:
    """
    Select stories to defer to meet capacity.
    
    Algorithm:
    1. Sort by priority ascending (nice-to-have first)
    2. Then by points descending (cut big stories first)
    3. Keep selecting until deferred_points >= points_to_cut
    
    Returns: (stories_to_defer, total_deferred_points)
    """
    if points_to_cut <= 0:
        return [], 0
    
    # Sort: priority ascending, then points descending
    sorted_stories = sorted(
        stories,
        key=lambda s: (
            PRIORITY_ORDER.get(s.get("priority"), 1),
            -(s.get("points") or 0)
        )
    )
    
    deferred = []
    deferred_points = 0
    
    for story in sorted_stories:
        if deferred_points >= points_to_cut:
            break
        
        story_points = story.get("points") or 0
        if story_points > 0:
            deferred.append(story)
            deferred_points += story_points
    
    return deferred, deferred_points


async def get_delivery_context(user_id: str, session: AsyncSession) -> dict:
    """Get user's delivery context or return defaults"""
    ctx_q = select(ProductDeliveryContext).where(
        ProductDeliveryContext.user_id == user_id
    )
    ctx_result = await session.execute(ctx_q)
    ctx = ctx_result.scalar_one_or_none()
    
    num_devs = ctx.num_developers if ctx and ctx.num_developers else 0
    sprint_length = ctx.sprint_cycle_length if ctx and ctx.sprint_cycle_length else 14
    
    # Check for custom points_per_dev_per_sprint (we'll need to add this field)
    # For now, use default
    points_per_dev = DEFAULT_POINTS_PER_DEV_PER_SPRINT
    
    sprint_capacity = num_devs * points_per_dev
    two_sprint_capacity = sprint_capacity * 2
    
    return {
        "num_developers": num_devs,
        "num_qa": ctx.num_qa if ctx else 0,
        "sprint_cycle_length": sprint_length,
        "points_per_dev_per_sprint": points_per_dev,
        "sprint_capacity": sprint_capacity,
        "two_sprint_capacity": two_sprint_capacity,
        "delivery_methodology": ctx.delivery_methodology if ctx else None,
        "delivery_platform": ctx.delivery_platform if ctx else None,
    }


async def get_initiative_points(epic_id: str, session: AsyncSession) -> dict:
    """Get total points and breakdown by priority for an initiative"""
    # Get all stories for this epic's features
    story_q = (
        select(
            UserStory.story_id,
            UserStory.title,
            UserStory.story_text,
            UserStory.story_points,
            UserStory.story_priority,
            UserStory.feature_id,
            Feature.title.label("feature_title")
        )
        .join(Feature, UserStory.feature_id == Feature.feature_id)
        .where(Feature.epic_id == epic_id)
    )
    
    result = await session.execute(story_q)
    stories = result.fetchall()
    
    total_points = 0
    must_have = 0
    should_have = 0
    nice_to_have = 0
    story_list = []
    
    for story in stories:
        points = story.story_points or 0
        total_points += points
        
        priority = story.story_priority
        if priority == "must-have":
            must_have += points
        elif priority == "nice-to-have":
            nice_to_have += points
        else:
            should_have += points
        
        story_list.append({
            "story_id": story.story_id,
            "title": story.title,
            "story_text": story.story_text,
            "points": points,
            "priority": priority,
            "feature_title": story.feature_title,
        })
    
    return {
        "total_points": total_points,
        "must_have_points": must_have,
        "should_have_points": should_have,
        "nice_to_have_points": nice_to_have,
        "stories": story_list,
        "stories_count": len(story_list),
    }


# ============================================
# API ENDPOINTS
# ============================================

@router.get("/summary", response_model=DeliverySummaryResponse)
async def get_delivery_summary(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Get global delivery reality summary.
    
    Returns capacity settings and computed totals across all active initiatives.
    """
    user_id = await get_current_user_id(request, session)
    
    # Get delivery context
    ctx = await get_delivery_context(user_id, session)
    
    # Get all active (non-archived) initiatives
    epics_q = select(Epic).where(
        Epic.user_id == user_id,
        Epic.is_archived == False
    )
    epics_result = await session.execute(epics_q)
    epics = epics_result.scalars().all()
    
    total_points = 0
    status_breakdown = {"on_track": 0, "at_risk": 0, "overloaded": 0}
    
    for epic in epics:
        points_data = await get_initiative_points(epic.epic_id, session)
        epic_points = points_data["total_points"]
        total_points += epic_points
        
        delta = ctx["two_sprint_capacity"] - epic_points
        assessment = calculate_assessment(delta, ctx["sprint_capacity"])
        status_breakdown[assessment] += 1
    
    return DeliverySummaryResponse(
        delivery_context=DeliveryContextSummary(**ctx),
        total_points_all_active_initiatives=total_points,
        total_active_initiatives=len(epics),
        status_breakdown=StatusBreakdown(**status_breakdown)
    )


@router.get("/initiatives", response_model=DeliveryRealityListResponse)
async def list_initiatives_delivery(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    List all active initiatives with their delivery reality assessment.
    
    Returns initiatives sorted by assessment severity (overloaded first).
    """
    user_id = await get_current_user_id(request, session)
    
    # Get delivery context
    ctx = await get_delivery_context(user_id, session)
    
    # Get all active (non-archived) initiatives
    epics_q = select(Epic).where(
        Epic.user_id == user_id,
        Epic.is_archived == False
    ).order_by(Epic.updated_at.desc())
    
    epics_result = await session.execute(epics_q)
    epics = epics_result.scalars().all()
    
    initiatives = []
    for epic in epics:
        points_data = await get_initiative_points(epic.epic_id, session)
        total_points = points_data["total_points"]
        
        delta = ctx["two_sprint_capacity"] - total_points
        assessment = calculate_assessment(delta, ctx["sprint_capacity"])
        
        initiatives.append(InitiativeListItem(
            epic_id=epic.epic_id,
            title=epic.title,
            total_points=total_points,
            two_sprint_capacity=ctx["two_sprint_capacity"],
            delta=delta,
            assessment=assessment,
            stories_count=points_data["stories_count"]
        ))
    
    # Sort by assessment severity (overloaded first, then at_risk, then on_track)
    assessment_order = {
        DeliveryAssessment.OVERLOADED.value: 0,
        DeliveryAssessment.AT_RISK.value: 1,
        DeliveryAssessment.ON_TRACK.value: 2,
    }
    initiatives.sort(key=lambda x: (assessment_order.get(x.assessment, 2), -x.total_points))
    
    return DeliveryRealityListResponse(
        delivery_context=DeliveryContextSummary(**ctx),
        initiatives=initiatives
    )


@router.get("/initiative/{epic_id}", response_model=InitiativeDeliveryReality)
async def get_initiative_delivery_reality(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed delivery reality for a specific initiative.
    
    Includes recommended deferrals if overloaded.
    """
    user_id = await get_current_user_id(request, session)
    
    # Verify ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Get delivery context
    ctx = await get_delivery_context(user_id, session)
    two_sprint_capacity = ctx["two_sprint_capacity"]
    sprint_capacity = ctx["sprint_capacity"]
    
    # Get points breakdown
    points_data = await get_initiative_points(epic_id, session)
    total_points = points_data["total_points"]
    
    delta = two_sprint_capacity - total_points
    assessment = calculate_assessment(delta, sprint_capacity)
    
    # Calculate recommended deferrals if overloaded
    recommended_defer = []
    deferred_points = 0
    new_total_points = total_points
    new_delta = delta
    
    if delta < 0:
        # Need to cut abs(delta) points
        points_to_cut = abs(delta)
        deferred, deferred_pts = get_stories_to_defer(
            points_data["stories"],
            points_to_cut
        )
        
        recommended_defer = [
            StoryForDeferral(
                story_id=s["story_id"],
                title=s["title"],
                story_text=s["story_text"],
                points=s["points"],
                priority=s["priority"],
                feature_title=s["feature_title"]
            )
            for s in deferred
        ]
        deferred_points = deferred_pts
        new_total_points = total_points - deferred_points
        new_delta = two_sprint_capacity - new_total_points
    
    return InitiativeDeliveryReality(
        epic_id=epic.epic_id,
        title=epic.title,
        total_points=total_points,
        two_sprint_capacity=two_sprint_capacity,
        delta=delta,
        assessment=assessment,
        recommended_defer=recommended_defer,
        deferred_points=deferred_points,
        new_total_points=new_total_points,
        new_delta=new_delta,
        total_stories=points_data["stories_count"],
        must_have_points=points_data["must_have_points"],
        should_have_points=points_data["should_have_points"],
        nice_to_have_points=points_data["nice_to_have_points"]
    )
