"""
PRD Document API for JarlPM
Save and retrieve Product Requirements Documents
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from db import get_db
from db.models import Epic, PRDDocument
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prd", tags=["prd"])


class SavePRDRequest(BaseModel):
    """Request to save PRD"""
    epic_id: str
    content: str  # Frontend sends as 'content', we'll store in 'sections'
    title: Optional[str] = None
    version: str = "1.0"
    status: str = "draft"


@router.get("/list")
async def list_prds(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all PRDs for the current user"""
    user_id = await get_current_user_id(request, session)
    
    # Get all PRDs with epic info
    result = await session.execute(
        select(PRDDocument, Epic)
        .join(Epic, PRDDocument.epic_id == Epic.epic_id)
        .where(PRDDocument.user_id == user_id)
        .order_by(PRDDocument.updated_at.desc())
    )
    rows = result.all()
    
    prds = []
    for prd, epic in rows:
        prds.append({
            "prd_id": prd.prd_id,
            "epic_id": prd.epic_id,
            "epic_title": epic.title,
            "title": prd.title or epic.title,
            "version": prd.version,
            "status": prd.status,
            "created_at": prd.created_at.isoformat(),
            "updated_at": prd.updated_at.isoformat(),
        })
    
    return {"prds": prds}


@router.get("/epics-without-prd")
async def get_epics_without_prd(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all epics that don't have a PRD yet"""
    user_id = await get_current_user_id(request, session)
    
    # Get epics that don't have a PRD
    result = await session.execute(
        select(Epic)
        .outerjoin(PRDDocument, Epic.epic_id == PRDDocument.epic_id)
        .where(
            Epic.user_id == user_id,
            PRDDocument.id.is_(None)
        )
        .order_by(Epic.updated_at.desc())
    )
    epics = result.scalars().all()
    
    return {
        "epics": [
            {
                "epic_id": e.epic_id,
                "title": e.title,
                "stage": e.current_stage,
            }
            for e in epics
        ]
    }


@router.get("/{epic_id}")
async def get_prd(
    epic_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get saved PRD for an Epic"""
    user_id = await get_current_user_id(request, session)
    
    # Get epic to verify ownership
    epic_result = await session.execute(
        select(Epic).where(
            Epic.epic_id == epic_id,
            Epic.user_id == user_id
        )
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get saved PRD
    prd_result = await session.execute(
        select(PRDDocument).where(PRDDocument.epic_id == epic_id)
    )
    prd = prd_result.scalar_one_or_none()
    
    if not prd:
        return {
            "epic_id": epic_id,
            "epic_title": epic.title,
            "prd": None,
            "exists": False
        }
    
    return {
        "epic_id": epic_id,
        "epic_title": epic.title,
        "prd": {
            "prd_id": prd.prd_id,
            "content": prd.sections.get("content", "") if prd.sections else "",  # Extract content from JSON
            "title": prd.title,
            "version": prd.version,
            "status": prd.status,
        },
        "updated_at": prd.updated_at.isoformat(),
        "exists": True
    }


@router.post("/save")
async def save_prd(
    request: Request,
    body: SavePRDRequest,
    session: AsyncSession = Depends(get_db)
):
    """Save or update PRD for an Epic"""
    user_id = await get_current_user_id(request, session)
    
    # Verify epic ownership
    epic_result = await session.execute(
        select(Epic).where(
            Epic.epic_id == body.epic_id,
            Epic.user_id == user_id
        )
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Check if PRD already exists
    existing_result = await session.execute(
        select(PRDDocument).where(PRDDocument.epic_id == body.epic_id)
    )
    existing_prd = existing_result.scalar_one_or_none()
    
    if existing_prd:
        # Update existing PRD
        existing_prd.sections = {"content": body.content}  # Store as JSON object
        existing_prd.title = body.title or epic.title
        existing_prd.version = body.version
        existing_prd.status = body.status
        existing_prd.source = "manual"
        existing_prd.updated_at = datetime.now(timezone.utc)
    else:
        # Create new PRD
        new_prd = PRDDocument(
            epic_id=body.epic_id,
            user_id=user_id,
            sections={"content": body.content},  # Store as JSON object
            title=body.title or epic.title,
            version=body.version,
            status=body.status,
            source="manual"
        )
        session.add(new_prd)
    
    await session.commit()
    
    return {
        "success": True,
        "epic_id": body.epic_id,
        "message": "PRD saved successfully"
    }


@router.delete("/{epic_id}")
async def delete_prd(
    epic_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Delete PRD for an Epic"""
    user_id = await get_current_user_id(request, session)
    
    # Get PRD
    prd_result = await session.execute(
        select(PRDDocument).where(
            PRDDocument.epic_id == epic_id,
            PRDDocument.user_id == user_id
        )
    )
    prd = prd_result.scalar_one_or_none()
    
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    
    await session.delete(prd)
    await session.commit()
    
    return {"success": True, "message": "PRD deleted"}


@router.post("/generate/{epic_id}")
async def generate_prd_with_llm(
    epic_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate a comprehensive PRD using LLM from epic data.
    Uses the epic's problem statement, features, and stories to create
    a senior PM-quality PRD document.
    """
    from services.llm_service import LLMService
    from services.strict_output_service import StrictOutputService
    from services.epic_service import EpicService
    from db.feature_models import Feature
    from db.user_story_models import UserStory
    
    user_id = await get_current_user_id(request, session)
    
    # Check subscription
    epic_service = EpicService(session)
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required for AI features")
    
    # Get epic
    epic_result = await session.execute(
        select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured. Please add your API key in Settings.")
    
    # Get features
    features_result = await session.execute(
        select(Feature).where(Feature.epic_id == epic_id)
    )
    features = features_result.scalars().all()
    
    # Get stories for each feature
    feature_ids = [f.feature_id for f in features]
    stories_result = await session.execute(
        select(UserStory).where(UserStory.feature_id.in_(feature_ids))
    ) if feature_ids else None
    stories = stories_result.scalars().all() if stories_result else []
    
    # Group stories by feature
    stories_by_feature = {}
    for story in stories:
        if story.feature_id not in stories_by_feature:
            stories_by_feature[story.feature_id] = []
        stories_by_feature[story.feature_id].append(story)
    
    # Build context for LLM
    features_context = []
    for f in features:
        feature_stories = stories_by_feature.get(f.feature_id, [])
        features_context.append({
            "name": f.title,
            "description": f.description,
            "priority": f.priority,
            "stories": [
                {
                    "title": s.title or s.story_text[:50],
                    "story_text": s.story_text,
                    "acceptance_criteria": s.acceptance_criteria,
                    "points": s.story_points,
                    "priority": s.priority
                }
                for s in feature_stories
            ]
        })
    
    system_prompt = """You are a Senior Product Manager creating a comprehensive PRD document.

Given the epic data and features, generate a professional PRD in Markdown format that would be ready to share with stakeholders.

The PRD should include:
1. Executive Summary - Problem, Vision, Target Users
2. Goals & Objectives - Desired outcomes, success metrics, key results
3. User Personas - Detailed personas based on target users
4. Feature Requirements - Each feature with user stories and acceptance criteria
5. Technical Considerations - Architecture notes, integrations, constraints
6. Risks & Mitigations - Key risks and how to address them
7. Success Criteria - How we'll measure success
8. Timeline & Milestones - Suggested phasing

Make it actionable, specific, and professional. Use the actual data provided, don't invent new features."""

    user_prompt = f"""Create a comprehensive PRD for:

PRODUCT: {epic.title}
TAGLINE: {epic.tagline or 'N/A'}

PROBLEM STATEMENT:
{epic.problem_statement or 'Not defined'}

VISION:
{epic.vision or 'Not defined'}

TARGET USERS:
{epic.target_users or 'Not defined'}

DESIRED OUTCOME:
{epic.desired_outcome or 'Not defined'}

FEATURES AND USER STORIES:
{logger.info(f"Features context: {features_context}")}
{str(features_context) if features_context else 'No features defined yet'}

Generate a professional, stakeholder-ready PRD document in Markdown format."""

    try:
        full_response = ""
        async for chunk in llm_service.generate_stream(user_id, system_prompt, user_prompt):
            full_response += chunk
        
        if not full_response.strip():
            raise HTTPException(status_code=500, detail="LLM returned empty response")
        
        # Save the generated PRD
        existing_result = await session.execute(
            select(PRDDocument).where(PRDDocument.epic_id == epic_id)
        )
        existing_prd = existing_result.scalar_one_or_none()
        
        if existing_prd:
            existing_prd.sections = {"content": full_response}
            existing_prd.source = "ai_generated"
            existing_prd.updated_at = datetime.now(timezone.utc)
        else:
            new_prd = PRDDocument(
                epic_id=epic_id,
                user_id=user_id,
                sections={"content": full_response},
                title=epic.title,
                version="1.0",
                status="draft",
                source="ai_generated"
            )
            session.add(new_prd)
        
        await session.commit()
        
        return {
            "success": True,
            "epic_id": epic_id,
            "content": full_response,
            "source": "ai_generated",
            "message": "PRD generated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PRD generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PRD: {str(e)}")
