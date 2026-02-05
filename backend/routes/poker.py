"""
AI-Powered Poker Planning Routes for JarlPM
Simulates a team of AI personas to estimate story points
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db import get_db
from db.models import Epic, EpicSnapshot
from db.user_story_models import UserStory, PokerEstimateSession, PokerPersonaEstimate
from services.llm_service import LLMService
from services.prompt_service import PromptService
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/poker", tags=["poker-planning"])


# ============================================
# AI Personas for Estimation
# ============================================

AI_PERSONAS = [
    {
        "id": "sr_developer",
        "name": "Sarah",
        "role": "Senior Developer",
        "avatar": "👩‍💻",
        "perspective": """You are Sarah, a Senior Developer with 10+ years of experience.
You focus on:
- Technical complexity and architecture implications
- Code quality, testing requirements, and tech debt
- Integration points and potential blockers
- Security considerations
You tend to be realistic about estimates, accounting for code review, testing, and edge cases."""
    },
    {
        "id": "jr_developer",
        "name": "Alex",
        "role": "Junior Developer",
        "avatar": "👨‍💻",
        "perspective": """You are Alex, a Junior Developer with 2 years of experience.
You focus on:
- Learning curve and documentation needs
- Clarity of requirements
- Available examples and patterns to follow
- Time needed to understand existing code
You tend to estimate slightly higher due to your awareness of unknowns and learning time."""
    },
    {
        "id": "qa_engineer",
        "name": "Maya",
        "role": "QA Engineer",
        "avatar": "🧪",
        "perspective": """You are Maya, a QA Engineer with 7 years of experience.
You focus on:
- Test coverage requirements (unit, integration, e2e)
- Edge cases and error scenarios
- Accessibility and cross-browser testing
- Regression risk and test maintenance
You consider the full testing pyramid when estimating."""
    },
    {
        "id": "devops_engineer",
        "name": "Jordan",
        "role": "DevOps Engineer",
        "avatar": "🔧",
        "perspective": """You are Jordan, a DevOps/Infrastructure Engineer with 6 years of experience.
You focus on:
- Deployment complexity and CI/CD changes
- Infrastructure requirements and scaling
- Monitoring, logging, and observability
- Security scanning and compliance
You consider operational aspects and deployment risks."""
    },
    {
        "id": "ux_designer",
        "name": "Riley",
        "role": "UX/UI Designer",
        "avatar": "🎨",
        "perspective": """You are Riley, a UX/UI Designer with 5 years of experience.
You focus on:
- User flow complexity and consistency
- Accessibility requirements (WCAG compliance)
- Responsive design considerations
- Design system alignment and component reuse
- User testing and iteration needs
You consider the full user experience, not just visual implementation."""
    }
]


class EstimateStoryRequest(BaseModel):
    story_id: str


class EstimateResponse(BaseModel):
    persona_id: str
    name: str
    role: str
    avatar: str
    estimate: int
    reasoning: str
    confidence: str  # "low", "medium", "high"


# ============================================
# Endpoints
# ============================================

@router.get("/personas")
async def get_ai_personas():
    """Get list of AI personas available for estimation"""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "role": p["role"],
            "avatar": p["avatar"]
        }
        for p in AI_PERSONAS
    ]


@router.post("/estimate")
async def estimate_story(
    request: Request,
    body: EstimateStoryRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Get AI estimates from all personas for a user story (streaming)
    Returns estimates from each AI persona with reasoning
    """
    user_id = await get_current_user_id(request, session)
    
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    # Get the story
    result = await session.execute(
        select(UserStory).where(UserStory.story_id == body.story_id)
    )
    story = result.scalar_one_or_none()
    
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
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
    
    # Build story context
    story_context = f"""
USER STORY TO ESTIMATE:
- Title: {story.title or 'Untitled'}
- As a: {story.persona}
- I want to: {story.action}
- So that: {story.benefit}
- Full story: "{story.story_text}"
- Acceptance Criteria:
{chr(10).join(f'  - {c}' for c in (story.acceptance_criteria or ['No criteria specified']))}
"""
    
    async def generate():
        # Start the estimation process
        yield f"data: {json.dumps({'type': 'start', 'total_personas': len(AI_PERSONAS)})}\n\n"
        
        estimates = []
        
        for persona in AI_PERSONAS:
            # Signal which persona is estimating
            yield f"data: {json.dumps({'type': 'persona_start', 'persona': {'id': persona['id'], 'name': persona['name'], 'role': persona['role'], 'avatar': persona['avatar']}})}\n\n"
            
            # Build persona-specific prompt
            system_prompt = f"""{delivery_context_text}

{persona['perspective']}

FIBONACCI SCALE FOR ESTIMATION:
- 1: Trivial - A few hours of work, very well understood
- 2: Small - About a day of work, minimal unknowns
- 3: Medium - 2-3 days of work, some complexity
- 5: Large - About a week of work, moderate complexity and unknowns
- 8: Very Large - 1-2 weeks, significant complexity, consider splitting
- 13: Huge - More than 2 weeks, high risk, should definitely be split

IMPORTANT RULES:
- Maximum estimate is 13 (stories larger than this should be split)
- Consider your specific role's perspective and concerns
- Be specific about WHY you chose this estimate
- Express your confidence level based on clarity of requirements

RESPONSE FORMAT (JSON only):
{{
  "estimate": <number from 1,2,3,5,8,13>,
  "reasoning": "<2-3 sentences explaining your estimate from your role's perspective>",
  "confidence": "<low|medium|high>"
}}

Respond ONLY with the JSON, no other text."""

            user_prompt = f"""Please estimate the following user story from your perspective as a {persona['role']}:

{story_context}

Provide your estimate in the specified JSON format."""

            try:
                full_response = ""
                async for chunk in llm_service.generate_stream(
                    user_id=user_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    conversation_history=None
                ):
                    full_response += chunk
                
                # Parse the response
                import re
                json_match = re.search(r'\{[\s\S]*?\}', full_response)
                if json_match:
                    try:
                        estimate_data = json.loads(json_match.group(0))
                        
                        # Validate and clamp estimate
                        estimate = estimate_data.get("estimate", 3)
                        if estimate not in [1, 2, 3, 5, 8, 13]:
                            # Find closest valid Fibonacci number
                            valid = [1, 2, 3, 5, 8, 13]
                            estimate = min(valid, key=lambda x: abs(x - estimate))
                        
                        persona_estimate = {
                            "persona_id": persona["id"],
                            "name": persona["name"],
                            "role": persona["role"],
                            "avatar": persona["avatar"],
                            "estimate": estimate,
                            "reasoning": estimate_data.get("reasoning", "No reasoning provided"),
                            "confidence": estimate_data.get("confidence", "medium")
                        }
                        estimates.append(persona_estimate)
                        
                        yield f"data: {json.dumps({'type': 'persona_estimate', 'estimate': persona_estimate})}\n\n"
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse estimate from {persona['name']}: {e}")
                        yield f"data: {json.dumps({'type': 'persona_error', 'persona_id': persona['id'], 'error': 'Failed to parse response'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'persona_error', 'persona_id': persona['id'], 'error': 'No valid JSON in response'})}\n\n"
                    
            except Exception as e:
                logger.error(f"Error getting estimate from {persona['name']}: {e}")
                yield f"data: {json.dumps({'type': 'persona_error', 'persona_id': persona['id'], 'error': str(e)})}\n\n"
        
        # Calculate summary statistics and save session
        session_id = None
        if estimates:
            valid_estimates = [e["estimate"] for e in estimates if isinstance(e["estimate"], int)]
            if valid_estimates:
                avg = sum(valid_estimates) / len(valid_estimates)
                # Find suggested (mode or closest to median)
                from collections import Counter
                vote_counts = Counter(valid_estimates)
                most_common = vote_counts.most_common(1)[0][0]
                
                # Calculate variance to determine consensus
                variance = sum((e - avg) ** 2 for e in valid_estimates) / len(valid_estimates)
                consensus = "high" if variance < 2 else "medium" if variance < 5 else "low"
                
                # Save session and estimates to database
                try:
                    poker_session = PokerEstimateSession(
                        story_id=body.story_id,
                        user_id=user_id,
                        min_estimate=min(valid_estimates),
                        max_estimate=max(valid_estimates),
                        average_estimate=round(avg, 2),
                        suggested_estimate=most_common
                    )
                    session.add(poker_session)
                    await session.flush()  # Get the session_id
                    
                    # Save individual persona estimates
                    for est in estimates:
                        persona_est = PokerPersonaEstimate(
                            session_id=poker_session.session_id,
                            persona_name=est["name"],
                            persona_role=est["role"],
                            estimate_points=est["estimate"],
                            reasoning=est["reasoning"],
                            confidence=est.get("confidence", "medium")
                        )
                        session.add(persona_est)
                    
                    await session.commit()
                    session_id = poker_session.session_id
                    logger.info(f"Saved poker session {session_id} with {len(estimates)} estimates")
                except Exception as save_error:
                    logger.error(f"Failed to save poker session: {save_error}")
                    # Don't fail the whole operation if save fails
                
                summary = {
                    "estimates": estimates,
                    "average": round(avg, 1),
                    "suggested": most_common,
                    "min": min(valid_estimates),
                    "max": max(valid_estimates),
                    "consensus": consensus,
                    "session_id": session_id
                }
                
                yield f"data: {json.dumps({'type': 'summary', 'summary': summary})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )



class SaveEstimateRequest(BaseModel):
    story_id: str
    story_points: int


@router.post("/save-estimate")
async def save_estimate(
    request: Request,
    body: SaveEstimateRequest,
    session: AsyncSession = Depends(get_db)
):
    """Save the accepted story point estimate to the database"""
    from db.user_story_models import UserStory
    
    # Verify user is authenticated (we don't need the ID, just auth check)
    await get_current_user_id(request, session)
    
    # Find the story
    result = await session.execute(
        select(UserStory).where(UserStory.story_id == body.story_id)
    )
    story = result.scalar_one_or_none()
    
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    
    # Update story points
    story.story_points = body.story_points
    story.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    await session.refresh(story)
    
    return {
        "success": True,
        "story_id": body.story_id,
        "story_points": body.story_points
    }



@router.post("/estimate-custom")
async def estimate_story_custom_text(
    request: Request,
    story_title: str,
    story_description: str,
    acceptance_criteria: List[str] = [],
    session: AsyncSession = Depends(get_db)
):
    """
    Get AI estimates for a custom story text (not from database)
    Useful for quick estimations without saving the story first
    """
    user_id = await get_current_user_id(request, session)
    
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
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
    
    # Build story context
    story_context = f"""
USER STORY TO ESTIMATE:
- Title: {story_title}
- Description: {story_description}
- Acceptance Criteria:
{chr(10).join(f'  - {c}' for c in (acceptance_criteria or ['No criteria specified']))}
"""
    
    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'total_personas': len(AI_PERSONAS)})}\n\n"
        
        estimates = []
        
        for persona in AI_PERSONAS:
            yield f"data: {json.dumps({'type': 'persona_start', 'persona': {'id': persona['id'], 'name': persona['name'], 'role': persona['role'], 'avatar': persona['avatar']}})}\n\n"
            
            system_prompt = f"""{delivery_context_text}

{persona['perspective']}

FIBONACCI SCALE FOR ESTIMATION:
- 1: Trivial - A few hours of work
- 2: Small - About a day of work
- 3: Medium - 2-3 days of work
- 5: Large - About a week of work
- 8: Very Large - 1-2 weeks
- 13: Huge - More than 2 weeks (should be split)

RESPONSE FORMAT (JSON only):
{{
  "estimate": <number from 1,2,3,5,8,13>,
  "reasoning": "<2-3 sentences from your role's perspective>",
  "confidence": "<low|medium|high>"
}}"""

            user_prompt = f"""Please estimate from your perspective as a {persona['role']}:

{story_context}"""

            try:
                full_response = ""
                async for chunk in llm_service.generate_stream(
                    user_id=user_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    conversation_history=None
                ):
                    full_response += chunk
                
                import re
                json_match = re.search(r'\{[\s\S]*?\}', full_response)
                if json_match:
                    try:
                        estimate_data = json.loads(json_match.group(0))
                        estimate = estimate_data.get("estimate", 3)
                        if estimate not in [1, 2, 3, 5, 8, 13]:
                            valid = [1, 2, 3, 5, 8, 13]
                            estimate = min(valid, key=lambda x: abs(x - estimate))
                        
                        persona_estimate = {
                            "persona_id": persona["id"],
                            "name": persona["name"],
                            "role": persona["role"],
                            "avatar": persona["avatar"],
                            "estimate": estimate,
                            "reasoning": estimate_data.get("reasoning", "No reasoning provided"),
                            "confidence": estimate_data.get("confidence", "medium")
                        }
                        estimates.append(persona_estimate)
                        yield f"data: {json.dumps({'type': 'persona_estimate', 'estimate': persona_estimate})}\n\n"
                    except json.JSONDecodeError:
                        yield f"data: {json.dumps({'type': 'persona_error', 'persona_id': persona['id'], 'error': 'Parse error'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'persona_error', 'persona_id': persona['id'], 'error': str(e)})}\n\n"
        
        if estimates:
            valid_estimates = [e["estimate"] for e in estimates]
            if valid_estimates:
                avg = sum(valid_estimates) / len(valid_estimates)
                from collections import Counter
                most_common = Counter(valid_estimates).most_common(1)[0][0]
                variance = sum((e - avg) ** 2 for e in valid_estimates) / len(valid_estimates)
                
                summary = {
                    "estimates": estimates,
                    "average": round(avg, 1),
                    "suggested": most_common,
                    "min": min(valid_estimates),
                    "max": max(valid_estimates),
                    "consensus": "high" if variance < 2 else "medium" if variance < 5 else "low"
                }
                yield f"data: {json.dumps({'type': 'summary', 'summary': summary})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/sessions/{story_id}")
async def get_poker_sessions(
    story_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all poker estimation sessions for a story with their reasoning"""
    user_id = await get_current_user_id(request, session)
    
    # Get all sessions for this story
    result = await session.execute(
        select(PokerEstimateSession)
        .where(PokerEstimateSession.story_id == story_id)
        .order_by(PokerEstimateSession.created_at.desc())
    )
    sessions = result.scalars().all()
    
    sessions_data = []
    for poker_session in sessions:
        # Get persona estimates for this session
        estimates_result = await session.execute(
            select(PokerPersonaEstimate)
            .where(PokerPersonaEstimate.session_id == poker_session.session_id)
        )
        persona_estimates = estimates_result.scalars().all()
        
        sessions_data.append({
            "session_id": poker_session.session_id,
            "story_id": poker_session.story_id,
            "min_estimate": poker_session.min_estimate,
            "max_estimate": poker_session.max_estimate,
            "average_estimate": poker_session.average_estimate,
            "suggested_estimate": poker_session.suggested_estimate,
            "accepted_estimate": poker_session.accepted_estimate,
            "accepted_at": poker_session.accepted_at.isoformat() if poker_session.accepted_at else None,
            "created_at": poker_session.created_at.isoformat(),
            "estimates": [
                {
                    "persona_name": est.persona_name,
                    "persona_role": est.persona_role,
                    "estimate_points": est.estimate_points,
                    "reasoning": est.reasoning,
                    "confidence": est.confidence
                }
                for est in persona_estimates
            ]
        })
    
    return {"sessions": sessions_data}


@router.get("/session/{session_id}")
async def get_poker_session(
    session_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get a specific poker session with full reasoning details"""
    await get_current_user_id(request, session)
    
    # Get the session
    result = await session.execute(
        select(PokerEstimateSession).where(PokerEstimateSession.session_id == session_id)
    )
    poker_session = result.scalar_one_or_none()
    
    if not poker_session:
        raise HTTPException(status_code=404, detail="Poker session not found")
    
    # Get persona estimates
    estimates_result = await session.execute(
        select(PokerPersonaEstimate)
        .where(PokerPersonaEstimate.session_id == session_id)
    )
    persona_estimates = estimates_result.scalars().all()
    
    return {
        "session_id": poker_session.session_id,
        "story_id": poker_session.story_id,
        "min_estimate": poker_session.min_estimate,
        "max_estimate": poker_session.max_estimate,
        "average_estimate": poker_session.average_estimate,
        "suggested_estimate": poker_session.suggested_estimate,
        "accepted_estimate": poker_session.accepted_estimate,
        "accepted_at": poker_session.accepted_at.isoformat() if poker_session.accepted_at else None,
        "created_at": poker_session.created_at.isoformat(),
        "estimates": [
            {
                "persona_name": est.persona_name,
                "persona_role": est.persona_role,
                "estimate_points": est.estimate_points,
                "reasoning": est.reasoning,
                "confidence": est.confidence
            }
            for est in persona_estimates
        ]
    }

