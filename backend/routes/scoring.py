"""
Scoring Routes for JarlPM
Handles RICE and MoSCoW scoring with AI assistance
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import EpicStage
from db.scoring_models import MoSCoWScore, IMPACT_VALUES, CONFIDENCE_VALUES, IMPACT_LABELS, CONFIDENCE_LABELS, MOSCOW_LABELS
from services.scoring_service import ScoringService
from services.llm_service import LLMService
from services.prompt_service import PromptService
from services.epic_service import EpicService
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scoring", tags=["scoring"])


# ============================================
# Request/Response Models
# ============================================

class MoSCoWScoreUpdate(BaseModel):
    score: str = Field(..., description="MoSCoW score: must_have, should_have, could_have, wont_have")


class RICEScoreUpdate(BaseModel):
    reach: int = Field(..., ge=1, le=10, description="Users affected per time period (1-10)")
    impact: float = Field(..., description="Impact per user: 0.25, 0.5, 1, 2, 3")
    confidence: float = Field(..., description="Confidence: 0.5 (low), 0.8 (medium), 1.0 (high)")
    effort: float = Field(..., ge=0.5, le=10, description="Person-months of effort (0.5-10)")


class ScoringOptionsResponse(BaseModel):
    moscow_options: dict
    rice_impact_options: dict
    rice_confidence_options: dict


class EpicMoSCoWResponse(BaseModel):
    epic_id: str
    moscow_score: Optional[str] = None
    moscow_label: Optional[str] = None


class FeatureScoringResponse(BaseModel):
    feature_id: str
    moscow_score: Optional[str] = None
    moscow_label: Optional[str] = None
    rice_reach: Optional[int] = None
    rice_impact: Optional[float] = None
    rice_impact_label: Optional[str] = None
    rice_confidence: Optional[float] = None
    rice_confidence_label: Optional[str] = None
    rice_effort: Optional[float] = None
    rice_total: Optional[float] = None


class StoryRICEResponse(BaseModel):
    story_id: str
    rice_reach: Optional[int] = None
    rice_impact: Optional[float] = None
    rice_impact_label: Optional[str] = None
    rice_confidence: Optional[float] = None
    rice_confidence_label: Optional[str] = None
    rice_effort: Optional[float] = None
    rice_total: Optional[float] = None


class BugRICEResponse(BaseModel):
    bug_id: str
    rice_reach: Optional[int] = None
    rice_impact: Optional[float] = None
    rice_impact_label: Optional[str] = None
    rice_confidence: Optional[float] = None
    rice_confidence_label: Optional[str] = None
    rice_effort: Optional[float] = None
    rice_total: Optional[float] = None


# ============================================
# Scoring Options Endpoint
# ============================================

@router.get("/options", response_model=ScoringOptionsResponse)
async def get_scoring_options():
    """Get all valid scoring options for UI dropdowns"""
    return ScoringOptionsResponse(
        moscow_options={k.value: v for k, v in MOSCOW_LABELS.items()},
        rice_impact_options=IMPACT_LABELS,
        rice_confidence_options=CONFIDENCE_LABELS
    )


# ============================================
# Epic MoSCoW Endpoints
# ============================================

@router.get("/epic/{epic_id}/moscow", response_model=EpicMoSCoWResponse)
async def get_epic_moscow(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get MoSCoW score for an Epic"""
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    
    epic = await scoring_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    label = None
    if epic.moscow_score:
        try:
            label = MOSCOW_LABELS.get(MoSCoWScore(epic.moscow_score))
        except ValueError:
            pass
    
    return EpicMoSCoWResponse(
        epic_id=epic.epic_id,
        moscow_score=epic.moscow_score,
        moscow_label=label
    )


@router.put("/epic/{epic_id}/moscow", response_model=EpicMoSCoWResponse)
async def update_epic_moscow(
    request: Request,
    epic_id: str,
    body: MoSCoWScoreUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update MoSCoW score for an Epic"""
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    
    try:
        epic = await scoring_service.update_epic_moscow(epic_id, user_id, body.score)
        label = MOSCOW_LABELS.get(MoSCoWScore(epic.moscow_score)) if epic.moscow_score else None
        return EpicMoSCoWResponse(
            epic_id=epic.epic_id,
            moscow_score=epic.moscow_score,
            moscow_label=label
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.post("/epic/{epic_id}/moscow/suggest")
async def suggest_epic_moscow(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get AI suggestion for Epic MoSCoW score (streaming)"""
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    epic = await scoring_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Check subscription
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
    
    # Build context
    epic_context = scoring_service.build_epic_context_for_ai(epic)
    
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping prioritize work using the MoSCoW framework.

MoSCoW Categories:
- MUST HAVE: Critical requirements essential for success. Without these, the product fails.
- SHOULD HAVE: Important but not critical. Can work around their absence temporarily.
- COULD HAVE: Nice to have. Include if time/resources allow.
- WON'T HAVE: Explicitly out of scope for now. May revisit later.

EPIC TO PRIORITIZE:
{epic_context}

Analyze this epic and suggest a MoSCoW classification. Explain your reasoning briefly.

RESPONSE FORMAT (JSON only at the end):
Provide your analysis, then end with:
[SUGGESTION]
{{"score": "must_have|should_have|could_have|wont_have", "reasoning": "Brief explanation"}}
[/SUGGESTION]"""

    user_prompt = "Please analyze and suggest a MoSCoW classification for this epic."
    
    async def generate():
        full_response = ""
        try:
            async for chunk in llm_service.generate_stream(
                user_id=user_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Extract suggestion
            import re
            match = re.search(r'\[SUGGESTION\]([\s\S]*?)\[/SUGGESTION\]', full_response)
            if match:
                try:
                    suggestion = json.loads(match.group(1).strip())
                    yield f"data: {json.dumps({'type': 'suggestion', 'suggestion': suggestion})}\n\n"
                except json.JSONDecodeError:
                    pass
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Epic MoSCoW suggestion error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


# ============================================
# Feature Scoring Endpoints
# ============================================

@router.get("/feature/{feature_id}", response_model=FeatureScoringResponse)
async def get_feature_scores(
    request: Request,
    feature_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get all scores for a Feature"""
    await get_current_user_id(request, session)  # Auth check
    scoring_service = ScoringService(session)
    
    feature = await scoring_service.get_feature(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    moscow_label = None
    if feature.moscow_score:
        try:
            moscow_label = MOSCOW_LABELS.get(MoSCoWScore(feature.moscow_score))
        except ValueError:
            pass
    
    return FeatureScoringResponse(
        feature_id=feature.feature_id,
        moscow_score=feature.moscow_score,
        moscow_label=moscow_label,
        rice_reach=feature.rice_reach,
        rice_impact=feature.rice_impact,
        rice_impact_label=IMPACT_LABELS.get(feature.rice_impact) if feature.rice_impact else None,
        rice_confidence=feature.rice_confidence,
        rice_confidence_label=CONFIDENCE_LABELS.get(feature.rice_confidence) if feature.rice_confidence else None,
        rice_effort=feature.rice_effort,
        rice_total=feature.rice_total
    )


@router.put("/feature/{feature_id}/moscow", response_model=FeatureScoringResponse)
async def update_feature_moscow(
    request: Request,
    feature_id: str,
    body: MoSCoWScoreUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update MoSCoW score for a Feature"""
    await get_current_user_id(request, session)  # Auth check
    scoring_service = ScoringService(session)
    
    try:
        feature = await scoring_service.update_feature_moscow(feature_id, body.score)
        moscow_label = MOSCOW_LABELS.get(MoSCoWScore(feature.moscow_score)) if feature.moscow_score else None
        return FeatureScoringResponse(
            feature_id=feature.feature_id,
            moscow_score=feature.moscow_score,
            moscow_label=moscow_label,
            rice_reach=feature.rice_reach,
            rice_impact=feature.rice_impact,
            rice_impact_label=IMPACT_LABELS.get(feature.rice_impact) if feature.rice_impact else None,
            rice_confidence=feature.rice_confidence,
            rice_confidence_label=CONFIDENCE_LABELS.get(feature.rice_confidence) if feature.rice_confidence else None,
            rice_effort=feature.rice_effort,
            rice_total=feature.rice_total
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.put("/feature/{feature_id}/rice", response_model=FeatureScoringResponse)
async def update_feature_rice(
    request: Request,
    feature_id: str,
    body: RICEScoreUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update RICE score for a Feature"""
    await get_current_user_id(request, session)  # Auth check
    scoring_service = ScoringService(session)
    
    try:
        feature = await scoring_service.update_feature_rice(
            feature_id, body.reach, body.impact, body.confidence, body.effort
        )
        moscow_label = MOSCOW_LABELS.get(MoSCoWScore(feature.moscow_score)) if feature.moscow_score else None
        return FeatureScoringResponse(
            feature_id=feature.feature_id,
            moscow_score=feature.moscow_score,
            moscow_label=moscow_label,
            rice_reach=feature.rice_reach,
            rice_impact=feature.rice_impact,
            rice_impact_label=IMPACT_LABELS.get(feature.rice_impact) if feature.rice_impact else None,
            rice_confidence=feature.rice_confidence,
            rice_confidence_label=CONFIDENCE_LABELS.get(feature.rice_confidence) if feature.rice_confidence else None,
            rice_effort=feature.rice_effort,
            rice_total=feature.rice_total
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.post("/feature/{feature_id}/suggest")
async def suggest_feature_scores(
    request: Request,
    feature_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get AI suggestion for Feature MoSCoW and RICE scores (streaming)"""
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    feature = await scoring_service.get_feature(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    # Check subscription
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
    
    # Build context
    feature_context = scoring_service.build_feature_context_for_ai(feature)
    
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping prioritize features using MoSCoW and RICE frameworks.

MoSCoW Categories:
- must_have: Critical, essential for success
- should_have: Important but not critical
- could_have: Nice to have if resources allow
- wont_have: Explicitly out of scope for now

RICE Framework:
- Reach (1-10): How many users will this affect? 1=few, 10=everyone
- Impact (0.25=minimal, 0.5=low, 1=medium, 2=high, 3=massive): Impact per user
- Confidence (0.5=low, 0.8=medium, 1.0=high): How confident are you in estimates?
- Effort (0.5-10): Person-months to implement

RICE Score = (Reach × Impact × Confidence) / Effort

FEATURE TO PRIORITIZE:
{feature_context}

Analyze this feature and suggest both MoSCoW and RICE scores.

RESPONSE FORMAT:
Provide analysis, then end with:
[SUGGESTION]
{{
  "moscow": {{"score": "must_have|should_have|could_have|wont_have", "reasoning": "..."}},
  "rice": {{
    "reach": 1-10,
    "impact": 0.25|0.5|1|2|3,
    "confidence": 0.5|0.8|1.0,
    "effort": 0.5-10,
    "reasoning": "..."
  }}
}}
[/SUGGESTION]"""

    user_prompt = "Please analyze and suggest prioritization scores for this feature."
    
    async def generate():
        full_response = ""
        try:
            async for chunk in llm_service.generate_stream(
                user_id=user_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Extract suggestion
            import re
            match = re.search(r'\[SUGGESTION\]([\s\S]*?)\[/SUGGESTION\]', full_response)
            if match:
                try:
                    suggestion = json.loads(match.group(1).strip())
                    yield f"data: {json.dumps({'type': 'suggestion', 'suggestion': suggestion})}\n\n"
                except json.JSONDecodeError:
                    pass
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Feature scoring suggestion error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


# ============================================
# User Story RICE Endpoints
# ============================================

@router.get("/story/{story_id}", response_model=StoryRICEResponse)
async def get_story_rice(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get RICE score for a User Story"""
    await get_current_user_id(request, session)  # Auth check
    scoring_service = ScoringService(session)
    
    story = await scoring_service.get_user_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    return StoryRICEResponse(
        story_id=story.story_id,
        rice_reach=story.rice_reach,
        rice_impact=story.rice_impact,
        rice_impact_label=IMPACT_LABELS.get(story.rice_impact) if story.rice_impact else None,
        rice_confidence=story.rice_confidence,
        rice_confidence_label=CONFIDENCE_LABELS.get(story.rice_confidence) if story.rice_confidence else None,
        rice_effort=story.rice_effort,
        rice_total=story.rice_total
    )


@router.put("/story/{story_id}/rice", response_model=StoryRICEResponse)
async def update_story_rice(
    request: Request,
    story_id: str,
    body: RICEScoreUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update RICE score for a User Story"""
    await get_current_user_id(request, session)  # Auth check
    scoring_service = ScoringService(session)
    
    try:
        story = await scoring_service.update_story_rice(
            story_id, body.reach, body.impact, body.confidence, body.effort
        )
        return StoryRICEResponse(
            story_id=story.story_id,
            rice_reach=story.rice_reach,
            rice_impact=story.rice_impact,
            rice_impact_label=IMPACT_LABELS.get(story.rice_impact) if story.rice_impact else None,
            rice_confidence=story.rice_confidence,
            rice_confidence_label=CONFIDENCE_LABELS.get(story.rice_confidence) if story.rice_confidence else None,
            rice_effort=story.rice_effort,
            rice_total=story.rice_total
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.post("/story/{story_id}/suggest")
async def suggest_story_rice(
    request: Request,
    story_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get AI suggestion for User Story RICE score (streaming)"""
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    story = await scoring_service.get_user_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="User story not found")
    
    # Check subscription
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
    
    # Build context
    story_context = scoring_service.build_story_context_for_ai(story)
    
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping prioritize user stories using the RICE framework.

RICE Framework:
- Reach (1-10): How many users will this affect? 1=few, 10=everyone
- Impact (0.25=minimal, 0.5=low, 1=medium, 2=high, 3=massive): Impact per user
- Confidence (0.5=low, 0.8=medium, 1.0=high): How confident are you in estimates?
- Effort (0.5-10): Person-months to implement (stories are usually 0.5-2)

RICE Score = (Reach × Impact × Confidence) / Effort

USER STORY TO PRIORITIZE:
{story_context}

Analyze this user story and suggest RICE scores.

RESPONSE FORMAT:
Provide analysis, then end with:
[SUGGESTION]
{{
  "reach": 1-10,
  "impact": 0.25|0.5|1|2|3,
  "confidence": 0.5|0.8|1.0,
  "effort": 0.5-10,
  "reasoning": "..."
}}
[/SUGGESTION]"""

    user_prompt = "Please analyze and suggest RICE scores for this user story."
    
    async def generate():
        full_response = ""
        try:
            async for chunk in llm_service.generate_stream(
                user_id=user_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Extract suggestion
            import re
            match = re.search(r'\[SUGGESTION\]([\s\S]*?)\[/SUGGESTION\]', full_response)
            if match:
                try:
                    suggestion = json.loads(match.group(1).strip())
                    yield f"data: {json.dumps({'type': 'suggestion', 'suggestion': suggestion})}\n\n"
                except json.JSONDecodeError:
                    pass
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Story RICE suggestion error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


# ============================================
# Bug RICE Endpoints
# ============================================

@router.get("/bug/{bug_id}", response_model=BugRICEResponse)
async def get_bug_rice(
    request: Request,
    bug_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get RICE score for a Bug"""
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    
    bug = await scoring_service.get_bug(bug_id, user_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    return BugRICEResponse(
        bug_id=bug.bug_id,
        rice_reach=bug.rice_reach,
        rice_impact=bug.rice_impact,
        rice_impact_label=IMPACT_LABELS.get(bug.rice_impact) if bug.rice_impact else None,
        rice_confidence=bug.rice_confidence,
        rice_confidence_label=CONFIDENCE_LABELS.get(bug.rice_confidence) if bug.rice_confidence else None,
        rice_effort=bug.rice_effort,
        rice_total=bug.rice_total
    )


@router.put("/bug/{bug_id}/rice", response_model=BugRICEResponse)
async def update_bug_rice(
    request: Request,
    bug_id: str,
    body: RICEScoreUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update RICE score for a Bug"""
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    
    try:
        bug = await scoring_service.update_bug_rice(
            bug_id, user_id, body.reach, body.impact, body.confidence, body.effort
        )
        return BugRICEResponse(
            bug_id=bug.bug_id,
            rice_reach=bug.rice_reach,
            rice_impact=bug.rice_impact,
            rice_impact_label=IMPACT_LABELS.get(bug.rice_impact) if bug.rice_impact else None,
            rice_confidence=bug.rice_confidence,
            rice_confidence_label=CONFIDENCE_LABELS.get(bug.rice_confidence) if bug.rice_confidence else None,
            rice_effort=bug.rice_effort,
            rice_total=bug.rice_total
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.post("/bug/{bug_id}/suggest")
async def suggest_bug_rice(
    request: Request,
    bug_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get AI suggestion for Bug RICE score (streaming)"""
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    
    bug = await scoring_service.get_bug(bug_id, user_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    # Check subscription
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
    
    # Build context
    bug_context = scoring_service.build_bug_context_for_ai(bug)
    
    system_prompt = f"""{delivery_context_text}

You are a Senior Product Manager helping prioritize bug fixes using the RICE framework.

RICE Framework for Bugs:
- Reach (1-10): How many users are affected? 1=few edge cases, 10=all users
- Impact (0.25=minimal, 0.5=low, 1=medium, 2=high, 3=massive): Severity of impact on affected users
- Confidence (0.5=low, 0.8=medium, 1.0=high): How confident are you about root cause and fix?
- Effort (0.5-10): Person-months to fix (bugs are usually 0.5-2)

Consider: severity, user impact, workaround availability, fix complexity.

RICE Score = (Reach × Impact × Confidence) / Effort

BUG TO PRIORITIZE:
{bug_context}

Analyze this bug and suggest RICE scores.

RESPONSE FORMAT:
Provide analysis, then end with:
[SUGGESTION]
{{
  "reach": 1-10,
  "impact": 0.25|0.5|1|2|3,
  "confidence": 0.5|0.8|1.0,
  "effort": 0.5-10,
  "reasoning": "..."
}}
[/SUGGESTION]"""

    user_prompt = "Please analyze and suggest RICE scores for this bug."
    
    async def generate():
        full_response = ""
        try:
            async for chunk in llm_service.generate_stream(
                user_id=user_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Extract suggestion
            import re
            match = re.search(r'\[SUGGESTION\]([\s\S]*?)\[/SUGGESTION\]', full_response)
            if match:
                try:
                    suggestion = json.loads(match.group(1).strip())
                    yield f"data: {json.dumps({'type': 'suggestion', 'suggestion': suggestion})}\n\n"
                except json.JSONDecodeError:
                    pass
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Bug RICE suggestion error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )



# ============================================
# Bulk Epic Scoring Endpoint
# ============================================

class BulkScoringRequest(BaseModel):
    epic_id: str


class FeatureScoreSuggestion(BaseModel):
    feature_id: str
    title: str
    moscow: dict
    rice: dict


class BulkScoringResponse(BaseModel):
    epic_id: str
    epic_title: str
    suggestions: List[FeatureScoreSuggestion]
    generated_at: str


@router.post("/epic/{epic_id}/bulk-score", response_model=BulkScoringResponse)
async def bulk_score_epic_features(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Generate AI scoring suggestions for all features in an Epic"""
    from datetime import datetime, timezone
    from db.models import Epic, Subscription, SubscriptionStatus
    from db.feature_models import Feature
    from sqlalchemy import select
    
    user_id = await get_current_user_id(request, session)
    
    # Check subscription
    sub_result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE.value
        )
    )
    if not sub_result.scalar_one_or_none():
        raise HTTPException(status_code=402, detail="Active subscription required")
    
    # Get epic
    epic_result = await session.execute(
        select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get features for this epic
    features_result = await session.execute(
        select(Feature).where(Feature.epic_id == epic_id)
    )
    features = features_result.scalars().all()
    
    if not features:
        raise HTTPException(status_code=400, detail="No features found for this epic")
    
    # Get LLM service
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="Please configure an LLM provider in Settings first")
    
    # Build context for all features
    features_context = []
    for f in features:
        features_context.append(f"- {f.title}: {f.description or 'No description'}")
    
    features_list = "\n".join(features_context)
    
    system_prompt = f"""You are a Senior Product Manager helping prioritize features using MoSCoW and RICE frameworks.

EPIC: {epic.title}

FEATURES TO SCORE:
{features_list}

For each feature, provide:
1. MoSCoW score (must_have, should_have, could_have, wont_have)
2. RICE scores:
   - Reach (1-10): Users affected
   - Impact (0.25=minimal, 0.5=low, 1=medium, 2=high, 3=massive)
   - Confidence (0.5=low, 0.8=medium, 1.0=high)
   - Effort (0.5-10 person-months)

IMPORTANT: Return ONLY valid JSON, no markdown fences.

Return format:
{{
  "features": [
    {{
      "title": "Feature name",
      "moscow": {{"score": "must_have|should_have|could_have|wont_have", "reasoning": "..."}},
      "rice": {{"reach": 1-10, "impact": 0.25-3, "confidence": 0.5-1.0, "effort": 0.5-10, "reasoning": "..."}}
    }}
  ]
}}"""

    user_prompt = "Please analyze and score all features for this epic."
    
    try:
        response_text = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        ):
            response_text += chunk
        
        # Parse JSON response
        clean_response = response_text.strip()
        if clean_response.startswith("```"):
            lines = clean_response.split("\n")
            clean_response = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        import json as json_lib
        result = json_lib.loads(clean_response)
        
        # Map suggestions back to features
        suggestions = []
        for suggestion in result.get("features", []):
            # Find matching feature
            matching_feature = next(
                (f for f in features if f.title.lower() == suggestion.get("title", "").lower()),
                None
            )
            if matching_feature:
                suggestions.append(FeatureScoreSuggestion(
                    feature_id=matching_feature.feature_id,
                    title=matching_feature.title,
                    moscow=suggestion.get("moscow", {}),
                    rice=suggestion.get("rice", {})
                ))
        
        return BulkScoringResponse(
            epic_id=epic_id,
            epic_title=epic.title,
            suggestions=suggestions,
            generated_at=datetime.now(timezone.utc).isoformat()
        )
        
    except json_lib.JSONDecodeError as e:
        logger.error(f"Failed to parse bulk scoring JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate valid scores. Please try again.")
    except Exception as e:
        logger.error(f"Bulk scoring failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@router.post("/epic/{epic_id}/apply-scores")
async def apply_bulk_scores(
    request: Request,
    epic_id: str,
    body: List[FeatureScoreSuggestion],
    session: AsyncSession = Depends(get_db)
):
    """Apply AI-generated scores to features"""
    from db.feature_models import Feature
    from sqlalchemy import select
    
    user_id = await get_current_user_id(request, session)
    scoring_service = ScoringService(session)
    
    # Verify epic ownership
    epic_service = EpicService(session)
    epic = await epic_service.get_epic(epic_id, user_id)
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    applied = []
    for suggestion in body:
        try:
            # Update MoSCoW
            if suggestion.moscow and suggestion.moscow.get("score"):
                await scoring_service.update_feature_moscow(
                    suggestion.feature_id, 
                    suggestion.moscow["score"]
                )
            
            # Update RICE
            if suggestion.rice:
                rice = suggestion.rice
                if all(k in rice for k in ["reach", "impact", "confidence", "effort"]):
                    await scoring_service.update_feature_rice(
                        suggestion.feature_id,
                        rice["reach"],
                        rice["impact"],
                        rice["confidence"],
                        rice["effort"]
                    )
            
            applied.append(suggestion.feature_id)
        except Exception as e:
            logger.error(f"Failed to apply scores for feature {suggestion.feature_id}: {e}")
    
    await session.commit()
    
    return {"applied": len(applied), "feature_ids": applied}
