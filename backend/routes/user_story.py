"""
User Story Routes for JarlPM
Handles user story CRUD, refinement conversations, and lifecycle management
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
from db.feature_models import Feature, FeatureStage
from db.user_story_models import UserStory, UserStoryStage
from services.user_story_service import UserStoryService
from services.llm_service import LLMService
from services.prompt_service import PromptService
from services.lock_policy_service import lock_policy
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stories", tags=["user-stories"])


# ============================================
# Request/Response Models
# ============================================

class UserStoryCreate(BaseModel):
    persona: str
    action: str
    benefit: str
    acceptance_criteria: Optional[List[str]] = None
    story_points: Optional[int] = None
    source: str = "manual"


class UserStoryUpdate(BaseModel):
    persona: Optional[str] = None
    action: Optional[str] = None
    benefit: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    story_points: Optional[int] = None


class FeatureStoryChatMessage(BaseModel):
    content: str


class UserStoryResponse(BaseModel):
    story_id: str
    feature_id: Optional[str] = None
    user_id: Optional[str] = None
    title: Optional[str] = None
    persona: str
    action: str
    benefit: str
    story_text: str
    acceptance_criteria: Optional[List[str]] = None
    current_stage: str
    source: str
    story_points: Optional[int] = None
    priority: Optional[int] = None
    is_standalone: bool = False
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None


class StoryConversationResponse(BaseModel):
    event_id: str
    story_id: str
    role: str
    content: str
    created_at: datetime


class GenerateStoriesRequest(BaseModel):
    count: int = 5  # Target number of stories to generate


# Standalone story models
class StandaloneStoryCreate(BaseModel):
    title: str
    persona: str
    action: str
    benefit: str
    acceptance_criteria: Optional[List[str]] = None
    story_points: Optional[int] = None
    source: str = "manual"


class StandaloneStoryProposal(BaseModel):
    title: str
    persona: str
    action: str
    benefit: str
    acceptance_criteria: Optional[List[str]] = None
    story_points: Optional[int] = None


class StoryChatMessage(BaseModel):
    content: str
    conversation_history: Optional[List[dict]] = []


def story_to_response(story: UserStory) -> UserStoryResponse:
    """Convert UserStory model to response"""
    return UserStoryResponse(
        story_id=story.story_id,
        feature_id=story.feature_id,
        user_id=story.user_id,
        title=story.title,
        persona=story.persona,
        action=story.action,
        benefit=story.benefit,
        story_text=story.story_text,
        acceptance_criteria=story.acceptance_criteria,
        current_stage=story.current_stage,
        source=story.source,
        story_points=story.story_points,
        priority=story.priority,
        is_standalone=story.is_standalone,
        created_at=story.created_at,
        updated_at=story.updated_at,
        approved_at=story.approved_at
    )


# ============================================
# Feature Story Endpoints
# ============================================

@router.get("/feature/{feature_id}", response_model=List[UserStoryResponse])
async def list_feature_stories(
    request: Request,
    feature_id: str,
    session: AsyncSession = Depends(get_db)
):
    """List all user stories for a feature"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    
    # Verify feature ownership via epic
    epic = await story_service.get_epic_for_feature(feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    stories = await story_service.get_feature_stories(feature_id)
    return [story_to_response(s) for s in stories]


@router.post("/feature/{feature_id}", response_model=UserStoryResponse, status_code=201)
async def create_story(
    request: Request,
    feature_id: str,
    body: UserStoryCreate,
    session: AsyncSession = Depends(get_db)
):
    """Create a new user story for a feature"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    
    # Verify feature ownership and is approved
    epic = await story_service.get_epic_for_feature(feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    feature = await story_service.get_feature(feature_id)
    if feature.current_stage != FeatureStage.APPROVED.value:
        raise HTTPException(status_code=400, detail="Feature must be approved before creating user stories")
    
    story = await story_service.create_user_story(
        feature_id=feature_id,
        persona=body.persona,
        action=body.action,
        benefit=body.benefit,
        acceptance_criteria=body.acceptance_criteria,
        story_points=body.story_points,
        source=body.source
    )
    
    return story_to_response(story)


@router.post("/feature/{feature_id}/generate")
async def generate_stories(
    request: Request,
    feature_id: str,
    body: GenerateStoriesRequest,
    session: AsyncSession = Depends(get_db)
):
    """Generate AI user story suggestions for an approved feature (streaming)"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    # Verify feature ownership and is approved
    epic = await story_service.get_epic_for_feature(feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    feature = await story_service.get_feature(feature_id)
    if feature.current_stage != FeatureStage.APPROVED.value:
        raise HTTPException(status_code=400, detail="Feature must be approved before generating user stories")
    
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
    
    # Get epic snapshot for context
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from db.models import Epic as EpicModel, EpicSnapshot
    
    result = await session.execute(
        select(EpicModel)
        .options(selectinload(EpicModel.snapshot))
        .where(EpicModel.epic_id == epic.epic_id)
    )
    epic_with_snapshot = result.scalar_one_or_none()
    snapshot = epic_with_snapshot.snapshot if epic_with_snapshot else None
    
    # Build the user story generation prompt
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping break down an approved Feature into User Stories.

EPIC CONTEXT (for reference):
- Title: {epic.title}
- Problem: {snapshot.problem_statement if snapshot else 'N/A'}
- Outcome: {snapshot.desired_outcome if snapshot else 'N/A'}

APPROVED FEATURE TO BREAK DOWN:
- Title: {feature.title}
- Description: {feature.description}
- Feature Acceptance Criteria:
{chr(10).join(f'  - {c}' for c in (feature.acceptance_criteria or ['N/A']))}

YOUR TASK:
Generate user stories that together accomplish this feature. Each story should:
1. Be completable within a single sprint
2. Follow the standard format: "As a [persona], I want to [action] so that [benefit]"
3. Have clear Given/When/Then acceptance criteria
4. Focus on WHAT the user needs, not HOW to implement it
5. Be independently testable

IMPORTANT GUIDELINES:
- User stories describe the problem and desired outcome, NOT implementation details
- Each story should deliver tangible user value
- Stories should be small enough to complete in one sprint
- Acceptance criteria must be testable and specific

RESPONSE FORMAT (JSON only):
[
  {{
    "persona": "the user role (e.g., 'logged-in user', 'admin', 'guest')",
    "action": "what they want to do (verb phrase)",
    "benefit": "why they want to do it (the value)",
    "acceptance_criteria": [
      "Given [context], When [action], Then [expected result]",
      "Given [context], When [action], Then [expected result]"
    ],
    "story_points": 3
  }}
]

Story points should be 1, 2, 3, 5, or 8 based on complexity.

Respond ONLY with the JSON array, no other text."""

    user_prompt = "Generate user stories to accomplish this feature. Aim for stories that are each completable in one sprint."
    
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
            
            # Parse and return stories
            import re
            json_match = re.search(r'\[[\s\S]*\]', full_response)
            if json_match:
                try:
                    stories = json.loads(json_match.group(0))
                    yield f"data: {json.dumps({'type': 'stories', 'stories': stories})}\n\n"
                except json.JSONDecodeError as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to parse stories: {str(e)}'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No valid JSON found in response'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Story generation error: {e}")
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
# Individual Story Endpoints
# ============================================

@router.get("/{story_id}", response_model=UserStoryResponse)
async def get_story(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get a user story by ID"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_user_story(story_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Verify ownership via feature -> epic
    epic = await story_service.get_epic_for_feature(story.feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="User story not found")
    
    return story_to_response(story)


@router.put("/{story_id}", response_model=UserStoryResponse)
async def update_story(
    request: Request,
    story_id: str,
    body: UserStoryUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update a user story (only if not approved and epic not locked)"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_user_story(story_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Verify ownership via feature -> epic
    epic = await story_service.get_epic_for_feature(story.feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Check lock policy
    epic_status = lock_policy.get_epic_status(epic.current_stage)
    policy_result = lock_policy.can_edit_story(epic_status)
    if not policy_result.allowed:
        raise HTTPException(status_code=409, detail=policy_result.reason)
    
    try:
        updated = await story_service.update_user_story(
            story_id=story_id,
            persona=body.persona,
            action=body.action,
            benefit=body.benefit,
            acceptance_criteria=body.acceptance_criteria,
            story_points=body.story_points
        )
        return story_to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{story_id}")
async def delete_story(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete a user story (only if epic not locked)"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_user_story(story_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Verify ownership via feature -> epic
    epic = await story_service.get_epic_for_feature(story.feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Check lock policy
    epic_status = lock_policy.get_epic_status(epic.current_stage)
    policy_result = lock_policy.can_delete_story(epic_status)
    if not policy_result.allowed:
        raise HTTPException(status_code=409, detail=policy_result.reason)
    
    await story_service.delete_user_story(story_id)
    return {"message": "User story deleted"}


@router.post("/{story_id}/approve", response_model=UserStoryResponse)
async def approve_story(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Approve and lock a user story"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_user_story(story_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Verify ownership via feature -> epic
    epic = await story_service.get_epic_for_feature(story.feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="User story not found")
    
    try:
        approved = await story_service.approve_user_story(story_id)
        return story_to_response(approved)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Story Refinement Chat
# ============================================

@router.get("/{story_id}/conversation", response_model=List[StoryConversationResponse])
async def get_story_conversation(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get conversation history for a user story"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_user_story(story_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Verify ownership via feature -> epic
    epic = await story_service.get_epic_for_feature(story.feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="User story not found")
    
    return [
        StoryConversationResponse(
            event_id=e.event_id,
            story_id=e.story_id,
            role=e.role,
            content=e.content,
            created_at=e.created_at
        ) for e in story.conversation_events
    ]


@router.post("/{story_id}/chat")
async def chat_with_story(
    request: Request,
    story_id: str,
    body: StoryChatMessage,
    session: AsyncSession = Depends(get_db)
):
    """Chat with AI to refine a user story (streaming)"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    story = await story_service.get_user_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Verify ownership via feature -> epic
    epic = await story_service.get_epic_for_feature(story.feature_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="User story not found")
    
    if story.current_stage == UserStoryStage.APPROVED.value:
        raise HTTPException(status_code=400, detail="Cannot refine approved user stories")
    
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
    if story.current_stage == UserStoryStage.DRAFT.value:
        await story_service.start_refinement(story_id)
    
    # Add user message to conversation
    await story_service.add_conversation_event(
        story_id=story_id,
        role="user",
        content=body.content
    )
    
    # Get delivery context
    delivery_context = await prompt_service.get_delivery_context(user_id)
    delivery_context_text = prompt_service.format_delivery_context(delivery_context)
    
    # Build refinement prompt
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping refine a User Story.

CURRENT USER STORY:
- Persona: {story.persona}
- Action: {story.action}
- Benefit: {story.benefit}
- Full Text: "{story.story_text}"
- Acceptance Criteria:
{chr(10).join(f'  - {c}' for c in (story.acceptance_criteria or []))}
- Story Points: {story.story_points or 'Not estimated'}

YOUR ROLE:
- Help the user refine this story based on their feedback
- Keep the standard format: "As a [persona], I want to [action] so that [benefit]"
- Ensure acceptance criteria use Given/When/Then format
- Keep the story focused on user value, not implementation
- Ensure it's completable in one sprint

RESPONSE FORMAT:
When providing an updated story, include it in this JSON format:

[STORY_UPDATE]
{{
  "persona": "the user role",
  "action": "what they want to do",
  "benefit": "why they want to do it",
  "acceptance_criteria": ["Given..., When..., Then...", "..."],
  "story_points": 3
}}
[/STORY_UPDATE]

If you're just discussing and not proposing changes yet, respond conversationally without the JSON block.

TONE: Professional, calm, direct, insightful."""

    user_prompt = body.content
    
    # Get conversation history
    history = await story_service.get_conversation_history(story_id, limit=10)
    
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
            
            # Check for story update in response
            import re
            update_match = re.search(r'\[STORY_UPDATE\]([\s\S]*?)\[/STORY_UPDATE\]', full_response)
            if update_match:
                try:
                    update_json = re.search(r'\{[\s\S]*\}', update_match.group(1))
                    if update_json:
                        update_data = json.loads(update_json.group(0))
                        # Apply the update
                        await story_service.update_user_story(
                            story_id=story_id,
                            persona=update_data.get("persona"),
                            action=update_data.get("action"),
                            benefit=update_data.get("benefit"),
                            acceptance_criteria=update_data.get("acceptance_criteria"),
                            story_points=update_data.get("story_points")
                        )
                        yield f"data: {json.dumps({'type': 'story_updated', 'update': update_data})}\n\n"
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse story update: {e}")
            
            # Save assistant response
            await story_service.add_conversation_event(
                story_id=story_id,
                role="assistant",
                content=full_response
            )
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Story chat error: {e}")
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
# STANDALONE STORY ENDPOINTS
# ============================================

@router.get("/standalone", response_model=List[UserStoryResponse])
async def list_standalone_stories(
    request: Request,
    stage: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """List all standalone user stories for the current user"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    stories = await story_service.get_all_stories_for_user(user_id, standalone_only=True, stage=stage)
    
    return [story_to_response(s) for s in stories]


@router.post("/standalone", response_model=UserStoryResponse, status_code=201)
async def create_standalone_story(
    request: Request,
    body: StandaloneStoryCreate,
    session: AsyncSession = Depends(get_db)
):
    """Create a standalone user story (not linked to a feature)"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    
    story = await story_service.create_standalone_story(
        user_id=user_id,
        title=body.title,
        persona=body.persona,
        action=body.action,
        benefit=body.benefit,
        acceptance_criteria=body.acceptance_criteria,
        story_points=body.story_points,
        source=body.source
    )
    
    logger.info(f"Created standalone story {story.story_id} for user {user_id}")
    return story_to_response(story)


@router.get("/standalone/{story_id}", response_model=UserStoryResponse)
async def get_standalone_story(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get a standalone user story by ID"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_story_for_user(story_id, user_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    if not story.is_standalone:
        raise HTTPException(status_code=400, detail="This is not a standalone story")
    
    return story_to_response(story)


@router.put("/standalone/{story_id}", response_model=UserStoryResponse)
async def update_standalone_story(
    request: Request,
    story_id: str,
    body: UserStoryUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update a standalone user story (only if not approved)"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_story_for_user(story_id, user_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    if not story.is_standalone:
        raise HTTPException(status_code=400, detail="This is not a standalone story")
    
    if story.current_stage == UserStoryStage.APPROVED.value:
        raise HTTPException(status_code=409, detail="Cannot update approved stories")
    
    try:
        updated = await story_service.update_user_story(
            story_id=story_id,
            persona=body.persona,
            action=body.action,
            benefit=body.benefit,
            acceptance_criteria=body.acceptance_criteria,
            story_points=body.story_points
        )
        return story_to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/standalone/{story_id}")
async def delete_standalone_story(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete a standalone user story"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_story_for_user(story_id, user_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    if not story.is_standalone:
        raise HTTPException(status_code=400, detail="This is not a standalone story")
    
    if story.current_stage == UserStoryStage.APPROVED.value:
        raise HTTPException(status_code=409, detail="Cannot delete approved stories")
    
    await story_service.delete_user_story(story_id)
    return {"message": "User story deleted"}


@router.post("/standalone/{story_id}/approve", response_model=UserStoryResponse)
async def approve_standalone_story(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Approve and lock a standalone user story"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    story = await story_service.get_story_for_user(story_id, user_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    if not story.is_standalone:
        raise HTTPException(status_code=400, detail="This is not a standalone story")
    
    try:
        approved = await story_service.approve_user_story(story_id)
        return story_to_response(approved)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/standalone/{story_id}/chat")
async def chat_with_standalone_story(
    request: Request,
    story_id: str,
    body: StoryChatMessage,
    session: AsyncSession = Depends(get_db)
):
    """Chat with AI to refine a standalone user story (streaming)"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    story = await story_service.get_story_for_user(story_id, user_id)
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    if not story.is_standalone:
        raise HTTPException(status_code=400, detail="This is not a standalone story")
    
    if story.current_stage == UserStoryStage.APPROVED.value:
        raise HTTPException(status_code=400, detail="Cannot refine approved user stories")
    
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
    if story.current_stage == UserStoryStage.DRAFT.value:
        await story_service.start_refinement(story_id)
    
    # Add user message to conversation
    await story_service.add_conversation_event(
        story_id=story_id,
        role="user",
        content=body.content
    )
    
    # Get delivery context
    delivery_context = await prompt_service.get_delivery_context(user_id)
    delivery_context_text = prompt_service.format_delivery_context(delivery_context)
    
    # Build refinement prompt for standalone story
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping refine a standalone User Story.

CURRENT USER STORY:
- Title: {story.title or 'Untitled'}
- Persona: {story.persona}
- Action: {story.action}
- Benefit: {story.benefit}
- Full Text: "{story.story_text}"
- Acceptance Criteria:
{chr(10).join(f'  - {c}' for c in (story.acceptance_criteria or []))}
- Story Points: {story.story_points or 'Not estimated'}

YOUR ROLE:
- Help the user refine this story based on their feedback
- Keep the standard format: "As a [persona], I want to [action] so that [benefit]"
- Ensure acceptance criteria use Given/When/Then format
- Keep the story focused on user value, not implementation
- Ensure it's completable in one sprint

RESPONSE FORMAT:
When providing an updated story, include it in this JSON format:

[STORY_UPDATE]
{{
  "title": "short descriptive title",
  "persona": "the user role",
  "action": "what they want to do",
  "benefit": "why they want to do it",
  "acceptance_criteria": ["Given..., When..., Then...", "..."],
  "story_points": 3
}}
[/STORY_UPDATE]

If you're just discussing and not proposing changes yet, respond conversationally without the JSON block.

TONE: Professional, calm, direct, insightful."""

    user_prompt = body.content
    
    # Get conversation history
    history = await story_service.get_conversation_history(story_id, limit=10)
    
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
            
            # Check for story update in response
            import re
            update_match = re.search(r'\[STORY_UPDATE\]([\s\S]*?)\[/STORY_UPDATE\]', full_response)
            if update_match:
                try:
                    update_json = re.search(r'\{[\s\S]*\}', update_match.group(1))
                    if update_json:
                        update_data = json.loads(update_json.group(0))
                        # Apply the update
                        await story_service.update_user_story(
                            story_id=story_id,
                            persona=update_data.get("persona"),
                            action=update_data.get("action"),
                            benefit=update_data.get("benefit"),
                            acceptance_criteria=update_data.get("acceptance_criteria"),
                            story_points=update_data.get("story_points")
                        )
                        yield f"data: {json.dumps({'type': 'story_updated', 'update': update_data})}\n\n"
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse story update: {e}")
            
            # Save assistant response
            await story_service.add_conversation_event(
                story_id=story_id,
                role="assistant",
                content=full_response
            )
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Standalone story chat error: {e}")
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
# AI-ASSISTED STANDALONE STORY CREATION
# ============================================

@router.post("/ai/chat")
async def ai_story_chat(
    request: Request,
    body: StoryChatMessage,
    session: AsyncSession = Depends(get_db)
):
    """AI-assisted standalone story creation via conversation (streaming)"""
    user_id = await get_current_user_id(request, session)
    
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    # Check subscription
    from services.epic_service import EpicService
    epic_service = EpicService(session)
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required")
    
    # Get user's active LLM config
    config = await llm_service.get_user_llm_config(user_id)
    if not config:
        raise HTTPException(status_code=400, detail="No LLM provider configured")
    
    # Get delivery context
    delivery_context = await prompt_service.get_delivery_context(user_id)
    delivery_context_text = prompt_service.format_delivery_context(delivery_context)
    
    # Build conversation context
    conversation = body.conversation_history or []
    
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping users create well-structured, actionable user stories through a friendly conversation.

CONVERSATION FLOW:
1. First, ask about the USER ROLE or PERSONA - who is the user in this story?
2. Then ask about the ACTION - what do they want to accomplish?
3. Ask about the BENEFIT - why do they want to do this? What value does it provide?
4. Ask about ACCEPTANCE CRITERIA - how will we know when this story is done?
5. Optionally discuss STORY POINTS (1, 2, 3, 5, or 8) based on complexity

IMPORTANT RULES:
- Ask ONE question at a time to keep the conversation focused
- Be conversational and helpful, not robotic
- If the user provides multiple pieces of information, acknowledge them
- Guide users to focus on WHAT (user value) not HOW (implementation)
- Stories should be completable within a single sprint
- Acceptance criteria should use Given/When/Then format

WHEN READY TO PROPOSE:
After gathering sufficient information (persona, action, benefit, at least 2 acceptance criteria), respond with a JSON block:
```json
{{
  "proposal": {{
    "title": "Brief descriptive title for the story",
    "persona": "the user role (e.g., 'logged-in user', 'admin', 'guest')",
    "action": "what they want to do (verb phrase)",
    "benefit": "why they want to do it (the value)",
    "acceptance_criteria": [
      "Given [context], When [action], Then [expected result]",
      "Given [context], When [action], Then [expected result]"
    ],
    "story_points": 3
  }}
}}
```

Story points guide:
- 1: Trivial change, quick fix
- 2: Small, well-understood task
- 3: Medium complexity, typical story
- 5: Larger story, some unknowns
- 8: Complex story, should consider splitting

Start by asking about the user or persona for this story."""

    # Format conversation for LLM
    formatted_history = []
    for msg in conversation:
        formatted_history.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    
    async def generate():
        full_response = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt=system_prompt,
            user_prompt=body.content,
            conversation_history=formatted_history if formatted_history else None
        ):
            full_response += chunk
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        
        # Check if response contains a proposal
        proposal = None
        is_complete = False
        
        # Try to extract JSON proposal from response
        try:
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', full_response, re.DOTALL)
            if json_match:
                proposal_data = json.loads(json_match.group(1))
                if "proposal" in proposal_data:
                    proposal = proposal_data["proposal"]
                    is_complete = True
        except (json.JSONDecodeError, KeyError):
            pass
        
        yield f"data: {json.dumps({'type': 'done', 'proposal': proposal, 'is_complete': is_complete})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/ai/create-from-proposal", response_model=UserStoryResponse)
async def create_story_from_proposal(
    request: Request,
    body: StandaloneStoryProposal,
    session: AsyncSession = Depends(get_db)
):
    """Create a standalone story from an AI-generated proposal"""
    user_id = await get_current_user_id(request, session)
    
    story_service = UserStoryService(session)
    
    story = await story_service.create_standalone_story(
        user_id=user_id,
        title=body.title,
        persona=body.persona,
        action=body.action,
        benefit=body.benefit,
        acceptance_criteria=body.acceptance_criteria,
        story_points=body.story_points,
        source="ai_generated"
    )
    
    logger.info(f"Created standalone story from AI proposal: {story.story_id} for user {user_id}")
    return story_to_response(story)
