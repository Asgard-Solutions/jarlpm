"""
Feature Routes for JarlPM
Handles feature CRUD, refinement conversations, and lifecycle management
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import Epic, EpicStage
from db.feature_models import Feature, FeatureStage
from services.feature_service import FeatureService
from services.llm_service import LLMService
from services.prompt_service import PromptService
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["features"])


# ============================================
# Request/Response Models
# ============================================

class FeatureCreate(BaseModel):
    title: str
    description: str
    acceptance_criteria: Optional[List[str]] = None
    source: str = "manual"  # "manual" or "ai_generated"


class FeatureUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None


class FeatureChatMessage(BaseModel):
    content: str


class FeatureResponse(BaseModel):
    feature_id: str
    epic_id: str
    title: str
    description: str
    acceptance_criteria: Optional[List[str]] = None
    current_stage: str
    source: str
    priority: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None


class FeatureConversationResponse(BaseModel):
    event_id: str
    feature_id: str
    role: str
    content: str
    created_at: datetime


class GenerateFeaturesRequest(BaseModel):
    count: int = 5  # Number of features to generate


def feature_to_response(feature: Feature) -> FeatureResponse:
    """Convert Feature model to response"""
    return FeatureResponse(
        feature_id=feature.feature_id,
        epic_id=feature.epic_id,
        title=feature.title,
        description=feature.description,
        acceptance_criteria=feature.acceptance_criteria,
        current_stage=feature.current_stage,
        source=feature.source,
        priority=feature.priority,
        created_at=feature.created_at,
        updated_at=feature.updated_at,
        approved_at=feature.approved_at
    )


# ============================================
# Epic Feature Endpoints
# ============================================

@router.get("/epic/{epic_id}", response_model=List[FeatureResponse])
async def list_epic_features(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """List all features for an epic"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    
    # Verify epic ownership
    epic = await feature_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    features = await feature_service.get_epic_features(epic_id)
    return [feature_to_response(f) for f in features]


@router.post("/epic/{epic_id}", response_model=FeatureResponse, status_code=201)
async def create_feature(
    request: Request,
    epic_id: str,
    body: FeatureCreate,
    session: AsyncSession = Depends(get_db)
):
    """Create a new feature for an epic"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    
    # Verify epic ownership and is locked
    epic = await feature_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    if epic.current_stage != EpicStage.EPIC_LOCKED.value:
        raise HTTPException(status_code=400, detail="Epic must be locked before creating features")
    
    feature = await feature_service.create_feature(
        epic_id=epic_id,
        title=body.title,
        description=body.description,
        acceptance_criteria=body.acceptance_criteria,
        source=body.source
    )
    
    return feature_to_response(feature)


@router.post("/epic/{epic_id}/generate")
async def generate_features(
    request: Request,
    epic_id: str,
    body: GenerateFeaturesRequest,
    session: AsyncSession = Depends(get_db)
):
    """Generate AI feature suggestions for a locked epic (streaming)"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    # Verify epic ownership and is locked
    epic = await feature_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    if epic.current_stage != EpicStage.EPIC_LOCKED.value:
        raise HTTPException(status_code=400, detail="Epic must be locked before generating features")
    
    # Check subscription
    from services.epic_service import EpicService
    epic_service = EpicService(session)
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required")
    
    # Check LLM config
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured")
    
    # Get delivery context
    delivery_context = await prompt_service.get_delivery_context(user_id)
    delivery_context_text = prompt_service.format_delivery_context(delivery_context)
    
    # Get epic snapshot data
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from db.models import Epic as EpicModel, EpicSnapshot
    
    result = await session.execute(
        select(EpicModel)
        .options(selectinload(EpicModel.snapshot))
        .where(EpicModel.epic_id == epic_id)
    )
    epic_with_snapshot = result.scalar_one_or_none()
    snapshot = epic_with_snapshot.snapshot if epic_with_snapshot else None
    
    # Build the feature generation prompt
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping break down a locked Epic into implementable Features.

LOCKED EPIC CONTENT (IMMUTABLE):
- Title: {epic.title}
- Problem Statement: {snapshot.problem_statement if snapshot else 'N/A'}
- Desired Outcome: {snapshot.desired_outcome if snapshot else 'N/A'}
- Epic Summary: {snapshot.epic_summary if snapshot else 'N/A'}
- Acceptance Criteria:
{chr(10).join(snapshot.acceptance_criteria) if snapshot and snapshot.acceptance_criteria else 'N/A'}

YOUR TASK:
Generate {body.count} specific, implementable features that together would fully deliver this epic.

Each feature should:
1. Have a clear, specific title
2. Have a focused description (2-3 sentences)
3. Have 2-4 testable acceptance criteria
4. Be independently deliverable
5. Not overlap significantly with other features

RESPONSE FORMAT (JSON only):
[
  {{
    "title": "Feature title",
    "description": "Feature description explaining what this feature does and why",
    "acceptance_criteria": ["Criterion 1", "Criterion 2", "Criterion 3"]
  }}
]

Respond ONLY with the JSON array, no other text."""

    user_prompt = "Generate the features now."
    
    async def generate():
        full_response = ""
        try:
            async for chunk in llm_service.generate_stream(
                user_id=user_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_history=None
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Parse and return features
            import re
            json_match = re.search(r'\[[\s\S]*\]', full_response)
            if json_match:
                try:
                    features = json.loads(json_match.group(0))
                    yield f"data: {json.dumps({'type': 'features', 'features': features})}\n\n"
                except json.JSONDecodeError as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to parse features: {str(e)}'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No valid JSON found in response'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Feature generation error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================
# Individual Feature Endpoints
# ============================================

@router.get("/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    request: Request,
    feature_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get a feature by ID"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    feature = await feature_service.get_feature(feature_id)
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    # Verify ownership via epic
    epic = await feature_service.get_epic(feature.epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    return feature_to_response(feature)


@router.put("/{feature_id}", response_model=FeatureResponse)
async def update_feature(
    request: Request,
    feature_id: str,
    body: FeatureUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update a feature (only if not approved)"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    feature = await feature_service.get_feature(feature_id)
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    # Verify ownership via epic
    epic = await feature_service.get_epic(feature.epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    try:
        updated = await feature_service.update_feature(
            feature_id=feature_id,
            title=body.title,
            description=body.description,
            acceptance_criteria=body.acceptance_criteria
        )
        return feature_to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{feature_id}")
async def delete_feature(
    request: Request,
    feature_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete a feature"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    feature = await feature_service.get_feature(feature_id)
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    # Verify ownership via epic
    epic = await feature_service.get_epic(feature.epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    await feature_service.delete_feature(feature_id)
    return {"message": "Feature deleted"}


@router.post("/{feature_id}/approve", response_model=FeatureResponse)
async def approve_feature(
    request: Request,
    feature_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Approve and lock a feature"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    feature = await feature_service.get_feature(feature_id)
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    # Verify ownership via epic
    epic = await feature_service.get_epic(feature.epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    try:
        approved = await feature_service.approve_feature(feature_id)
        return feature_to_response(approved)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Feature Refinement Chat
# ============================================

@router.get("/{feature_id}/conversation", response_model=List[FeatureConversationResponse])
async def get_feature_conversation(
    request: Request,
    feature_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get conversation history for a feature"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    feature = await feature_service.get_feature(feature_id)
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    # Verify ownership via epic
    epic = await feature_service.get_epic(feature.epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    return [
        FeatureConversationResponse(
            event_id=e.event_id,
            feature_id=e.feature_id,
            role=e.role,
            content=e.content,
            created_at=e.created_at
        ) for e in feature.conversation_events
    ]


@router.post("/{feature_id}/chat")
async def chat_with_feature(
    request: Request,
    feature_id: str,
    body: FeatureChatMessage,
    session: AsyncSession = Depends(get_db)
):
    """Chat with AI to refine a feature (streaming)"""
    user_id = await get_current_user_id(request, session)
    
    feature_service = FeatureService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    feature = await feature_service.get_feature(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    # Verify ownership via epic
    epic = await feature_service.get_epic(feature.epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    if feature.current_stage == FeatureStage.APPROVED.value:
        raise HTTPException(status_code=400, detail="Cannot refine approved features")
    
    # Check subscription
    from services.epic_service import EpicService
    epic_service = EpicService(session)
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required")
    
    # Check LLM config
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured")
    
    # Move to refining stage if in draft
    if feature.current_stage == FeatureStage.DRAFT.value:
        await feature_service.start_refinement(feature_id)
    
    # Add user message to conversation
    await feature_service.add_conversation_event(
        feature_id=feature_id,
        role="user",
        content=body.content
    )
    
    # Get delivery context
    delivery_context = await prompt_service.get_delivery_context(user_id)
    delivery_context_text = prompt_service.format_delivery_context(delivery_context)
    
    # Build refinement prompt
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping refine a Feature.

CURRENT FEATURE:
- Title: {feature.title}
- Description: {feature.description}
- Acceptance Criteria:
{chr(10).join(f'  - {c}' for c in (feature.acceptance_criteria or []))}

YOUR ROLE:
- Help the user refine this feature based on their feedback
- When changes are agreed upon, provide an updated version
- Keep the feature focused and implementable

RESPONSE FORMAT:
When providing an updated feature, include it in this JSON format:

[FEATURE_UPDATE]
{{
  "title": "Updated feature title",
  "description": "Updated description",
  "acceptance_criteria": ["Criterion 1", "Criterion 2"]
}}
[/FEATURE_UPDATE]

If you're just discussing and not proposing changes yet, respond conversationally without the JSON block.

TONE: Professional, calm, direct, insightful."""

    user_prompt = body.content
    
    # Get conversation history
    history = await feature_service.get_conversation_history(feature_id, limit=10)
    
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
            
            # Check for feature update in response
            import re
            update_match = re.search(r'\[FEATURE_UPDATE\]([\s\S]*?)\[/FEATURE_UPDATE\]', full_response)
            if update_match:
                try:
                    update_json = re.search(r'\{[\s\S]*\}', update_match.group(1))
                    if update_json:
                        update_data = json.loads(update_json.group(0))
                        # Apply the update
                        await feature_service.update_feature(
                            feature_id=feature_id,
                            title=update_data.get("title"),
                            description=update_data.get("description"),
                            acceptance_criteria=update_data.get("acceptance_criteria")
                        )
                        yield f"data: {json.dumps({'type': 'feature_updated', 'update': update_data})}\n\n"
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse feature update: {e}")
            
            # Save assistant response
            await feature_service.add_conversation_event(
                feature_id=feature_id,
                role="assistant",
                content=full_response
            )
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Feature chat error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
