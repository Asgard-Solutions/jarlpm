from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import json
import logging
import re

from models.epic import (
    Epic, EpicStage, EpicCreate, EpicChatMessage, EpicConfirmProposal,
    EpicTranscriptEvent, EpicDecision, EpicArtifact, ArtifactCreate, ArtifactType,
    PendingProposal, STAGE_ORDER
)
from services.epic_service import EpicService
from services.llm_service import LLMService
from services.prompt_service import PromptService
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epics", tags=["epics"])


# Response models
class EpicResponse(BaseModel):
    epic_id: str
    title: str
    current_stage: EpicStage
    snapshot: dict
    pending_proposal: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class EpicListResponse(BaseModel):
    epics: List[EpicResponse]


class TranscriptResponse(BaseModel):
    events: List[dict]


class DecisionResponse(BaseModel):
    decisions: List[dict]


class ArtifactResponse(BaseModel):
    artifact_id: str
    epic_id: str
    artifact_type: ArtifactType
    title: str
    description: str
    acceptance_criteria: Optional[List[str]] = None
    priority: Optional[int] = None
    created_at: datetime


@router.get("", response_model=EpicListResponse)
async def list_epics(request: Request):
    """List all epics for the current user"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    epics = await epic_service.get_user_epics(user_id)
    
    return EpicListResponse(
        epics=[EpicResponse(
            epic_id=e.epic_id,
            title=e.title,
            current_stage=e.current_stage,
            snapshot=e.snapshot.model_dump() if e.snapshot else {},
            pending_proposal=e.pending_proposal.model_dump() if e.pending_proposal else None,
            created_at=e.created_at,
            updated_at=e.updated_at
        ) for e in epics]
    )


@router.post("", response_model=EpicResponse, status_code=201)
async def create_epic(request: Request, body: EpicCreate):
    """Create a new epic"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    epic = await epic_service.create_epic(user_id, body.title)
    
    # Add initial system message to transcript
    await epic_service.add_transcript_event(
        epic_id=epic.epic_id,
        role="system",
        content=f"Epic '{epic.title}' created. Starting in Problem Capture stage.",
        stage=epic.current_stage
    )
    
    return EpicResponse(
        epic_id=epic.epic_id,
        title=epic.title,
        current_stage=epic.current_stage,
        snapshot=epic.snapshot.model_dump() if epic.snapshot else {},
        pending_proposal=None,
        created_at=epic.created_at,
        updated_at=epic.updated_at
    )


@router.get("/{epic_id}", response_model=EpicResponse)
async def get_epic(request: Request, epic_id: str):
    """Get an epic by ID"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    epic = await epic_service.get_epic(epic_id, user_id)
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    return EpicResponse(
        epic_id=epic.epic_id,
        title=epic.title,
        current_stage=epic.current_stage,
        snapshot=epic.snapshot.model_dump() if epic.snapshot else {},
        pending_proposal=epic.pending_proposal.model_dump() if epic.pending_proposal else None,
        created_at=epic.created_at,
        updated_at=epic.updated_at
    )


@router.delete("/{epic_id}")
async def delete_epic(request: Request, epic_id: str):
    """Delete an epic (requires explicit confirmation - handled by frontend)"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    success = await epic_service.delete_epic(epic_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    return {"message": "Epic deleted"}


@router.post("/{epic_id}/chat")
async def chat_with_epic(request: Request, epic_id: str, body: EpicChatMessage):
    """Chat with AI about the epic (streaming response)"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    llm_service = LLMService(db)
    prompt_service = PromptService(db)
    
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
    
    # Check if epic is locked
    if epic.current_stage == EpicStage.EPIC_LOCKED:
        # Still allow chat but make it clear the epic is locked
        pass
    
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
    
    # Render prompts
    system_prompt, user_prompt = prompt_service.render_prompt(
        template,
        epic.title,
        body.content,
        epic.snapshot
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
                conversation_history=history[:-1] if history else None  # Exclude last user message
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Check for proposal in response
            proposal = llm_service.extract_proposal(full_response)
            if proposal:
                # Determine target stage based on proposal type
                target_stage = None
                field = None
                
                if proposal["type"] == "PROBLEM_STATEMENT" and epic.current_stage == EpicStage.PROBLEM_CAPTURE:
                    target_stage = EpicStage.PROBLEM_CONFIRMED
                    field = "problem_statement"
                elif proposal["type"] == "DESIRED_OUTCOME" and epic.current_stage == EpicStage.OUTCOME_CAPTURE:
                    target_stage = EpicStage.OUTCOME_CONFIRMED
                    field = "desired_outcome"
                elif proposal["type"] == "EPIC_FINAL" and epic.current_stage == EpicStage.EPIC_DRAFTED:
                    target_stage = EpicStage.EPIC_LOCKED
                    field = "epic_final"
                
                if target_stage and field:
                    # Create pending proposal
                    pending = await epic_service.set_pending_proposal(
                        epic_id=epic_id,
                        user_id=user_id,
                        field=field,
                        content=proposal["content"],
                        target_stage=target_stage
                    )
                    yield f"data: {json.dumps({'type': 'proposal', 'proposal_id': pending.proposal_id, 'field': field, 'content': proposal['content'], 'target_stage': target_stage.value})}\n\n"
            
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
async def confirm_proposal(request: Request, epic_id: str, body: EpicConfirmProposal):
    """Confirm or reject a pending proposal"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    
    try:
        if body.confirmed:
            epic = await epic_service.confirm_proposal(epic_id, user_id, body.proposal_id)
            
            # Add confirmation to transcript
            await epic_service.add_transcript_event(
                epic_id=epic_id,
                role="system",
                content=f"Proposal confirmed. Advanced to {epic.current_stage.value} stage.",
                stage=epic.current_stage
            )
        else:
            epic = await epic_service.reject_proposal(epic_id, user_id, body.proposal_id)
            
            # Add rejection to transcript
            await epic_service.add_transcript_event(
                epic_id=epic_id,
                role="system",
                content="Proposal rejected. Please continue the conversation.",
                stage=epic.current_stage
            )
        
        return EpicResponse(
            epic_id=epic.epic_id,
            title=epic.title,
            current_stage=epic.current_stage,
            snapshot=epic.snapshot.model_dump() if epic.snapshot else {},
            pending_proposal=epic.pending_proposal.model_dump() if epic.pending_proposal else None,
            created_at=epic.created_at,
            updated_at=epic.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{epic_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(request: Request, epic_id: str):
    """Get full transcript for an epic"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    
    # Verify ownership
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    events = await epic_service.get_transcript(epic_id)
    
    return TranscriptResponse(
        events=[e.model_dump() for e in events]
    )


@router.get("/{epic_id}/decisions", response_model=DecisionResponse)
async def get_decisions(request: Request, epic_id: str):
    """Get all decisions for an epic"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    
    # Verify ownership
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    decisions = await epic_service.get_decisions(epic_id)
    
    return DecisionResponse(
        decisions=[d.model_dump() for d in decisions]
    )


# Artifact endpoints
@router.get("/{epic_id}/artifacts", response_model=List[ArtifactResponse])
async def list_artifacts(request: Request, epic_id: str):
    """List all artifacts for an epic"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    
    # Verify ownership
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    cursor = db.epic_artifacts.find(
        {"epic_id": epic_id},
        {"_id": 0}
    ).sort("created_at", -1)
    artifacts = await cursor.to_list(1000)
    
    return [ArtifactResponse(**a) for a in artifacts]


@router.post("/{epic_id}/artifacts", response_model=ArtifactResponse)
async def create_artifact(request: Request, epic_id: str, body: ArtifactCreate):
    """Create a new artifact under an epic"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    
    # Verify ownership
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    import uuid
    artifact_doc = {
        "artifact_id": f"art_{uuid.uuid4().hex[:12]}",
        "epic_id": epic_id,
        "artifact_type": body.artifact_type.value,
        "title": body.title,
        "description": body.description,
        "acceptance_criteria": body.acceptance_criteria,
        "priority": body.priority,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.epic_artifacts.insert_one(artifact_doc)
    
    return ArtifactResponse(**artifact_doc)


@router.delete("/{epic_id}/artifacts/{artifact_id}")
async def delete_artifact(request: Request, epic_id: str, artifact_id: str):
    """Delete an artifact"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    epic_service = EpicService(db)
    
    # Verify ownership
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    result = await db.epic_artifacts.delete_one(
        {"artifact_id": artifact_id, "epic_id": epic_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    return {"message": "Artifact deleted"}
