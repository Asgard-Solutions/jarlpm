"""
Sprint Routes for JarlPM
Handles sprint planning, tracking, and AI-powered sprint insights
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import json as json_lib
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.user_story_models import UserStory
from db.models import Epic, ProductDeliveryContext, SprintInsight
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sprints", tags=["sprints"])


# ============================================
# Request/Response Models
# ============================================

class SprintInfo(BaseModel):
    """Current sprint information"""
    sprint_number: int
    start_date: str
    end_date: str
    days_remaining: int
    progress: int
    cycle_length: int


class SprintCapacity(BaseModel):
    """Sprint capacity information"""
    sprint_capacity: int
    committed_points: int
    delta: int
    is_overloaded: bool


class SprintSummary(BaseModel):
    """Sprint summary with all relevant data"""
    sprint_info: Optional[SprintInfo] = None
    capacity: Optional[SprintCapacity] = None
    stories_by_status: dict
    blocked_stories: List[dict] = []
    total_points: int
    completed_points: int


class UpdateStorySprintRequest(BaseModel):
    """Request to update story sprint assignment"""
    sprint_number: Optional[int] = None


class UpdateStoryStatusRequest(BaseModel):
    """Request to update story status"""
    status: str  # draft, ready, in_progress, done, blocked
    blocked_reason: Optional[str] = None


class SprintKickoffPlan(BaseModel):
    """AI-generated sprint kickoff plan"""
    sprint_goal: str
    top_stories: List[dict]
    sequencing: List[str]
    risks: List[str]


class StandupSummary(BaseModel):
    """AI-generated daily standup summary"""
    what_changed: List[str]
    whats_blocked: List[str]
    what_to_do_next: List[str]
    summary: str


class WipSuggestions(BaseModel):
    """AI-generated WIP optimization suggestions"""
    finish_first: List[dict]
    consider_pausing: List[dict]
    reasoning: str


class SavedInsight(BaseModel):
    """A saved sprint insight"""
    insight_id: str
    insight_type: str
    content: dict
    generated_at: str


class SprintInsightsResponse(BaseModel):
    """Response with all saved insights for a sprint"""
    sprint_number: int
    kickoff_plan: Optional[SavedInsight] = None
    standup_summary: Optional[SavedInsight] = None
    wip_suggestions: Optional[SavedInsight] = None


# ============================================
# Helper Functions
# ============================================

async def get_delivery_context(user_id: str, session: AsyncSession) -> Optional[dict]:
    """Get user's delivery context"""
    result = await session.execute(
        select(ProductDeliveryContext).where(ProductDeliveryContext.user_id == user_id)
    )
    ctx = result.scalar_one_or_none()
    if not ctx:
        return None
    return {
        "num_developers": ctx.num_developers or 0,
        "sprint_cycle_length": ctx.sprint_cycle_length or 14,
        "points_per_dev_per_sprint": ctx.points_per_dev_per_sprint or 8,
        "sprint_start_date": ctx.sprint_start_date,
    }


def calculate_sprint_info(ctx: dict) -> Optional[SprintInfo]:
    """Calculate current sprint information from delivery context"""
    if not ctx or not ctx.get("sprint_start_date") or not ctx.get("sprint_cycle_length"):
        return None
    
    start_date = ctx["sprint_start_date"]
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    
    cycle_length = ctx["sprint_cycle_length"]
    today = datetime.now(timezone.utc)
    
    # Calculate days since start
    days_since_start = (today - start_date).days
    
    # If sprint hasn't started yet, return sprint 1 with future dates
    if days_since_start < 0:
        # Sprint hasn't started - show as Sprint 1 (upcoming)
        current_sprint_num = 1
        current_sprint_start = start_date
        current_sprint_end = start_date + timedelta(days=cycle_length - 1)
        days_remaining = cycle_length + abs(days_since_start)
        progress = 0
    else:
        # Calculate current sprint number (1-based)
        current_sprint_num = (days_since_start // cycle_length) + 1
        
        # Calculate current sprint dates
        current_sprint_start = start_date + timedelta(days=(current_sprint_num - 1) * cycle_length)
        current_sprint_end = current_sprint_start + timedelta(days=cycle_length - 1)
        
        # Days remaining
        days_remaining = (current_sprint_end - today).days
        progress = min(100, max(0, round(((cycle_length - days_remaining) / cycle_length) * 100)))
    
    return SprintInfo(
        sprint_number=current_sprint_num,
        start_date=current_sprint_start.isoformat(),
        end_date=current_sprint_end.isoformat(),
        days_remaining=max(0, days_remaining),
        progress=progress,
        cycle_length=cycle_length
    )


# ============================================
# Core Sprint Endpoints
# ============================================

@router.get("/current", response_model=SprintSummary)
async def get_current_sprint(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get current sprint summary with all relevant data"""
    user_id = await get_current_user_id(request, session)
    
    # Get delivery context
    ctx = await get_delivery_context(user_id, session)
    sprint_info = calculate_sprint_info(ctx) if ctx else None
    
    # Get all stories for the user (from their epics)
    epics_result = await session.execute(
        select(Epic.epic_id).where(Epic.user_id == user_id, Epic.is_archived.is_(False))
    )
    epic_ids = [e[0] for e in epics_result.fetchall()]
    
    # Get stories from features of these epics
    from db.feature_models import Feature
    features_result = await session.execute(
        select(Feature.feature_id).where(Feature.epic_id.in_(epic_ids))
    )
    feature_ids = [f[0] for f in features_result.fetchall()]
    
    stories_result = await session.execute(
        select(UserStory).where(
            (UserStory.feature_id.in_(feature_ids)) | 
            ((UserStory.user_id == user_id) & (UserStory.is_standalone.is_(True)))
        )
    )
    stories = stories_result.scalars().all()
    
    # Get current sprint number
    current_sprint = sprint_info.sprint_number if sprint_info else None
    
    # Filter to current sprint stories if sprint is configured
    if current_sprint:
        sprint_stories = [s for s in stories if s.sprint_number == current_sprint]
    else:
        sprint_stories = stories
    
    # Group by status
    stories_by_status = {
        "backlog": [],
        "ready": [],
        "in_progress": [],
        "done": [],
        "blocked": []
    }
    
    blocked_stories = []
    
    for story in sprint_stories:
        status = story.status or "backlog"
        story_data = {
            "story_id": story.story_id,
            "title": story.title or story.story_text[:50],
            "story_points": story.story_points,
            "priority": story.priority,
            "feature_id": story.feature_id,
            "sprint_number": story.sprint_number,
            "status": status,
            "blocked_reason": story.blocked_reason,
        }
        
        if status in stories_by_status:
            stories_by_status[status].append(story_data)
        else:
            stories_by_status["backlog"].append(story_data)
        
        if status == "blocked":
            blocked_stories.append(story_data)
    
    # Calculate capacity
    capacity = None
    if ctx and ctx.get("num_developers") and sprint_info:
        sprint_capacity = ctx["num_developers"] * ctx["points_per_dev_per_sprint"]
        committed_points = sum(s.story_points or 0 for s in sprint_stories)
        delta = sprint_capacity - committed_points
        capacity = SprintCapacity(
            sprint_capacity=sprint_capacity,
            committed_points=committed_points,
            delta=delta,
            is_overloaded=delta < 0
        )
    
    total_points = sum(s.story_points or 0 for s in sprint_stories)
    completed_points = sum(
        s.story_points or 0 for s in sprint_stories 
        if s.status == "done"
    )
    
    return SprintSummary(
        sprint_info=sprint_info,
        capacity=capacity,
        stories_by_status=stories_by_status,
        blocked_stories=blocked_stories,
        total_points=total_points,
        completed_points=completed_points
    )


@router.put("/story/{story_id}/sprint")
async def update_story_sprint(
    request: Request,
    story_id: str,
    body: UpdateStorySprintRequest,
    session: AsyncSession = Depends(get_db)
):
    """Assign or unassign a story to a sprint"""
    from db.feature_models import Feature
    
    user_id = await get_current_user_id(request, session)
    
    # Get the story
    result = await session.execute(
        select(UserStory).where(UserStory.story_id == story_id)
    )
    story = result.scalar_one_or_none()
    
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    
    # ===== OWNERSHIP CHECK =====
    # For standalone stories, check user_id directly
    if story.is_standalone:
        if story.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this story")
    else:
        # For feature-based stories, verify ownership via feature→epic→user_id
        feature_result = await session.execute(
            select(Feature).where(Feature.feature_id == story.feature_id)
        )
        feature = feature_result.scalar_one_or_none()
        if not feature:
            raise HTTPException(status_code=404, detail="Story's feature not found")
        
        epic_result = await session.execute(
            select(Epic).where(Epic.epic_id == feature.epic_id, Epic.user_id == user_id)
        )
        epic = epic_result.scalar_one_or_none()
        if not epic:
            raise HTTPException(status_code=403, detail="Not authorized to modify this story")
    
    # Update sprint number
    story.sprint_number = body.sprint_number
    await session.commit()
    
    return {
        "story_id": story_id,
        "sprint_number": body.sprint_number,
        "message": f"Story {'assigned to Sprint ' + str(body.sprint_number) if body.sprint_number else 'removed from sprint'}"
    }


@router.put("/story/{story_id}/status")
async def update_story_status(
    request: Request,
    story_id: str,
    body: UpdateStoryStatusRequest,
    session: AsyncSession = Depends(get_db)
):
    """Update story status (including blocked with reason)"""
    from db.feature_models import Feature
    
    user_id = await get_current_user_id(request, session)
    
    valid_statuses = ["draft", "ready", "in_progress", "done", "blocked"]
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    # Get the story
    result = await session.execute(
        select(UserStory).where(UserStory.story_id == story_id)
    )
    story = result.scalar_one_or_none()
    
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    
    # ===== OWNERSHIP CHECK =====
    # For standalone stories, check user_id directly
    if story.is_standalone:
        if story.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this story")
    else:
        # For feature-based stories, verify ownership via feature→epic→user_id
        feature_result = await session.execute(
            select(Feature).where(Feature.feature_id == story.feature_id)
        )
        feature = feature_result.scalar_one_or_none()
        if not feature:
            raise HTTPException(status_code=404, detail="Story's feature not found")
        
        epic_result = await session.execute(
            select(Epic).where(Epic.epic_id == feature.epic_id, Epic.user_id == user_id)
        )
        epic = epic_result.scalar_one_or_none()
        if not epic:
            raise HTTPException(status_code=403, detail="Not authorized to modify this story")
    
    # Update status and blocked reason
    story.status = body.status
    if body.status == "blocked":
        story.blocked_reason = body.blocked_reason
    else:
        story.blocked_reason = None  # Clear blocked reason when not blocked
    
    await session.commit()
    
    return {
        "story_id": story_id,
        "status": body.status,
        "blocked_reason": story.blocked_reason,
        "message": f"Story status updated to {body.status}"
    }


@router.post("/story/{story_id}/commit")
async def commit_story_to_sprint(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Commit a story to the current sprint"""
    from db.feature_models import Feature
    
    user_id = await get_current_user_id(request, session)
    
    # Get delivery context for sprint number
    ctx = await get_delivery_context(user_id, session)
    sprint_info = calculate_sprint_info(ctx) if ctx else None
    
    if not sprint_info:
        raise HTTPException(status_code=400, detail="Sprint not configured")
    
    # Get the story
    result = await session.execute(
        select(UserStory).where(UserStory.story_id == story_id)
    )
    story = result.scalar_one_or_none()
    
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    
    # ===== OWNERSHIP CHECK =====
    # For standalone stories, check user_id directly
    if story.is_standalone:
        if story.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this story")
    else:
        # For feature-based stories, verify ownership via feature→epic→user_id
        feature_result = await session.execute(
            select(Feature).where(Feature.feature_id == story.feature_id)
        )
        feature = feature_result.scalar_one_or_none()
        if not feature:
            raise HTTPException(status_code=404, detail="Story's feature not found")
        
        epic_result = await session.execute(
            select(Epic).where(Epic.epic_id == feature.epic_id, Epic.user_id == user_id)
        )
        epic = epic_result.scalar_one_or_none()
        if not epic:
            raise HTTPException(status_code=403, detail="Not authorized to modify this story")
    
    # Assign to current sprint and set to ready
    story.sprint_number = sprint_info.sprint_number
    if not story.status or story.status == "draft":
        story.status = "ready"
    
    await session.commit()
    
    return {
        "story_id": story_id,
        "sprint_number": sprint_info.sprint_number,
        "status": story.status,
        "message": f"Story committed to Sprint {sprint_info.sprint_number}"
    }


# ============================================
# Sprint Insights Storage & Retrieval
# ============================================

async def save_sprint_insight(
    session: AsyncSession,
    user_id: str,
    sprint_number: int,
    insight_type: str,
    content: dict
) -> SprintInsight:
    """Save a sprint insight to the database"""
    insight = SprintInsight(
        user_id=user_id,
        sprint_number=sprint_number,
        insight_type=insight_type,
        content=content,
        generated_at=datetime.now(timezone.utc)
    )
    session.add(insight)
    await session.commit()
    await session.refresh(insight)
    return insight


@router.get("/insights/current", response_model=SprintInsightsResponse)
async def get_current_sprint_insights(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Get all saved AI-generated insights for the current sprint.
    """
    user_id = await get_current_user_id(request, session)
    
    # Get current sprint number
    ctx = await get_delivery_context(user_id, session)
    sprint_info = calculate_sprint_info(ctx) if ctx else None
    
    if not sprint_info:
        return SprintInsightsResponse(sprint_number=0)
    
    # Get all insights for current sprint
    result = await session.execute(
        select(SprintInsight)
        .where(
            SprintInsight.user_id == user_id,
            SprintInsight.sprint_number == sprint_info.sprint_number
        )
        .order_by(SprintInsight.generated_at.desc())
    )
    insights = result.scalars().all()
    
    # Group by type, keeping only the most recent
    insights_by_type = {}
    for insight in insights:
        if insight.insight_type not in insights_by_type:
            insights_by_type[insight.insight_type] = SavedInsight(
                insight_id=insight.insight_id,
                insight_type=insight.insight_type,
                content=insight.content,
                generated_at=insight.generated_at.isoformat() if insight.generated_at else ""
            )
    
    return SprintInsightsResponse(
        sprint_number=sprint_info.sprint_number,
        kickoff_plan=insights_by_type.get("kickoff_plan"),
        standup_summary=insights_by_type.get("standup_summary"),
        wip_suggestions=insights_by_type.get("wip_suggestions")
    )


@router.get("/insights/{sprint_number}", response_model=SprintInsightsResponse)
async def get_sprint_insights(
    request: Request,
    sprint_number: int,
    session: AsyncSession = Depends(get_db)
):
    """
    Get all saved AI-generated insights for a sprint.
    Returns the most recent insight of each type.
    """
    user_id = await get_current_user_id(request, session)
    
    # Get all insights for this sprint, ordered by generated_at desc
    result = await session.execute(
        select(SprintInsight)
        .where(
            SprintInsight.user_id == user_id,
            SprintInsight.sprint_number == sprint_number
        )
        .order_by(SprintInsight.generated_at.desc())
    )
    insights = result.scalars().all()
    
    # Group by type, keeping only the most recent
    insights_by_type = {}
    for insight in insights:
        if insight.insight_type not in insights_by_type:
            insights_by_type[insight.insight_type] = SavedInsight(
                insight_id=insight.insight_id,
                insight_type=insight.insight_type,
                content=insight.content,
                generated_at=insight.generated_at.isoformat() if insight.generated_at else ""
            )
    
    return SprintInsightsResponse(
        sprint_number=sprint_number,
        kickoff_plan=insights_by_type.get("kickoff_plan"),
        standup_summary=insights_by_type.get("standup_summary"),
        wip_suggestions=insights_by_type.get("wip_suggestions")
    )


# ============================================
# AI-Powered Sprint Features
# ============================================

@router.post("/ai/kickoff-plan", response_model=SprintKickoffPlan)
async def generate_sprint_kickoff(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered sprint kickoff plan.
    
    Input: Ready stories + AC + dependencies + capacity
    Output: Sprint goal, top 5 stories, sequencing, risks
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
    
    # Get current sprint data
    ctx = await get_delivery_context(user_id, session)
    sprint_info = calculate_sprint_info(ctx) if ctx else None
    
    if not sprint_info:
        raise HTTPException(status_code=400, detail="Sprint not configured")
    
    # Get LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured. Please add your API key in Settings.")
    
    # Get ready stories for this sprint
    epics_result = await session.execute(
        select(Epic.epic_id, Epic.title).where(Epic.user_id == user_id, Epic.is_archived.is_(False))
    )
    epics = {e[0]: e[1] for e in epics_result.fetchall()}
    
    from db.feature_models import Feature
    features_result = await session.execute(
        select(Feature.feature_id, Feature.title, Feature.epic_id).where(Feature.epic_id.in_(epics.keys()))
    )
    features = {f[0]: {"title": f[1], "epic_id": f[2]} for f in features_result.fetchall()}
    
    stories_result = await session.execute(
        select(UserStory).where(
            UserStory.feature_id.in_(features.keys()),
            UserStory.sprint_number == sprint_info.sprint_number
        )
    )
    stories = stories_result.scalars().all()
    
    if not stories:
        raise HTTPException(status_code=400, detail="No stories committed to current sprint")
    
    # Calculate capacity
    sprint_capacity = (ctx["num_developers"] or 0) * (ctx["points_per_dev_per_sprint"] or 8)
    
    # Build story data for AI - collect valid IDs for validation
    valid_story_ids = set()
    stories_for_ai = []
    for story in stories:
        valid_story_ids.add(story.story_id)
        feature_data = features.get(story.feature_id, {})
        stories_for_ai.append({
            "id": story.story_id,
            "title": story.title or story.story_text[:50],
            "story_text": story.story_text,
            "acceptance_criteria": story.acceptance_criteria or [],
            "points": story.story_points,
            "priority": story.priority,
            "dependencies": story.dependencies or [],
            "feature": feature_data.get("title", ""),
            "epic": epics.get(feature_data.get("epic_id", ""), ""),
            "status": story.status
        })
    
    system_prompt = """You are a Senior Scrum Master helping with sprint planning.

Given the committed stories for a sprint, generate a kickoff plan.

IMPORTANT: Only reference story IDs from the provided list. Do not invent IDs.

Return ONLY valid JSON (no markdown fences):
{
  "sprint_goal": "One sentence summarizing what the team will deliver",
  "top_stories": [
    {"id": "story_id", "title": "title", "reason": "Why this is priority"}
  ],
  "sequencing": [
    "Start with X because...",
    "Then Y in parallel with...",
    "Finally Z after..."
  ],
  "risks": [
    "Risk 1: Description",
    "Risk 2: Description",
    "Risk 3: Description"
  ]
}"""

    user_prompt = f"""Sprint {sprint_info.sprint_number}
Capacity: {sprint_capacity} points
Team: {ctx['num_developers']} developers
Sprint length: {ctx['sprint_cycle_length']} days

COMMITTED STORIES ({len(stories_for_ai)} stories, {sum(s['points'] or 0 for s in stories_for_ai)} points):
{json_lib.dumps(stories_for_ai, indent=2)}

Generate the sprint kickoff plan."""

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
            schema=SprintKickoffPlan,
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
            logger.error(f"Failed to parse AI kickoff-plan response after repairs: {validation_result.errors}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate sprint kickoff plan: {', '.join(validation_result.errors)}"
            )
        
        # Validate story IDs in top_stories to prevent hallucination
        result_data = validation_result.data
        validated_top_stories = [
            s for s in result_data.get("top_stories", [])
            if s.get("id") in valid_story_ids
        ]
        result_data["top_stories"] = validated_top_stories
        
        # ===== SAVE INSIGHT TO DATABASE =====
        await save_sprint_insight(
            session=session,
            user_id=user_id,
            sprint_number=sprint_info.sprint_number,
            insight_type="kickoff_plan",
            content=result_data
        )
        
        return SprintKickoffPlan(**result_data)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Sprint kickoff plan generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate sprint kickoff plan: {str(e)}")


@router.post("/ai/standup-summary", response_model=StandupSummary)
async def generate_standup_summary(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered daily standup summary.
    
    Input: Status changes since yesterday
    Output: What changed, what's blocked, what to do next
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
    
    # Get current sprint data
    ctx = await get_delivery_context(user_id, session)
    sprint_info = calculate_sprint_info(ctx) if ctx else None
    
    if not sprint_info:
        raise HTTPException(status_code=400, detail="Sprint not configured")
    
    # Get LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured. Please add your API key in Settings.")
    
    # Get stories for this sprint
    epics_result = await session.execute(
        select(Epic.epic_id).where(Epic.user_id == user_id, Epic.is_archived.is_(False))
    )
    epic_ids = [e[0] for e in epics_result.fetchall()]
    
    from db.feature_models import Feature
    features_result = await session.execute(
        select(Feature.feature_id).where(Feature.epic_id.in_(epic_ids))
    )
    feature_ids = [f[0] for f in features_result.fetchall()]
    
    stories_result = await session.execute(
        select(UserStory).where(
            UserStory.feature_id.in_(feature_ids),
            UserStory.sprint_number == sprint_info.sprint_number
        )
    )
    stories = stories_result.scalars().all()
    
    if not stories:
        raise HTTPException(status_code=400, detail="No stories in current sprint")
    
    # Build current state
    stories_by_status = {
        "ready": [s for s in stories if s.status == "ready"],
        "in_progress": [s for s in stories if s.status == "in_progress"],
        "done": [s for s in stories if s.status == "done"],
        "blocked": [s for s in stories if s.status == "blocked"],
    }
    
    system_prompt = """You are a Scrum Master generating a daily standup summary.

Given the current sprint state, generate a concise standup summary.

Return ONLY valid JSON (no markdown fences):
{
  "what_changed": ["Change 1", "Change 2"],
  "whats_blocked": ["Blocked item 1 - reason"],
  "what_to_do_next": ["Action 1", "Action 2", "Action 3"],
  "summary": "One sentence overall status"
}"""

    blocked_info = [
        f"{s.title or s.story_text[:30]} - {s.blocked_reason or 'No reason given'}"
        for s in stories_by_status["blocked"]
    ]
    
    user_prompt = f"""Sprint {sprint_info.sprint_number} Status ({sprint_info.days_remaining} days remaining):

READY ({len(stories_by_status['ready'])}): {', '.join([s.title or 'Untitled' for s in stories_by_status['ready'][:5]])}
IN PROGRESS ({len(stories_by_status['in_progress'])}): {', '.join([s.title or 'Untitled' for s in stories_by_status['in_progress']])}
DONE ({len(stories_by_status['done'])}): {', '.join([s.title or 'Untitled' for s in stories_by_status['done'][:5]])}
BLOCKED ({len(stories_by_status['blocked'])}): {'; '.join(blocked_info) if blocked_info else 'None'}

Total points: {sum(s.story_points or 0 for s in stories)}
Completed: {sum(s.story_points or 0 for s in stories_by_status['done'])}

Generate the standup summary."""

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
            schema=StandupSummary,
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
            logger.error(f"Failed to parse AI standup-summary response after repairs: {validation_result.errors}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate standup summary: {', '.join(validation_result.errors)}"
            )
        
        # ===== SAVE INSIGHT TO DATABASE =====
        await save_sprint_insight(
            session=session,
            user_id=user_id,
            sprint_number=sprint_info.sprint_number,
            insight_type="standup_summary",
            content=validation_result.data
        )
        
        return StandupSummary(**validation_result.data)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Standup summary generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate standup summary: {str(e)}")


@router.post("/ai/wip-suggestions", response_model=WipSuggestions)
async def generate_wip_suggestions(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered WIP optimization suggestions.
    
    If in_progress is overloaded, recommend what to finish first vs pause.
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
    
    # Get current sprint data
    ctx = await get_delivery_context(user_id, session)
    sprint_info = calculate_sprint_info(ctx) if ctx else None
    
    if not sprint_info:
        raise HTTPException(status_code=400, detail="Sprint not configured")
    
    # Get LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured. Please add your API key in Settings.")
    
    # Get in-progress stories
    epics_result = await session.execute(
        select(Epic.epic_id).where(Epic.user_id == user_id, Epic.is_archived.is_(False))
    )
    epic_ids = [e[0] for e in epics_result.fetchall()]
    
    from db.feature_models import Feature
    features_result = await session.execute(
        select(Feature.feature_id).where(Feature.epic_id.in_(epic_ids))
    )
    feature_ids = [f[0] for f in features_result.fetchall()]
    
    stories_result = await session.execute(
        select(UserStory).where(
            UserStory.feature_id.in_(feature_ids),
            UserStory.sprint_number == sprint_info.sprint_number,
            UserStory.status == "in_progress"
        )
    )
    in_progress_stories = stories_result.scalars().all()
    
    if len(in_progress_stories) < 2:
        return WipSuggestions(
            finish_first=[],
            consider_pausing=[],
            reasoning="WIP looks healthy - only 1 or fewer stories in progress."
        )
    
    # Build story data - collect valid IDs for validation
    valid_story_ids = set()
    stories_for_ai = []
    for s in in_progress_stories:
        valid_story_ids.add(s.story_id)
        stories_for_ai.append({
            "id": s.story_id,
            "title": s.title or s.story_text[:50],
            "points": s.story_points,
            "priority": s.priority,
        })
    
    system_prompt = """You are a Scrum Master helping optimize work-in-progress.

Given in-progress stories, recommend which to focus on first and which to pause.

IMPORTANT: Only reference story IDs from the provided list. Do not invent IDs.

Return ONLY valid JSON (no markdown fences):
{
  "finish_first": [
    {"id": "story_id", "title": "title", "reason": "Why to prioritize"}
  ],
  "consider_pausing": [
    {"id": "story_id", "title": "title", "reason": "Why to pause"}
  ],
  "reasoning": "Brief explanation of the WIP optimization strategy"
}"""

    user_prompt = f"""Sprint {sprint_info.sprint_number} - {sprint_info.days_remaining} days remaining
Team size: {ctx['num_developers']} developers

IN PROGRESS ({len(in_progress_stories)} stories):
{json_lib.dumps(stories_for_ai, indent=2)}

Recommended WIP limit: {ctx['num_developers'] + 1} stories
Current WIP: {len(in_progress_stories)} stories

Generate WIP optimization suggestions."""

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
            schema=WipSuggestions,
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
            logger.error(f"Failed to parse AI wip-suggestions response after repairs: {validation_result.errors}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate WIP suggestions: {', '.join(validation_result.errors)}"
            )
        
        # Validate story IDs to prevent hallucination
        result_data = validation_result.data
        validated_finish_first = [
            s for s in result_data.get("finish_first", [])
            if s.get("id") in valid_story_ids
        ]
        validated_consider_pausing = [
            s for s in result_data.get("consider_pausing", [])
            if s.get("id") in valid_story_ids
        ]
        result_data["finish_first"] = validated_finish_first
        result_data["consider_pausing"] = validated_consider_pausing
        
        # ===== SAVE INSIGHT TO DATABASE =====
        await save_sprint_insight(
            session=session,
            user_id=user_id,
            sprint_number=sprint_info.sprint_number,
            insight_type="wip_suggestions",
            content=result_data
        )
        
        return WipSuggestions(**result_data)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"WIP suggestions generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate WIP suggestions: {str(e)}")


@router.get("/from-delivery-reality/{epic_id}")
async def get_sprint_stories_from_scope_plan(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get stories ready for sprint planning from a Delivery Reality scope plan.
    
    This connects Delivery Reality → Sprints by using the saved scope plan
    to suggest which stories to commit to the sprint.
    """
    from db.models import ScopePlan
    
    user_id = await get_current_user_id(request, session)
    
    # Get active scope plan
    plan_result = await session.execute(
        select(ScopePlan).where(
            ScopePlan.epic_id == epic_id,
            ScopePlan.user_id == user_id,
            ScopePlan.is_active.is_(True)
        )
    )
    plan = plan_result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(status_code=404, detail="No active scope plan found for this initiative")
    
    deferred_ids = set(plan.deferred_story_ids or [])
    
    # Get delivery context
    ctx = await get_delivery_context(user_id, session)
    sprint_info = calculate_sprint_info(ctx) if ctx else None
    
    # Get stories from this epic's features
    from db.feature_models import Feature
    features_result = await session.execute(
        select(Feature.feature_id).where(Feature.epic_id == epic_id)
    )
    feature_ids = [f[0] for f in features_result.fetchall()]
    
    stories_result = await session.execute(
        select(UserStory).where(UserStory.feature_id.in_(feature_ids))
    )
    stories = stories_result.scalars().all()
    
    # Separate into included (for sprint) and deferred
    included = []
    deferred = []
    
    for story in stories:
        story_data = {
            "story_id": story.story_id,
            "title": story.title or story.story_text[:50],
            "story_points": story.story_points,
            "priority": story.priority,
            "current_sprint": story.sprint_number,
            "status": story.status,
        }
        
        if story.story_id in deferred_ids:
            deferred.append(story_data)
        else:
            included.append(story_data)
    
    sprint_capacity = (ctx["num_developers"] or 0) * (ctx["points_per_dev_per_sprint"] or 8) if ctx else 0
    total_included_points = sum(s["story_points"] or 0 for s in included)
    
    return {
        "epic_id": epic_id,
        "sprint_number": sprint_info.sprint_number if sprint_info else None,
        "sprint_capacity": sprint_capacity,
        "included_stories": included,
        "included_points": total_included_points,
        "deferred_stories": deferred,
        "fits_in_sprint": total_included_points <= sprint_capacity,
        "message": f"{len(included)} stories ({total_included_points} pts) ready for sprint from scope plan"
    }
