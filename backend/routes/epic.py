from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import logging
import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import get_db
from db.models import (
    Epic as EpicModel, EpicStage, EpicSnapshot, EpicTranscriptEvent,
    EpicDecision, EpicArtifact, ArtifactType, STAGE_ORDER
)
from models.epic import EpicCreate, EpicChatMessage, EpicConfirmProposal, ArtifactCreate
from services.epic_service import EpicService
from services.llm_service import LLMService
from services.prompt_service import PromptService
from services.lock_policy_service import lock_policy
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epics", tags=["epics"])


# Response models
class EpicSnapshotResponse(BaseModel):
    problem_statement: Optional[str] = None
    problem_confirmed_at: Optional[datetime] = None
    desired_outcome: Optional[str] = None
    outcome_confirmed_at: Optional[datetime] = None
    epic_summary: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    epic_locked_at: Optional[datetime] = None


class EpicResponse(BaseModel):
    epic_id: str
    title: str
    current_stage: str  # Changed from EpicStage to str
    snapshot: EpicSnapshotResponse
    pending_proposal: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class EpicListResponse(BaseModel):
    epics: List[EpicResponse]


class TranscriptEventResponse(BaseModel):
    event_id: str
    epic_id: str
    role: str
    content: str
    stage: str  # Changed from EpicStage to str
    event_metadata: Optional[dict] = None
    created_at: datetime


class TranscriptResponse(BaseModel):
    events: List[TranscriptEventResponse]


class DecisionEventResponse(BaseModel):
    decision_id: str
    epic_id: str
    decision_type: str
    from_stage: str  # Changed from EpicStage to str
    to_stage: Optional[str] = None  # Changed from EpicStage to str
    proposal_id: Optional[str] = None
    content_snapshot: Optional[str] = None
    user_id: str
    created_at: datetime


class DecisionResponse(BaseModel):
    decisions: List[DecisionEventResponse]


class ArtifactResponse(BaseModel):
    artifact_id: str
    epic_id: str
    artifact_type: str  # Changed from ArtifactType to str
    title: str
    description: str
    acceptance_criteria: Optional[List[str]] = None
    priority: Optional[int] = None
    created_at: datetime


def snapshot_to_response(snapshot: Optional[EpicSnapshot]) -> EpicSnapshotResponse:
    """Convert SQLAlchemy EpicSnapshot to response model"""
    if not snapshot:
        return EpicSnapshotResponse()
    return EpicSnapshotResponse(
        problem_statement=snapshot.problem_statement,
        problem_confirmed_at=snapshot.problem_confirmed_at,
        desired_outcome=snapshot.desired_outcome,
        outcome_confirmed_at=snapshot.outcome_confirmed_at,
        epic_summary=snapshot.epic_summary,
        acceptance_criteria=snapshot.acceptance_criteria,
        epic_locked_at=snapshot.epic_locked_at
    )


def epic_to_response(epic: EpicModel) -> EpicResponse:
    """Convert SQLAlchemy Epic to response model"""
    return EpicResponse(
        epic_id=epic.epic_id,
        title=epic.title,
        current_stage=epic.current_stage,
        snapshot=snapshot_to_response(epic.snapshot),
        pending_proposal=epic.pending_proposal,
        created_at=epic.created_at,
        updated_at=epic.updated_at
    )


@router.get("", response_model=EpicListResponse)
async def list_epics(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """List all epics for the current user"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    epics = await epic_service.get_user_epics(user_id)
    
    return EpicListResponse(
        epics=[epic_to_response(e) for e in epics]
    )


@router.post("", response_model=EpicResponse, status_code=201)
async def create_epic(
    request: Request, 
    body: EpicCreate,
    session: AsyncSession = Depends(get_db)
):
    """Create a new epic"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    epic = await epic_service.create_epic(user_id, body.title)
    
    # Add initial system message to transcript
    await epic_service.add_transcript_event(
        epic_id=epic.epic_id,
        role="system",
        content=f"Epic '{epic.title}' created. Starting in Problem Capture stage.",
        stage=epic.current_stage
    )
    
    return epic_to_response(epic)


@router.get("/{epic_id}", response_model=EpicResponse)
async def get_epic(
    request: Request, 
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get an epic by ID"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    epic = await epic_service.get_epic(epic_id, user_id)
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    return epic_to_response(epic)


@router.get("/{epic_id}/permissions")
async def get_epic_permissions(
    request: Request, 
    epic_id: str,
    session: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get edit permissions for an epic and its children.
    
    Returns a permission map that the frontend can use to determine
    which actions are allowed at the current epic stage.
    """
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    epic = await epic_service.get_epic(epic_id, user_id)
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get epic status from current stage
    epic_status = lock_policy.get_epic_status(epic.current_stage)
    
    # Get all permissions
    permissions = lock_policy.get_edit_permissions(epic_status, epic.current_stage)
    
    return {
        "epic_id": epic_id,
        "current_stage": epic.current_stage,
        "permissions": permissions
    }


@router.delete("/{epic_id}")
async def delete_epic(
    request: Request, 
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete an epic (requires explicit confirmation - handled by frontend)"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    success = await epic_service.delete_epic(epic_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    return {"message": "Epic deleted"}


@router.post("/{epic_id}/chat")
async def chat_with_epic(
    request: Request, 
    epic_id: str, 
    body: EpicChatMessage,
    session: AsyncSession = Depends(get_db)
):
    """Chat with AI about the epic (streaming response)"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    # Get epic
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Check subscription for AI features
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(
            status_code=402,
            detail="Active subscription required for AI features. Please subscribe to continue."
        )
    
    # Check if user has LLM configured
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(
            status_code=400,
            detail="No LLM provider configured. Please add your API key in settings."
        )
    
    # Add user message to transcript
    await epic_service.add_transcript_event(
        epic_id=epic_id,
        role="user",
        content=body.content,
        stage=epic.current_stage
    )
    
    # Get prompt template for current stage
    template = await prompt_service.get_prompt_for_stage(epic.current_stage)
    if not template:
        raise HTTPException(status_code=500, detail="Prompt template not found for stage")
    
    # Get user's delivery context for prompt injection
    delivery_context = await prompt_service.get_delivery_context(user_id)
    
    # Render prompts with delivery context
    system_prompt, user_prompt = prompt_service.render_prompt(
        template,
        epic.title,
        body.content,
        epic.snapshot,
        delivery_context
    )
    
    # Get conversation history
    history = await epic_service.get_conversation_history(epic_id, limit=20)
    
    async def generate():
        full_response = ""
        try:
            async for chunk in llm_service.generate_stream(
                user_id=user_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_history=history[:-1] if history else None
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Check for proposal in response
            proposal = llm_service.extract_proposal(full_response)
            if proposal:
                target_stage = None
                field = None
                
                if proposal["type"] == "PROBLEM_STATEMENT" and epic.current_stage == EpicStage.PROBLEM_CAPTURE.value:
                    target_stage = EpicStage.PROBLEM_CONFIRMED
                    field = "problem_statement"
                elif proposal["type"] == "DESIRED_OUTCOME" and epic.current_stage == EpicStage.OUTCOME_CAPTURE.value:
                    target_stage = EpicStage.OUTCOME_CONFIRMED
                    field = "desired_outcome"
                elif proposal["type"] == "EPIC_FINAL" and epic.current_stage == EpicStage.EPIC_DRAFTED.value:
                    target_stage = EpicStage.EPIC_LOCKED
                    field = "epic_final"
                
                if target_stage and field:
                    pending = await epic_service.set_pending_proposal(
                        epic_id=epic_id,
                        user_id=user_id,
                        field=field,
                        content=proposal["content"],
                        target_stage=target_stage
                    )
                    yield f"data: {json.dumps({'type': 'proposal', 'proposal_id': pending['proposal_id'], 'field': field, 'content': proposal['content'], 'target_stage': target_stage.value})}\n\n"
            
            # Add assistant response to transcript
            await epic_service.add_transcript_event(
                epic_id=epic_id,
                role="assistant",
                content=full_response,
                stage=epic.current_stage
            )
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except ValueError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except Exception as e:
            logger.error(f"Chat error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred while generating response'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{epic_id}/confirm-proposal", response_model=EpicResponse)
async def confirm_proposal(
    request: Request, 
    epic_id: str, 
    body: EpicConfirmProposal,
    session: AsyncSession = Depends(get_db)
):
    """Confirm or reject a pending proposal"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    
    try:
        if body.confirmed:
            epic = await epic_service.confirm_proposal(epic_id, user_id, body.proposal_id)
            
            # Get human-readable stage name
            stage_display = epic.current_stage.replace("_", " ").title()
            await epic_service.add_transcript_event(
                epic_id=epic_id,
                role="system",
                content=f"Proposal confirmed. Now in {stage_display} stage.",
                stage=epic.current_stage
            )
        else:
            epic = await epic_service.reject_proposal(epic_id, user_id, body.proposal_id)
            
            await epic_service.add_transcript_event(
                epic_id=epic_id,
                role="system",
                content="Proposal rejected. Please continue the conversation.",
                stage=epic.current_stage
            )
        
        return epic_to_response(epic)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{epic_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    request: Request, 
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get full transcript for an epic"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    events = await epic_service.get_transcript(epic_id)
    
    return TranscriptResponse(
        events=[TranscriptEventResponse(
            event_id=e.event_id,
            epic_id=e.epic_id,
            role=e.role,
            content=e.content,
            stage=e.stage,
            event_metadata=e.event_metadata,
            created_at=e.created_at
        ) for e in events]
    )


@router.get("/{epic_id}/decisions", response_model=DecisionResponse)
async def get_decisions(
    request: Request, 
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get all decisions for an epic"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    decisions = await epic_service.get_decisions(epic_id)
    
    return DecisionResponse(
        decisions=[DecisionEventResponse(
            decision_id=d.decision_id,
            epic_id=d.epic_id,
            decision_type=d.decision_type,
            from_stage=d.from_stage,
            to_stage=d.to_stage,
            proposal_id=d.proposal_id,
            content_snapshot=d.content_snapshot,
            user_id=d.user_id,
            created_at=d.created_at
        ) for d in decisions]
    )


# Artifact endpoints
@router.get("/{epic_id}/artifacts", response_model=List[ArtifactResponse])
async def list_artifacts(
    request: Request, 
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """List all artifacts for an epic"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    result = await session.execute(
        select(EpicArtifact)
        .where(EpicArtifact.epic_id == epic_id)
        .order_by(EpicArtifact.created_at.desc())
    )
    artifacts = result.scalars().all()
    
    return [ArtifactResponse(
        artifact_id=a.artifact_id,
        epic_id=a.epic_id,
        artifact_type=a.artifact_type,
        title=a.title,
        description=a.description,
        acceptance_criteria=a.acceptance_criteria,
        priority=a.priority,
        created_at=a.created_at
    ) for a in artifacts]


@router.post("/{epic_id}/artifacts", response_model=ArtifactResponse)
async def create_artifact(
    request: Request, 
    epic_id: str, 
    body: ArtifactCreate,
    session: AsyncSession = Depends(get_db)
):
    """Create a new artifact under an epic"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    artifact = EpicArtifact(
        epic_id=epic_id,
        artifact_type=body.artifact_type,
        title=body.title,
        description=body.description,
        acceptance_criteria=body.acceptance_criteria,
        priority=body.priority
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    
    return ArtifactResponse(
        artifact_id=artifact.artifact_id,
        epic_id=artifact.epic_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        description=artifact.description,
        acceptance_criteria=artifact.acceptance_criteria,
        priority=artifact.priority,
        created_at=artifact.created_at
    )


@router.delete("/{epic_id}/artifacts/{artifact_id}")
async def delete_artifact(
    request: Request, 
    epic_id: str, 
    artifact_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete an artifact"""
    user_id = await get_current_user_id(request, session)
    
    epic_service = EpicService(session)
    
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    result = await session.execute(
        delete(EpicArtifact)
        .where(EpicArtifact.artifact_id == artifact_id, EpicArtifact.epic_id == epic_id)
    )
    await session.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    return {"message": "Artifact deleted"}
