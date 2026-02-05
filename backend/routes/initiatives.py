"""
Initiative Library Routes for JarlPM
List, search, filter, and manage saved initiatives.

Turns JarlPM from a one-off generator into a system of record.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, desc, asc

from db import get_db
from db.models import Epic, EpicSnapshot
from db.feature_models import Feature
from db.user_story_models import UserStory
from routes.auth import get_current_user_id

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/initiatives", tags=["initiatives"])


class InitiativeStatus(str, Enum):
    """Initiative statuses for V1"""
    DRAFT = "draft"        # New initiatives start here
    ACTIVE = "active"      # Work in progress
    COMPLETED = "completed"  # Finished
    ARCHIVED = "archived"  # Reversible soft-delete


class InitiativeSummary(BaseModel):
    """Summary view of an initiative for list display (table row)"""
    epic_id: str
    title: str
    tagline: Optional[str] = None
    status: str
    problem_statement: Optional[str] = None
    
    # Metrics (optional columns)
    features_count: int = 0
    stories_count: int = 0
    total_points: int = 0
    
    # Dates
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InitiativeListResponse(BaseModel):
    """Paginated list of initiatives"""
    initiatives: List[InitiativeSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


class InitiativeStatusUpdate(BaseModel):
    """Request to update initiative status"""
    status: InitiativeStatus


class InitiativeDuplicateRequest(BaseModel):
    """Request to duplicate an initiative"""
    new_title: Optional[str] = None


class InitiativeDetail(BaseModel):
    """Full initiative detail view"""
    epic_id: str
    title: str
    tagline: Optional[str] = None
    status: str
    
    # PRD content (from EpicSnapshot)
    problem_statement: Optional[str] = None
    desired_outcome: Optional[str] = None
    epic_summary: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    
    # Metrics
    features_count: int = 0
    stories_count: int = 0
    total_points: int = 0
    
    # Features summary
    features: List[dict] = []
    
    # Sprint plan (if available)
    sprint_plan: Optional[dict] = None
    
    # Dates
    created_at: datetime
    updated_at: datetime


def map_stage_to_status(stage: str) -> str:
    """Map Epic current_stage to Initiative status for frontend"""
    status_map = {
        "problem_capture": "draft",
        "problem_confirmed": "draft",
        "outcome_capture": "draft",
        "outcome_confirmed": "draft",
        "epic_drafted": "active",
        "epic_locked": "completed"
    }
    return status_map.get(stage, "draft")


def map_status_to_stages(status: str) -> List[str]:
    """Map Initiative status to possible Epic stages for filtering"""
    stage_map = {
        "draft": ["problem_capture", "problem_confirmed", "outcome_capture", "outcome_confirmed"],
        "active": ["epic_drafted"],
        "completed": ["epic_locked"],
        "archived": []  # Archived is tracked separately
    }
    return stage_map.get(status, [])


@router.get("", response_model=InitiativeListResponse)
async def list_initiatives(
    request: Request,
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: draft, active, completed, archived"),
    search: Optional[str] = Query(None, description="Search in title, tagline, or problem statement"),
    sort_by: str = Query("updated_at", description="Sort field: updated_at, created_at, title"),
    sort_order: str = Query("desc", description="Sort order: asc or desc")
):
    """
    List all initiatives for the current user with pagination and filtering.
    Default sort: Most recently updated first.
    """
    user_id = await get_current_user_id(request, session)
    
    # Base query
    base_filter = Epic.user_id == user_id
    
    # Status filter - map to epic stages
    if status:
        stages = map_status_to_stages(status)
        if stages:
            base_filter = and_(base_filter, Epic.current_stage.in_(stages))
    
    # Count total
    count_query = select(func.count(Epic.id)).where(base_filter)
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # Sort
    sort_column = getattr(Epic, sort_by, Epic.updated_at)
    order_func = desc if sort_order == "desc" else asc
    
    # Fetch initiatives with pagination
    offset = (page - 1) * page_size
    query = (
        select(Epic)
        .where(base_filter)
        .order_by(order_func(sort_column))
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(query)
    epics = result.scalars().all()
    
    # Build summaries with feature/story counts
    initiatives = []
    for epic in epics:
        # Get feature count
        feature_count_q = select(func.count(Feature.id)).where(Feature.epic_id == epic.epic_id)
        feature_result = await session.execute(feature_count_q)
        features_count = feature_result.scalar() or 0
        
        # Get story count and total points
        story_q = select(
            func.count(UserStory.id),
            func.coalesce(func.sum(UserStory.story_points), 0)
        ).join(Feature, UserStory.feature_id == Feature.feature_id).where(Feature.epic_id == epic.epic_id)
        story_result = await session.execute(story_q)
        story_row = story_result.fetchone()
        stories_count = story_row[0] if story_row else 0
        total_points = int(story_row[1]) if story_row else 0
        
        # Get snapshot for problem statement and tagline
        snapshot_q = select(EpicSnapshot).where(EpicSnapshot.epic_id == epic.epic_id)
        snapshot_result = await session.execute(snapshot_q)
        snapshot = snapshot_result.scalar_one_or_none()
        
        # Generate tagline from problem statement if needed
        problem_text = snapshot.problem_statement if snapshot and snapshot.problem_statement else None
        tagline = problem_text[:100] + "..." if problem_text and len(problem_text) > 100 else problem_text
        
        # Map stage to display status
        display_status = map_stage_to_status(epic.current_stage)
        
        initiatives.append(InitiativeSummary(
            epic_id=epic.epic_id,
            title=epic.title,
            tagline=tagline,
            status=display_status,
            problem_statement=problem_text[:200] if problem_text and len(problem_text) > 200 else problem_text,
            features_count=features_count,
            stories_count=stories_count,
            total_points=total_points,
            created_at=epic.created_at,
            updated_at=epic.updated_at
        ))
    
    # Apply search filter client-side to include problem statement
    # (since we need to join with snapshot)
    if search:
        search_lower = search.lower()
        initiatives = [
            i for i in initiatives
            if search_lower in (i.title or "").lower()
            or search_lower in (i.tagline or "").lower()
            or search_lower in (i.problem_statement or "").lower()
        ]
        total = len(initiatives)
    
    return InitiativeListResponse(
        initiatives=initiatives,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(initiatives)) < total
    )


@router.get("/{epic_id}", response_model=InitiativeDetail)
async def get_initiative(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get full details of a specific initiative.
    """
    user_id = await get_current_user_id(request, session)
    
    # Fetch epic
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Fetch snapshot
    snapshot_q = select(EpicSnapshot).where(EpicSnapshot.epic_id == epic_id)
    snapshot_result = await session.execute(snapshot_q)
    snapshot = snapshot_result.scalar_one_or_none()
    
    # Fetch features with stories (sorted by priority/created_at)
    features_q = select(Feature).where(Feature.epic_id == epic_id).order_by(Feature.priority.nullslast(), Feature.created_at)
    features_result = await session.execute(features_q)
    features = features_result.scalars().all()
    
    features_data = []
    total_points = 0
    stories_count = 0
    
    for feature in features:
        # Get stories for this feature
        stories_q = select(UserStory).where(UserStory.feature_id == feature.feature_id)
        stories_result = await session.execute(stories_q)
        stories = stories_result.scalars().all()
        
        feature_points = sum(s.story_points or 0 for s in stories)
        total_points += feature_points
        stories_count += len(stories)
        
        features_data.append({
            "feature_id": feature.feature_id,
            "name": feature.title,  # Use title field
            "description": feature.description,
            "priority": feature.moscow_score or "should-have",
            "stories_count": len(stories),
            "total_points": feature_points,
            "stories": [
                {
                    "story_id": s.story_id,
                    "title": s.title,
                    "story_text": s.story_text,
                    "points": s.story_points,
                    "status": s.current_stage,
                    "labels": s.labels or [],
                    "priority": s.story_priority
                }
                for s in stories
            ]
        })
    
    # Map status
    display_status = map_stage_to_status(epic.current_stage)
    
    return InitiativeDetail(
        epic_id=epic.epic_id,
        title=epic.title,
        tagline=snapshot.problem_statement[:100] if snapshot and snapshot.problem_statement else None,
        status=display_status,
        problem_statement=snapshot.problem_statement if snapshot else None,
        desired_outcome=snapshot.desired_outcome if snapshot else None,
        epic_summary=snapshot.epic_summary if snapshot else None,
        acceptance_criteria=snapshot.acceptance_criteria if snapshot else None,
        features_count=len(features),
        stories_count=stories_count,
        total_points=total_points,
        features=features_data,
        created_at=epic.created_at,
        updated_at=epic.updated_at
    )


@router.patch("/{epic_id}/status")
async def update_initiative_status(
    request: Request,
    epic_id: str,
    body: InitiativeStatusUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Update the status of an initiative.
    - draft: New initiatives or work in progress (early stages)
    - active: Epic drafted and being refined
    - completed: Epic locked and ready
    - archived: Soft-deleted (reversible)
    """
    user_id = await get_current_user_id(request, session)
    
    # Fetch epic
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Note: We don't change the actual Epic stage here since that's managed
    # by the epic workflow. Status is a UI-level concept.
    # For archived, we could add a separate field in future.
    epic.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {"message": f"Status updated to {body.status.value}", "epic_id": epic_id}


@router.post("/{epic_id}/duplicate")
async def duplicate_initiative(
    request: Request,
    epic_id: str,
    body: InitiativeDuplicateRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Duplicate an initiative (creates a copy with all features and stories).
    """
    user_id = await get_current_user_id(request, session)
    
    # Fetch original epic
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    original_epic = epic_result.scalar_one_or_none()
    
    if not original_epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    from db.models import generate_uuid
    
    now = datetime.now(timezone.utc)
    new_title = body.new_title or f"{original_epic.title} (Copy)"
    
    # Create new epic
    new_epic = Epic(
        epic_id=generate_uuid("epic_"),
        user_id=user_id,
        title=new_title,
        current_stage="problem_capture",  # Start fresh
        created_at=now,
        updated_at=now
    )
    session.add(new_epic)
    
    # Copy snapshot if exists
    snapshot_q = select(EpicSnapshot).where(EpicSnapshot.epic_id == epic_id)
    snapshot_result = await session.execute(snapshot_q)
    original_snapshot = snapshot_result.scalar_one_or_none()
    
    if original_snapshot:
        new_snapshot = EpicSnapshot(
            epic_id=new_epic.epic_id,
            problem_statement=original_snapshot.problem_statement,
            desired_outcome=original_snapshot.desired_outcome,
            epic_summary=original_snapshot.epic_summary,
            acceptance_criteria=original_snapshot.acceptance_criteria
        )
        session.add(new_snapshot)
    
    # Copy features and stories
    features_q = select(Feature).where(Feature.epic_id == epic_id)
    features_result = await session.execute(features_q)
    original_features = features_result.scalars().all()
    
    from db.feature_models import generate_uuid as feat_uuid
    from db.user_story_models import generate_uuid as story_uuid
    
    for orig_feat in original_features:
        new_feature = Feature(
            feature_id=feat_uuid("feat_"),
            epic_id=new_epic.epic_id,
            title=orig_feat.title,
            description=orig_feat.description,
            acceptance_criteria=orig_feat.acceptance_criteria,
            current_stage="draft",  # Reset stage
            source=orig_feat.source,
            priority=orig_feat.priority,
            moscow_score=orig_feat.moscow_score,
            created_at=now,
            updated_at=now
        )
        session.add(new_feature)
        
        # Copy stories
        stories_q = select(UserStory).where(UserStory.feature_id == orig_feat.feature_id)
        stories_result = await session.execute(stories_q)
        original_stories = stories_result.scalars().all()
        
        for orig_story in original_stories:
            new_story = UserStory(
                story_id=story_uuid("story_"),
                feature_id=new_feature.feature_id,
                persona=orig_story.persona,
                action=orig_story.action,
                benefit=orig_story.benefit,
                story_text=orig_story.story_text,
                title=orig_story.title,
                acceptance_criteria=orig_story.acceptance_criteria,
                labels=orig_story.labels,
                story_priority=orig_story.story_priority,
                dependencies=orig_story.dependencies,
                risks=orig_story.risks,
                current_stage="draft",  # Reset stage
                source=orig_story.source,
                story_points=orig_story.story_points,
                priority=orig_story.priority,
                version=1,
                created_at=now,
                updated_at=now
            )
            session.add(new_story)
    
    await session.commit()
    
    return {
        "message": "Initiative duplicated",
        "new_epic_id": new_epic.epic_id,
        "title": new_title
    }


@router.patch("/{epic_id}/archive")
async def archive_initiative(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Archive an initiative (soft delete - reversible).
    """
    user_id = await get_current_user_id(request, session)
    
    # Fetch epic
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # For now, we'll track this via updated_at timestamp
    # In future, add a dedicated "archived" field
    epic.updated_at = datetime.now(timezone.utc)
    await session.commit()
    
    return {"message": "Initiative archived", "epic_id": epic_id}


@router.patch("/{epic_id}/unarchive")
async def unarchive_initiative(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Unarchive an initiative (restore from soft delete).
    """
    user_id = await get_current_user_id(request, session)
    
    # Fetch epic
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    epic.updated_at = datetime.now(timezone.utc)
    await session.commit()
    
    return {"message": "Initiative unarchived", "epic_id": epic_id}


@router.delete("/{epic_id}")
async def delete_initiative(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Permanently delete an initiative and all associated data.
    Use archive for reversible soft-delete instead.
    """
    user_id = await get_current_user_id(request, session)
    
    # Fetch epic
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Set the session variable to allow cascade deletes through append-only triggers
    from sqlalchemy import text
    await session.execute(text("SET LOCAL jarlpm.allow_cascade_delete = 'true'"))
    
    # Delete (cascade will handle related records)
    await session.delete(epic)
    await session.commit()
    
    return {"message": "Initiative deleted", "epic_id": epic_id}


@router.get("/stats/summary")
async def get_initiatives_summary(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Get summary statistics for user's initiatives.
    """
    user_id = await get_current_user_id(request, session)
    
    # Count by stage
    total_q = select(func.count(Epic.id)).where(Epic.user_id == user_id)
    total_result = await session.execute(total_q)
    total = total_result.scalar() or 0
    
    draft_stages = ["problem_capture", "problem_confirmed", "outcome_capture", "outcome_confirmed"]
    draft_q = select(func.count(Epic.id)).where(
        Epic.user_id == user_id,
        Epic.current_stage.in_(draft_stages)
    )
    draft_result = await session.execute(draft_q)
    draft_count = draft_result.scalar() or 0
    
    active_q = select(func.count(Epic.id)).where(
        Epic.user_id == user_id,
        Epic.current_stage == "epic_drafted"
    )
    active_result = await session.execute(active_q)
    active_count = active_result.scalar() or 0
    
    completed_q = select(func.count(Epic.id)).where(
        Epic.user_id == user_id,
        Epic.current_stage == "epic_locked"
    )
    completed_result = await session.execute(completed_q)
    completed_count = completed_result.scalar() or 0
    
    return {
        "total": total,
        "draft": draft_count,
        "active": active_count,
        "completed": completed_count
    }


@router.get("/{epic_id}/features/{feature_id}/regenerate")
async def get_feature_for_regeneration(
    request: Request,
    epic_id: str,
    feature_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get feature context for regeneration.
    Returns the feature data needed to regenerate just this feature.
    """
    user_id = await get_current_user_id(request, session)
    
    # Verify ownership
    epic_q = select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    epic_result = await session.execute(epic_q)
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    # Get feature
    feature_q = select(Feature).where(Feature.feature_id == feature_id, Feature.epic_id == epic_id)
    feature_result = await session.execute(feature_q)
    feature = feature_result.scalar_one_or_none()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    # Get snapshot for context
    snapshot_q = select(EpicSnapshot).where(EpicSnapshot.epic_id == epic_id)
    snapshot_result = await session.execute(snapshot_q)
    snapshot = snapshot_result.scalar_one_or_none()
    
    return {
        "epic_id": epic_id,
        "feature_id": feature_id,
        "feature_name": feature.title,  # Use title field
        "feature_description": feature.description,
        "context": {
            "product_name": epic.title,
            "problem_statement": snapshot.problem_statement if snapshot else None,
            "desired_outcome": snapshot.desired_outcome if snapshot else None
        }
    }
