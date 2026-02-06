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
    
    # Use user's custom velocity or default
    points_per_dev = ctx.points_per_dev_per_sprint if ctx and ctx.points_per_dev_per_sprint else DEFAULT_POINTS_PER_DEV_PER_SPRINT
    
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
        Epic.is_archived.is_(False)
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
        Epic.is_archived.is_(False)
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


# ============================================
# SCOPE PLAN ENDPOINTS
# ============================================

class ScopePlanCreate(BaseModel):
    """Request to save a scope plan"""
    name: str = "Default Plan"
    deferred_story_ids: List[str] = []
    notes: Optional[str] = None


class ScopePlanResponse(BaseModel):
    """Saved scope plan response"""
    plan_id: str
    epic_id: str
    name: str
    deferred_story_ids: List[str] = []
    total_points: int
    deferred_points: int
    remaining_points: int
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@router.post("/initiative/{epic_id}/scope-plan", response_model=ScopePlanResponse)
async def save_scope_plan(
    request: Request,
    epic_id: str,
    body: ScopePlanCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Save a scope plan for an initiative.
    
    Stores deferred story IDs without modifying the stories themselves.
    This allows reversible planning - PMs can experiment with scope cuts.
    """
    from db.models import ScopePlan, generate_uuid
    
    user_id = await get_current_user_id(request, session)
    
    # Verify epic ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Get current points breakdown
    points_data = await get_initiative_points(epic_id, session)
    total_points = points_data["total_points"]
    
    # Calculate deferred points from selected stories
    deferred_points = sum(
        s["points"] for s in points_data["stories"]
        if s["story_id"] in body.deferred_story_ids
    )
    remaining_points = total_points - deferred_points
    
    # Deactivate any existing active plans for this epic
    existing_q = select(ScopePlan).where(
        ScopePlan.epic_id == epic_id,
        ScopePlan.user_id == user_id,
        ScopePlan.is_active.is_(True)
    )
    existing_result = await session.execute(existing_q)
    existing_plans = existing_result.scalars().all()
    
    for plan in existing_plans:
        plan.is_active = False
    
    # Create new plan
    new_plan = ScopePlan(
        plan_id=generate_uuid("splan_"),
        epic_id=epic_id,
        user_id=user_id,
        name=body.name,
        deferred_story_ids=body.deferred_story_ids,
        total_points=total_points,
        deferred_points=deferred_points,
        remaining_points=remaining_points,
        notes=body.notes,
        is_active=True
    )
    session.add(new_plan)
    await session.commit()
    await session.refresh(new_plan)
    
    return ScopePlanResponse(
        plan_id=new_plan.plan_id,
        epic_id=new_plan.epic_id,
        name=new_plan.name,
        deferred_story_ids=new_plan.deferred_story_ids or [],
        total_points=new_plan.total_points,
        deferred_points=new_plan.deferred_points,
        remaining_points=new_plan.remaining_points,
        notes=new_plan.notes,
        is_active=new_plan.is_active,
        created_at=new_plan.created_at,
        updated_at=new_plan.updated_at
    )


@router.get("/initiative/{epic_id}/scope-plan", response_model=Optional[ScopePlanResponse])
async def get_active_scope_plan(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get the active scope plan for an initiative.
    
    Returns None if no plan exists.
    """
    from db.models import ScopePlan
    
    user_id = await get_current_user_id(request, session)
    
    # Verify epic ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Get active plan
    plan_q = select(ScopePlan).where(
        ScopePlan.epic_id == epic_id,
        ScopePlan.user_id == user_id,
        ScopePlan.is_active.is_(True)
    )
    plan_result = await session.execute(plan_q)
    plan = plan_result.scalar_one_or_none()
    
    if not plan:
        return None
    
    return ScopePlanResponse(
        plan_id=plan.plan_id,
        epic_id=plan.epic_id,
        name=plan.name,
        deferred_story_ids=plan.deferred_story_ids or [],
        total_points=plan.total_points,
        deferred_points=plan.deferred_points,
        remaining_points=plan.remaining_points,
        notes=plan.notes,
        is_active=plan.is_active,
        created_at=plan.created_at,
        updated_at=plan.updated_at
    )


@router.delete("/initiative/{epic_id}/scope-plan")
async def clear_scope_plan(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Clear (deactivate) the active scope plan for an initiative.
    
    This allows returning to the "base plan" (no deferrals).
    """
    from db.models import ScopePlan
    
    user_id = await get_current_user_id(request, session)
    
    # Verify epic ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Deactivate any active plans
    plan_q = select(ScopePlan).where(
        ScopePlan.epic_id == epic_id,
        ScopePlan.user_id == user_id,
        ScopePlan.is_active.is_(True)
    )
    plan_result = await session.execute(plan_q)
    active_plans = plan_result.scalars().all()
    
    for plan in active_plans:
        plan.is_active = False
    
    await session.commit()
    
    return {"message": "Scope plan cleared", "epic_id": epic_id}


# ============================================
# ENHANCED UX FEATURES
# ============================================

def generate_cuts_summary(deferred_stories: List[dict], total_deferred_points: int) -> str:
    """
    Generate a human-readable summary of why these cuts were made.
    Example: "To fit capacity, defer 3 nice-to-haves totaling 8 pts (Search filters, CSV export, Dark mode polish)."
    """
    if not deferred_stories:
        return ""
    
    # Group by priority
    priority_groups = {}
    for story in deferred_stories:
        priority = story.get("priority", "should-have") or "should-have"
        if priority not in priority_groups:
            priority_groups[priority] = []
        priority_groups[priority].append(story)
    
    # Build summary parts
    parts = []
    priority_labels = {
        "nice-to-have": "nice-to-haves",
        "should-have": "should-haves", 
        "must-have": "must-haves"
    }
    
    for priority in ["nice-to-have", "should-have", "must-have"]:
        if priority in priority_groups:
            stories = priority_groups[priority]
            count = len(stories)
            points = sum(s.get("points", 0) for s in stories)
            titles = [s.get("title") or s.get("story_text", "")[:30] for s in stories[:3]]
            
            label = priority_labels.get(priority, priority)
            titles_str = ", ".join(titles)
            if len(stories) > 3:
                titles_str += f", +{len(stories) - 3} more"
            
            parts.append(f"{count} {label} ({points} pts): {titles_str}")
    
    if not parts:
        return ""
    
    return f"To fit capacity, defer {', '.join(parts)}."


def check_mvp_feasibility(must_have_points: int, two_sprint_capacity: int) -> dict:
    """
    Check if must-haves alone fit within capacity.
    Returns feasibility status and recommendation.
    """
    delta = two_sprint_capacity - must_have_points
    
    if delta >= 0:
        return {
            "mvp_feasible": True,
            "must_have_points": must_have_points,
            "capacity": two_sprint_capacity,
            "buffer": delta,
            "message": f"Must-haves ({must_have_points} pts) fit within capacity with {delta} pts buffer."
        }
    else:
        return {
            "mvp_feasible": False,
            "must_have_points": must_have_points,
            "capacity": two_sprint_capacity,
            "over_by": abs(delta),
            "message": f"HARD PROBLEM: Must-haves alone ({must_have_points} pts) exceed capacity by {abs(delta)} pts. Consider reframing scope or extending timeline."
        }


class ScopeDecisionSummary(BaseModel):
    """Shareable scope decision artifact"""
    epic_id: str
    title: str
    generated_at: str
    capacity: int
    total_points: int
    # MVP Analysis
    mvp_analysis: dict
    # Sprint breakdown
    sprint_1_scope: List[dict] = []
    sprint_2_scope: List[dict] = []
    deferred_scope: List[dict] = []
    # Summary stats
    sprint_1_points: int = 0
    sprint_2_points: int = 0
    deferred_points: int = 0
    # Notes
    cuts_summary: str = ""
    notes: Optional[str] = None


@router.get("/initiative/{epic_id}/scope-summary", response_model=ScopeDecisionSummary)
async def get_scope_decision_summary(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate a shareable Scope Decision Summary for an initiative.
    
    This is the artifact PMs can export to PRD or send to the team.
    """
    from db.models import ScopePlan
    
    user_id = await get_current_user_id(request, session)
    
    # Verify epic ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Get delivery context
    ctx = await get_delivery_context(user_id, session)
    sprint_capacity = ctx["sprint_capacity"]
    two_sprint_capacity = ctx["two_sprint_capacity"]
    
    # Get points breakdown
    points_data = await get_initiative_points(epic_id, session)
    total_points = points_data["total_points"]
    stories = points_data["stories"]
    
    # Get active scope plan if exists
    plan_q = select(ScopePlan).where(
        ScopePlan.epic_id == epic_id,
        ScopePlan.user_id == user_id,
        ScopePlan.is_active.is_(True)
    )
    plan_result = await session.execute(plan_q)
    plan = plan_result.scalar_one_or_none()
    
    deferred_ids = set(plan.deferred_story_ids) if plan else set()
    
    # Separate stories into included and deferred
    included_stories = [s for s in stories if s["story_id"] not in deferred_ids]
    deferred_stories = [s for s in stories if s["story_id"] in deferred_ids]
    
    # Sort included stories by priority (must-have first) then points
    priority_order = {"must-have": 0, "should-have": 1, "nice-to-have": 2, None: 1}
    included_stories.sort(key=lambda s: (priority_order.get(s.get("priority"), 1), -(s.get("points") or 0)))
    
    # Split into Sprint 1 and Sprint 2
    sprint_1_scope = []
    sprint_2_scope = []
    sprint_1_points = 0
    sprint_2_points = 0
    
    for story in included_stories:
        story_points = story.get("points") or 0
        if sprint_1_points + story_points <= sprint_capacity:
            sprint_1_scope.append({
                "story_id": story["story_id"],
                "title": story.get("title") or story["story_text"][:50],
                "points": story_points,
                "priority": story.get("priority"),
                "feature": story.get("feature_title")
            })
            sprint_1_points += story_points
        else:
            sprint_2_scope.append({
                "story_id": story["story_id"],
                "title": story.get("title") or story["story_text"][:50],
                "points": story_points,
                "priority": story.get("priority"),
                "feature": story.get("feature_title")
            })
            sprint_2_points += story_points
    
    # Format deferred scope
    deferred_scope = [{
        "story_id": s["story_id"],
        "title": s.get("title") or s["story_text"][:50],
        "points": s.get("points") or 0,
        "priority": s.get("priority"),
        "feature": s.get("feature_title")
    } for s in deferred_stories]
    
    deferred_points = sum(s.get("points") or 0 for s in deferred_stories)
    
    # Generate cuts summary
    cuts_summary = generate_cuts_summary(deferred_stories, deferred_points)
    
    # MVP Analysis
    mvp_analysis = check_mvp_feasibility(points_data["must_have_points"], two_sprint_capacity)
    
    return ScopeDecisionSummary(
        epic_id=epic_id,
        title=epic.title,
        generated_at=datetime.now(timezone.utc).isoformat(),
        capacity=two_sprint_capacity,
        total_points=total_points,
        mvp_analysis=mvp_analysis,
        sprint_1_scope=sprint_1_scope,
        sprint_2_scope=sprint_2_scope,
        deferred_scope=deferred_scope,
        sprint_1_points=sprint_1_points,
        sprint_2_points=sprint_2_points,
        deferred_points=deferred_points,
        cuts_summary=cuts_summary,
        notes=plan.notes if plan else None
    )


# ============================================
# AI-POWERED FEATURES
# ============================================

class ScopeCutRationale(BaseModel):
    """AI-generated rationale for scope cuts"""
    rationale: str
    user_impact_tradeoff: str
    what_to_validate_first: str


class AlternativeCutSet(BaseModel):
    """An alternative way to cut scope"""
    name: str
    description: str
    strategy: str  # 'cut_polish', 'cut_integrations', 'cut_low_adoption'
    stories_to_defer: List[str]  # story_ids
    total_deferred_points: int


class AlternativeCutSetsResponse(BaseModel):
    """Multiple alternative cut options"""
    alternatives: List[AlternativeCutSet]


class RiskReview(BaseModel):
    """AI-generated risk review for the plan"""
    top_delivery_risks: List[str]
    top_assumptions: List[str]
    suggested_spike: Optional[dict] = None  # {title, points, description}


@router.post("/initiative/{epic_id}/ai/cut-rationale", response_model=ScopeCutRationale)
async def generate_cut_rationale(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered rationale for the scope cuts.
    
    Uses user's configured LLM to generate:
    - Rationale for the cuts
    - User impact tradeoff analysis
    - What to validate first
    """
    from services.llm_service import LLMService
    from services.strict_output_service import StrictOutputService
    from services.epic_service import EpicService
    
    user_id = await get_current_user_id(request, session)
    
    # ===== SUBSCRIPTION CHECK =====
    epic_service = EpicService(session)
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required for AI features")
    
    # Verify epic ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Get LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured. Please add your API key in Settings.")
    
    # Get delivery context and points data
    ctx = await get_delivery_context(user_id, session)
    points_data = await get_initiative_points(epic_id, session)
    
    # Get scope plan
    from db.models import ScopePlan
    plan_q = select(ScopePlan).where(
        ScopePlan.epic_id == epic_id,
        ScopePlan.user_id == user_id,
        ScopePlan.is_active.is_(True)
    )
    plan_result = await session.execute(plan_q)
    plan = plan_result.scalar_one_or_none()
    
    deferred_ids = set(plan.deferred_story_ids) if plan else set()
    
    # Build context for AI
    deferred_stories = [s for s in points_data["stories"] if s["story_id"] in deferred_ids]
    included_stories = [s for s in points_data["stories"] if s["story_id"] not in deferred_ids]
    
    must_haves = [s for s in included_stories if s.get("priority") == "must-have"]
    
    # Calculate deferred points
    deferred_points = sum(s.get("points", 0) for s in deferred_stories)
    
    system_prompt = """You are a Senior Product Manager helping communicate scope decisions.

Given the scope cuts made for an initiative, generate a clear rationale that can be shared with stakeholders.

Return ONLY valid JSON (no markdown fences) in this format:
{
  "rationale": "1-2 sentences explaining why these specific items were deferred",
  "user_impact_tradeoff": "1-2 sentences on what users will/won't get and why that's acceptable",
  "what_to_validate_first": "1 sentence on what assumption or risk should be validated first"
}"""

    user_prompt = f"""Initiative: {epic.title}

Capacity: {ctx['two_sprint_capacity']} points (2 sprints)
Total scope: {points_data['total_points']} points

INCLUDED (must-haves that will ship):
{chr(10).join([f"- {s.get('title', s['story_text'][:40])} ({s.get('points', 0)} pts)" for s in must_haves[:5]])}

DEFERRED ({deferred_points} points cut):
{chr(10).join([f"- {s.get('title', s['story_text'][:40])} ({s.get('points', 0)} pts, {s.get('priority', 'should-have')})" for s in deferred_stories])}

Generate the rationale for these cuts."""

    # ===== USE STRICT OUTPUT SERVICE FOR ROBUST PARSING =====
    strict_service = StrictOutputService(session)
    
    # Prepare for streaming - extract config BEFORE releasing session
    config_data = llm_service.prepare_for_streaming(llm_config)
    llm_provider = llm_config.provider
    llm_model = llm_config.model_name
    
    try:
        # Generate response using sessionless streaming
        full_response = ""
        llm = LLMService()  # No session needed
        async for chunk in llm.stream_with_config(config_data, system_prompt, user_prompt):
            full_response += chunk
        
        # Repair callback for StrictOutputService (also sessionless)
        async def repair_callback(repair_prompt: str) -> str:
            repair_response = ""
            repair_llm = LLMService()  # No session
            async for chunk in repair_llm.stream_with_config(config_data, system_prompt, repair_prompt):
                repair_response += chunk
            return repair_response
        
        # Validate and repair with StrictOutputService
        validation_result = await strict_service.validate_and_repair(
            raw_response=full_response,
            schema=ScopeCutRationale,
            repair_callback=repair_callback,
            max_repairs=2,
            original_prompt=user_prompt
        )
        
        # Track model health (needs a fresh session)
        from db import AsyncSessionLocal
        async with AsyncSessionLocal() as track_session:
            track_strict = StrictOutputService(track_session)
            await track_strict.track_call(
                user_id=user_id,
                provider=llm_provider,
                model_name=llm_model,
                success=validation_result.valid,
                repaired=validation_result.repair_attempts > 0
            )
        
        if not validation_result.valid:
            logger.error(f"Failed to parse AI cut-rationale response after repairs: {validation_result.errors}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate valid cut rationale: {', '.join(validation_result.errors)}"
            )
        
        return ScopeCutRationale(**validation_result.data)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Cut rationale generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate cut rationale: {str(e)}")


@router.post("/initiative/{epic_id}/ai/alternative-cuts", response_model=AlternativeCutSetsResponse)
async def generate_alternative_cuts(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered alternative cut strategies.
    
    Offers 2-3 alternatives with different prioritization heuristics:
    - Cut polish (UX refinements, edge cases)
    - Cut integrations (3rd party, advanced features)
    - Cut low adoption risk (features with uncertain usage)
    """
    from services.llm_service import LLMService
    from services.strict_output_service import StrictOutputService
    from services.epic_service import EpicService
    from pydantic import BaseModel as PydanticBaseModel
    from typing import List as TypingList
    import json as json_lib
    
    user_id = await get_current_user_id(request, session)
    
    # ===== SUBSCRIPTION CHECK =====
    epic_service = EpicService(session)
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required for AI features")
    
    # Verify epic ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Get LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured. Please add your API key in Settings.")
    
    # Get context
    ctx = await get_delivery_context(user_id, session)
    points_data = await get_initiative_points(epic_id, session)
    
    delta = ctx["two_sprint_capacity"] - points_data["total_points"]
    points_to_cut = abs(delta) if delta < 0 else 0
    
    if points_to_cut == 0:
        return AlternativeCutSetsResponse(alternatives=[])
    
    # Build story list for AI - this will be used to validate returned IDs
    valid_story_ids = set()
    stories_for_ai = []
    for s in points_data["stories"]:
        valid_story_ids.add(s["story_id"])
        stories_for_ai.append({
            "id": s["story_id"],
            "title": s.get("title") or s["story_text"][:50],
            "points": s.get("points", 0),
            "priority": s.get("priority", "should-have"),
            "feature": s.get("feature_title", "")
        })
    
    # Create internal schema for LLM response parsing
    class AlternativeCutLLM(PydanticBaseModel):
        name: str
        description: str
        strategy: str
        story_ids: TypingList[str]
        total_points: int
    
    class AlternativesLLMResponse(PydanticBaseModel):
        alternatives: TypingList[AlternativeCutLLM]
    
    system_prompt = """You are a Senior Product Manager helping with scope decisions.

Given a list of stories and points to cut, generate 3 alternative cut strategies.

STRATEGIES:
1. "Cut Polish" - Defer UX refinements, edge cases, nice-to-haves
2. "Cut Integrations" - Defer 3rd party integrations, advanced features
3. "Cut Low Adoption" - Defer features with uncertain user adoption

For each strategy, select stories to defer that total AT LEAST the required points to cut.

IMPORTANT: Only use story IDs from the provided list. Do not invent IDs.

Return ONLY valid JSON (no markdown fences):
{
  "alternatives": [
    {
      "name": "Cut Polish",
      "description": "Brief description of what gets deferred",
      "strategy": "cut_polish",
      "story_ids": ["story_id1", "story_id2"],
      "total_points": 15
    },
    ...
  ]
}"""

    user_prompt = f"""Initiative: {epic.title}
Points to cut: {points_to_cut} (to fit {ctx['two_sprint_capacity']} pt capacity)

STORIES (use ONLY these IDs):
{json_lib.dumps(stories_for_ai, indent=2)}

Generate 3 alternative cut strategies, each cutting at least {points_to_cut} points."""

    # ===== USE STRICT OUTPUT SERVICE FOR ROBUST PARSING =====
    strict_service = StrictOutputService(session)
    
    # Prepare for streaming - extract config BEFORE releasing session
    config_data = llm_service.prepare_for_streaming(llm_config)
    llm_provider = llm_config.provider
    llm_model = llm_config.model_name
    
    try:
        # Generate response using sessionless streaming
        full_response = ""
        llm = LLMService()  # No session needed
        async for chunk in llm.stream_with_config(config_data, system_prompt, user_prompt):
            full_response += chunk
        
        # Repair callback for StrictOutputService (also sessionless)
        async def repair_callback(repair_prompt: str) -> str:
            repair_response = ""
            repair_llm = LLMService()  # No session
            async for chunk in repair_llm.stream_with_config(config_data, system_prompt, repair_prompt):
                repair_response += chunk
            return repair_response
        
        # Validate and repair with StrictOutputService
        validation_result = await strict_service.validate_and_repair(
            raw_response=full_response,
            schema=AlternativesLLMResponse,
            repair_callback=repair_callback,
            max_repairs=2,
            original_prompt=user_prompt
        )
        
        # Track model health (needs a fresh session)
        from db import AsyncSessionLocal
        async with AsyncSessionLocal() as track_session:
            track_strict = StrictOutputService(track_session)
            await track_strict.track_call(
                user_id=user_id,
                provider=llm_provider,
                model_name=llm_model,
                success=validation_result.valid,
                repaired=validation_result.repair_attempts > 0
            )
        
        if not validation_result.valid:
            logger.error(f"Failed to parse AI alternative-cuts response after repairs: {validation_result.errors}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate alternative cuts: {', '.join(validation_result.errors)}"
            )
        
        # ===== VALIDATE STORY IDS TO PREVENT HALLUCINATION =====
        alternatives = []
        for alt in validation_result.data.get("alternatives", []):
            # Filter to only valid story IDs
            validated_story_ids = [sid for sid in alt.get("story_ids", []) if sid in valid_story_ids]
            
            # Recalculate total points based on validated IDs
            validated_points = sum(
                s.get("points", 0) for s in points_data["stories"] 
                if s["story_id"] in validated_story_ids
            )
            
            alternatives.append(AlternativeCutSet(
                name=alt.get("name", ""),
                description=alt.get("description", ""),
                strategy=alt.get("strategy", ""),
                stories_to_defer=validated_story_ids,  # Only valid IDs
                total_deferred_points=validated_points  # Recalculated
            ))
        
        return AlternativeCutSetsResponse(alternatives=alternatives)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Alternative cuts generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate alternative cuts: {str(e)}")


@router.post("/initiative/{epic_id}/ai/risk-review", response_model=RiskReview)
async def generate_risk_review(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered risk review for the saved scope plan.
    
    Returns:
    - Top 3 delivery risks
    - Top 3 assumptions to validate
    - Suggested spike story (1-2 pts)
    """
    from services.llm_service import LLMService
    from services.strict_output_service import StrictOutputService
    from services.epic_service import EpicService
    
    user_id = await get_current_user_id(request, session)
    
    # ===== SUBSCRIPTION CHECK =====
    epic_service = EpicService(session)
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required for AI features")
    
    # Verify epic ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Get LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured. Please add your API key in Settings.")
    
    # Get context
    ctx = await get_delivery_context(user_id, session)
    points_data = await get_initiative_points(epic_id, session)
    
    # Get scope plan
    from db.models import ScopePlan
    plan_q = select(ScopePlan).where(
        ScopePlan.epic_id == epic_id,
        ScopePlan.user_id == user_id,
        ScopePlan.is_active.is_(True)
    )
    plan_result = await session.execute(plan_q)
    plan = plan_result.scalar_one_or_none()
    
    deferred_ids = set(plan.deferred_story_ids) if plan else set()
    
    included_stories = [s for s in points_data["stories"] if s["story_id"] not in deferred_ids]
    deferred_stories = [s for s in points_data["stories"] if s["story_id"] in deferred_ids]
    
    system_prompt = """You are a Senior Product Manager reviewing a scope plan for delivery risks.

Given the planned scope and deferred items, identify:
1. Top 3 delivery risks (things that could go wrong)
2. Top 3 assumptions that need validation
3. A suggested spike story to de-risk the plan (1-2 points)

Return ONLY valid JSON (no markdown fences):
{
  "top_delivery_risks": [
    "Risk 1: Brief description",
    "Risk 2: Brief description",
    "Risk 3: Brief description"
  ],
  "top_assumptions": [
    "Assumption 1: Brief description",
    "Assumption 2: Brief description",
    "Assumption 3: Brief description"
  ],
  "suggested_spike": {
    "title": "Spike title",
    "points": 2,
    "description": "What this spike validates"
  }
}"""

    user_prompt = f"""Initiative: {epic.title}

DELIVERY CONTEXT:
- Team: {ctx['num_developers']} developers
- Sprint capacity: {ctx['sprint_capacity']} points
- 2-sprint capacity: {ctx['two_sprint_capacity']} points

PLANNED SCOPE ({sum(s.get('points', 0) for s in included_stories)} points):
{chr(10).join([f"- {s.get('title', s['story_text'][:40])} ({s.get('points', 0)} pts, {s.get('priority', 'should-have')})" for s in included_stories[:10]])}
{f'... and {len(included_stories) - 10} more stories' if len(included_stories) > 10 else ''}

DEFERRED ({sum(s.get('points', 0) for s in deferred_stories)} points):
{chr(10).join([f"- {s.get('title', s['story_text'][:40])} ({s.get('points', 0)} pts)" for s in deferred_stories]) if deferred_stories else 'None'}

Generate the risk review."""

    # ===== USE STRICT OUTPUT SERVICE FOR ROBUST PARSING =====
    strict_service = StrictOutputService(session)
    
    try:
        # Generate response
        full_response = ""
        async for chunk in llm_service.generate_stream(user_id, system_prompt, user_prompt):
            full_response += chunk
        
        # Repair callback for StrictOutputService
        async def repair_callback(repair_prompt: str) -> str:
            repair_response = ""
            async for chunk in llm_service.generate_stream(user_id, system_prompt, repair_prompt):
                repair_response += chunk
            return repair_response
        
        # Validate and repair with StrictOutputService
        validation_result = await strict_service.validate_and_repair(
            raw_response=full_response,
            schema=RiskReview,
            repair_callback=repair_callback,
            max_repairs=2,
            original_prompt=user_prompt
        )
        
        # Track model health
        await strict_service.track_call(
            user_id=user_id,
            provider=llm_config.provider,
            model_name=llm_config.model_name,
            success=validation_result.valid,
            repaired=validation_result.repair_attempts > 0
        )
        
        if not validation_result.valid:
            logger.error(f"Failed to parse AI risk-review response after repairs: {validation_result.errors}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate risk review: {', '.join(validation_result.errors)}"
            )
        
        return RiskReview(**validation_result.data)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Risk review generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate risk review: {str(e)}")

