"""
Magic Moment: New Initiative Generator
Paste a messy idea → get PRD + Epic + Features + Stories + 2-sprint plan
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db import get_db
from db.models import Epic, EpicSnapshot, Subscription, SubscriptionStatus
from db.feature_models import Feature
from db.user_story_models import UserStory
from services.llm_service import LLMService
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/initiative", tags=["initiative"])


class NewInitiativeRequest(BaseModel):
    idea: str  # The messy idea/problem + context
    product_name: Optional[str] = None


SYSTEM_PROMPT = """You are JarlPM, an expert Product Manager AI. Your job is to transform messy ideas into structured, actionable product plans.

Given a raw idea or problem description, you will generate a complete product initiative including:
1. A clean PRD (Product Requirements Document)
2. An Epic with clear problem statement and desired outcomes
3. Features broken down from the epic
4. User stories with acceptance criteria for each feature
5. Rough story point estimates (Fibonacci: 1, 2, 3, 5, 8, 13)
6. A 2-sprint delivery plan

Be concise but thorough. Focus on what matters for shipping.

OUTPUT FORMAT: You must respond with valid JSON only. No markdown, no explanation, just the JSON object.

{
  "product_name": "Short product name",
  "tagline": "One-line description",
  "prd": {
    "problem_statement": "Clear problem being solved",
    "target_users": "Who has this problem",
    "desired_outcome": "What success looks like",
    "key_metrics": ["metric1", "metric2"],
    "out_of_scope": ["thing1", "thing2"],
    "risks": ["risk1", "risk2"]
  },
  "epic": {
    "title": "Epic title",
    "description": "Epic description",
    "vision": "Product vision statement"
  },
  "features": [
    {
      "name": "Feature name",
      "description": "What this feature does",
      "priority": "must-have|should-have|nice-to-have",
      "stories": [
        {
          "title": "Story title",
          "persona": "As a [user type]",
          "action": "I want to [action]",
          "benefit": "So that [benefit]",
          "acceptance_criteria": ["Given X, When Y, Then Z", "..."],
          "points": 3
        }
      ]
    }
  ],
  "sprint_plan": {
    "sprint_1": {
      "goal": "Sprint 1 goal",
      "stories": ["Story title 1", "Story title 2"],
      "total_points": 13
    },
    "sprint_2": {
      "goal": "Sprint 2 goal", 
      "stories": ["Story title 3", "Story title 4"],
      "total_points": 8
    }
  },
  "total_points": 21
}"""


@router.post("/generate")
async def generate_initiative(
    request: Request,
    body: NewInitiativeRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Magic moment endpoint: Transform a messy idea into a complete initiative
    Returns streaming JSON with progress updates
    """
    user_id = await get_current_user_id(request, session)
    
    # Check subscription
    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = sub_result.scalar_one_or_none()
    
    is_active = subscription and subscription.status in [
        SubscriptionStatus.ACTIVE.value, 
        SubscriptionStatus.ACTIVE,
        "active"
    ]
    
    if not is_active:
        raise HTTPException(status_code=402, detail="Active subscription required for AI features")
    
    # Check LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="Please configure an LLM provider in Settings first")
    
    user_prompt = f"""Transform this idea into a complete product initiative:

{body.idea}

{f"Product name hint: {body.product_name}" if body.product_name else ""}

Generate a comprehensive plan with PRD, epic, features, user stories with acceptance criteria, story points, and a 2-sprint delivery plan. Remember to output ONLY valid JSON."""

    async def generate():
        # Signal start
        yield f"data: {json.dumps({'type': 'start', 'message': 'Analyzing your idea...'})}\n\n"
        
        full_response = ""
        features_started = False
        stories_started = False
        sprint_started = False
        
        try:
            # Stream the LLM response
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Generating PRD and epic...'})}\n\n"
            
            async for chunk in llm_service.generate_stream(
                user_id=user_id,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                conversation_history=None
            ):
                full_response += chunk
                
                # Send progress updates based on content
                if '"features"' in full_response and not features_started:
                    features_started = True
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Breaking down features...'})}\n\n"
                elif '"stories"' in full_response and not stories_started:
                    stories_started = True
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Writing user stories...'})}\n\n"
                elif '"sprint_plan"' in full_response and not sprint_started:
                    sprint_started = True
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Planning sprints...'})}\n\n"
            
            # Parse the response
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Finalizing plan...'})}\n\n"
            
            # Extract JSON from response (handle markdown code blocks)
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', full_response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{[\s\S]*\}', full_response)
                json_str = json_match.group(0) if json_match else full_response
            
            try:
                initiative_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse initiative JSON: {e}")
                logger.error(f"Raw response: {full_response[:500]}")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to parse AI response. Please try again.'})}\n\n"
                return
            
            # Send the complete initiative
            yield f"data: {json.dumps({'type': 'initiative', 'data': initiative_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'message': 'Initiative generated!'})}\n\n"
            
        except Exception as e:
            logger.error(f"Initiative generation failed: {e}")
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


@router.post("/save")
async def save_initiative(
    request: Request,
    initiative: dict,
    session: AsyncSession = Depends(get_db)
):
    """
    Save a generated initiative to the database
    Creates Epic, Features, and UserStories
    """
    user_id = await get_current_user_id(request, session)
    
    now = datetime.now(timezone.utc)
    
    try:
        # Create Epic
        epic_data = initiative.get("epic", {})
        prd_data = initiative.get("prd", {})
        
        epic = Epic(
            epic_id=str(uuid.uuid4()),
            user_id=user_id,
            title=initiative.get("product_name", epic_data.get("title", "New Initiative")),
            description=epic_data.get("description", ""),
            status="in_progress",
            created_at=now,
            updated_at=now
        )
        session.add(epic)
        
        # Create snapshot with PRD data
        snapshot = EpicSnapshot(
            snapshot_id=str(uuid.uuid4()),
            epic_id=epic.epic_id,
            version=1,
            problem_statement=prd_data.get("problem_statement", ""),
            vision=epic_data.get("vision", ""),
            desired_outcome=prd_data.get("desired_outcome", ""),
            target_users=prd_data.get("target_users", ""),
            out_of_scope=prd_data.get("out_of_scope", []),
            risks=prd_data.get("risks", []),
            assumptions=[],
            success_metrics=prd_data.get("key_metrics", []),
            created_at=now
        )
        session.add(snapshot)
        
        # Create Features and Stories
        features_data = initiative.get("features", [])
        created_features = []
        created_stories = []
        
        for i, feat_data in enumerate(features_data):
            feature = Feature(
                feature_id=str(uuid.uuid4()),
                epic_id=epic.epic_id,
                name=feat_data.get("name", f"Feature {i+1}"),
                description=feat_data.get("description", ""),
                priority=feat_data.get("priority", "should-have"),
                status="planned",
                order_index=i,
                created_at=now,
                updated_at=now
            )
            session.add(feature)
            created_features.append(feature)
            
            # Create stories for this feature
            for j, story_data in enumerate(feat_data.get("stories", [])):
                story = UserStory(
                    story_id=str(uuid.uuid4()),
                    feature_id=feature.feature_id,
                    title=story_data.get("title", f"Story {j+1}"),
                    persona=story_data.get("persona", ""),
                    action=story_data.get("action", ""),
                    benefit=story_data.get("benefit", ""),
                    story_text=f"As {story_data.get('persona', 'a user')}, I want to {story_data.get('action', '')} so that {story_data.get('benefit', '')}",
                    acceptance_criteria=story_data.get("acceptance_criteria", []),
                    status="draft",
                    story_points=story_data.get("points"),
                    order_index=j,
                    created_at=now,
                    updated_at=now
                )
                session.add(story)
                created_stories.append(story)
        
        await session.commit()
        
        return {
            "success": True,
            "epic_id": epic.epic_id,
            "features_created": len(created_features),
            "stories_created": len(created_stories),
            "message": f"Created epic with {len(created_features)} features and {len(created_stories)} stories"
        }
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to save initiative: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save initiative: {str(e)}")
