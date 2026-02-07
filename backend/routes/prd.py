"""
PRD Document API for JarlPM
Save and retrieve Product Requirements Documents
"""
import logging
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from db import get_db
from db.models import Epic, PRDDocument
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prd", tags=["prd"])


# Pydantic schemas for PRD validation
class PRDSummary(BaseModel):
    title: str = Field(default="Untitled PRD")
    version: str = Field(default="1.0")
    owner: str = Field(default="Product Manager")
    overview: str = Field(default="")
    problem_statement: str = Field(default="")
    goal: str = Field(default="")
    target_users: str = Field(default="")


class PRDContext(BaseModel):
    evidence: List[str] = Field(default_factory=list)
    current_workflow: str = Field(default="")
    why_now: str = Field(default="")


class PRDPersona(BaseModel):
    name: str = Field(default="User")
    context: str = Field(default="")
    jtbd: str = Field(default="")
    pain_points: List[str] = Field(default_factory=list)
    current_workaround: str = Field(default="")


class PRDScopeItem(BaseModel):
    item: str
    rationale: str = Field(default="")


class PRDAssumption(BaseModel):
    assumption: str
    risk_if_wrong: str = Field(default="")
    validation: str = Field(default="")


class PRDScope(BaseModel):
    mvp_in: List[PRDScopeItem] = Field(default_factory=list)
    not_now: List[PRDScopeItem] = Field(default_factory=list)
    assumptions: List[PRDAssumption] = Field(default_factory=list)


class PRDStory(BaseModel):
    story: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    edge_cases: List[str] = Field(default_factory=list)


class PRDFeature(BaseModel):
    name: str
    description: str = Field(default="")
    priority: str = Field(default="should-have")
    stories: List[PRDStory] = Field(default_factory=list)


class PRDRequirements(BaseModel):
    features: List[PRDFeature] = Field(default_factory=list)


class PRDNFRs(BaseModel):
    performance: List[str] = Field(default_factory=list)
    reliability: List[str] = Field(default_factory=list)
    security: List[str] = Field(default_factory=list)
    accessibility: List[str] = Field(default_factory=list)


class PRDSuccessMetric(BaseModel):
    metric: str
    target: str = Field(default="")
    measurement: str = Field(default="")


class PRDMetrics(BaseModel):
    success_metrics: List[PRDSuccessMetric] = Field(default_factory=list)
    guardrails: List[str] = Field(default_factory=list)
    instrumentation: List[str] = Field(default_factory=list)
    evaluation_window: str = Field(default="")


class PRDRisk(BaseModel):
    risk: str
    type: str = Field(default="product")
    likelihood: str = Field(default="medium")
    impact: str = Field(default="medium")
    mitigation: str = Field(default="")


class PRDOpenQuestion(BaseModel):
    question: str
    owner: str = Field(default="TBD")
    due_date: str = Field(default="TBD")
    status: str = Field(default="open")


class PRDGlossaryItem(BaseModel):
    term: str
    definition: str = Field(default="")


class PRDAppendix(BaseModel):
    alternatives_considered: List[str] = Field(default_factory=list)
    glossary: List[PRDGlossaryItem] = Field(default_factory=list)


class StructuredPRD(BaseModel):
    """Complete structured PRD schema for validation"""
    summary: PRDSummary = Field(default_factory=PRDSummary)
    context: PRDContext = Field(default_factory=PRDContext)
    personas: List[PRDPersona] = Field(default_factory=list)
    scope: PRDScope = Field(default_factory=PRDScope)
    requirements: PRDRequirements = Field(default_factory=PRDRequirements)
    nfrs: PRDNFRs = Field(default_factory=PRDNFRs)
    metrics: PRDMetrics = Field(default_factory=PRDMetrics)
    risks: List[PRDRisk] = Field(default_factory=list)
    open_questions: List[PRDOpenQuestion] = Field(default_factory=list)
    appendix: PRDAppendix = Field(default_factory=PRDAppendix)


class SavePRDRequest(BaseModel):
    """Request to save PRD (legacy markdown format)"""
    epic_id: str
    content: str  # Frontend sends as 'content', we'll store in 'sections'
    title: Optional[str] = None
    version: str = "1.0"
    status: str = "draft"


class UpdateStructuredPRDRequest(BaseModel):
    """Request to update structured PRD"""
    prd: dict  # The full structured PRD JSON
    title: Optional[str] = None
    version: Optional[str] = None


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
    """Get saved PRD for an Epic - returns structured JSON or legacy markdown"""
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
    
    # Determine format and extract content
    sections = prd.sections or {}
    prd_format = sections.get("format", "markdown")
    
    if prd_format == "json" and "prd" in sections:
        # New structured JSON format
        return {
            "epic_id": epic_id,
            "epic_title": epic.title,
            "prd": {
                "prd_id": prd.prd_id,
                "data": sections.get("prd"),
                "format": "json",
                "title": prd.title,
                "version": prd.version,
                "status": prd.status,
            },
            "updated_at": prd.updated_at.isoformat(),
            "exists": True
        }
    else:
        # Legacy markdown format
        return {
            "epic_id": epic_id,
            "epic_title": epic.title,
            "prd": {
                "prd_id": prd.prd_id,
                "content": sections.get("content", ""),
                "format": "markdown",
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


@router.put("/update/{epic_id}")
async def update_structured_prd(
    epic_id: str,
    request: Request,
    body: UpdateStructuredPRDRequest,
    session: AsyncSession = Depends(get_db)
):
    """Update structured PRD (JSON format) for an Epic"""
    user_id = await get_current_user_id(request, session)
    
    # Get existing PRD
    prd_result = await session.execute(
        select(PRDDocument).where(
            PRDDocument.epic_id == epic_id,
            PRDDocument.user_id == user_id
        )
    )
    prd = prd_result.scalar_one_or_none()
    
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    
    # Validate the PRD structure using Pydantic
    try:
        validated_prd = StructuredPRD.model_validate(body.prd)
        prd_data = validated_prd.model_dump()
    except Exception as e:
        logger.warning(f"PRD validation warning: {e}")
        # Still accept it but log the warning
        prd_data = body.prd
    
    # Update the PRD
    prd.sections = {
        "prd": prd_data,
        "format": "json",
        "validated": True,
        "edited": True
    }
    
    if body.title:
        prd.title = body.title
    if body.version:
        prd.version = body.version
    
    prd.source = "manual_edit"
    prd.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {
        "success": True,
        "epic_id": epic_id,
        "prd": prd_data,
        "message": "PRD updated successfully"
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
    Produces a structured JSON PRD with all senior PM-quality sections.
    """
    from services.llm_service import LLMService
    from services.strict_output_service import StrictOutputService
    from services.epic_service import EpicService
    from db.feature_models import Feature
    from db.user_story_models import UserStory
    from db.models import EpicSnapshot
    
    user_id = await get_current_user_id(request, session)
    
    # Check subscription
    epic_service = EpicService(session)
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required for AI features")
    
    # Get epic with snapshot
    epic_result = await session.execute(
        select(Epic).where(Epic.epic_id == epic_id, Epic.user_id == user_id)
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get snapshot for detailed content
    snapshot_result = await session.execute(
        select(EpicSnapshot).where(EpicSnapshot.epic_id == epic_id)
    )
    snapshot = snapshot_result.scalar_one_or_none()
    
    # Get LLM config
    llm_service = LLMService(session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured. Please add your API key in Settings.")
    
    # Prepare for streaming - extract config BEFORE releasing session
    config_data = llm_service.prepare_for_streaming(llm_config)
    
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
                    "title": s.title or s.story_text[:50] if s.story_text else "Untitled",
                    "story_text": s.story_text or "",
                    "acceptance_criteria": s.acceptance_criteria or [],
                    "edge_cases": s.edge_cases or [],
                    "notes_for_engineering": s.notes_for_engineering or "",
                    "points": s.story_points,
                    "priority": s.priority
                }
                for s in feature_stories
            ]
        })
    
    # Get problem statement and outcome from snapshot or epic proposal
    problem_statement = ""
    desired_outcome = ""
    epic_summary = ""
    target_users = ""
    
    if snapshot:
        problem_statement = snapshot.problem_statement or ""
        desired_outcome = snapshot.desired_outcome or ""
        epic_summary = snapshot.epic_summary or ""
    
    # Fallback to pending_proposal if snapshot doesn't have content
    if epic.pending_proposal:
        proposal = epic.pending_proposal
        if not problem_statement:
            problem_statement = proposal.get("problem_statement", "")
        if not desired_outcome:
            desired_outcome = proposal.get("desired_outcome", "")
        # Try to get more context from proposal
        if proposal.get("prd"):
            prd = proposal.get("prd", {})
            if not problem_statement:
                problem_statement = prd.get("problem_statement", "")
            if not desired_outcome:
                desired_outcome = prd.get("desired_outcome", "")
            target_users = prd.get("target_users", "")
    
    system_prompt = """You are a Senior Product Manager creating a comprehensive, stakeholder-ready PRD.

Generate a structured JSON PRD following this EXACT schema. Every field must have meaningful content - no placeholders or "TBD".

OUTPUT FORMAT: Valid JSON only. No markdown, no explanations, no extra text.

REQUIRED JSON SCHEMA:
{
  "summary": {
    "title": "string - Product/feature name",
    "version": "string - e.g. '1.0'",
    "owner": "string - Product Manager name or role",
    "overview": "string - One paragraph executive summary (2-3 sentences)",
    "problem_statement": "string - What's broken and why it matters (be specific with impact)",
    "goal": "string - Measurable desired outcome with success criteria",
    "target_users": "string - Who uses this and in what context"
  },
  "context": {
    "evidence": ["array of strings - Data points, customer quotes, research findings, support tickets"],
    "current_workflow": "string - What users do today without this solution",
    "why_now": "string - Urgency or triggering change for building this now"
  },
  "personas": [
    {
      "name": "string - Persona name (e.g. 'Sarah, Team Lead')",
      "context": "string - Role and situation",
      "jtbd": "string - Job to be done (When I..., I want to..., So that...)",
      "pain_points": ["array of strings - Top frustrations"],
      "current_workaround": "string - How they solve it today"
    }
  ],
  "scope": {
    "mvp_in": [
      {
        "item": "string - What's included",
        "rationale": "string - Why it's essential for MVP"
      }
    ],
    "not_now": [
      {
        "item": "string - What's deferred",
        "rationale": "string - Why it's not in MVP"
      }
    ],
    "assumptions": [
      {
        "assumption": "string - What we're assuming is true",
        "risk_if_wrong": "string - Impact if this assumption is false",
        "validation": "string - How we'll validate this"
      }
    ]
  },
  "requirements": {
    "features": [
      {
        "name": "string - Feature name",
        "description": "string - What it does",
        "priority": "string - must-have | should-have | nice-to-have",
        "stories": [
          {
            "story": "string - As a [user], I want [action] so that [benefit]",
            "acceptance_criteria": ["array of strings - Given/When/Then format"],
            "edge_cases": ["array of strings - Failure modes and edge cases"]
          }
        ]
      }
    ]
  },
  "nfrs": {
    "performance": ["array of strings - p95/p99 targets, load times"],
    "reliability": ["array of strings - Error handling, uptime targets"],
    "security": ["array of strings - Auth, data protection, PII handling"],
    "accessibility": ["array of strings - WCAG level, screen reader support"]
  },
  "metrics": {
    "success_metrics": [
      {
        "metric": "string - What we're measuring",
        "target": "string - Specific target value",
        "measurement": "string - How we'll measure it"
      }
    ],
    "guardrails": ["array of strings - Metrics we must not hurt"],
    "instrumentation": ["array of strings - Events and properties to track"],
    "evaluation_window": "string - When and how we'll evaluate success"
  },
  "risks": [
    {
      "risk": "string - What could go wrong",
      "type": "string - product | technical | execution",
      "likelihood": "string - high | medium | low",
      "impact": "string - high | medium | low",
      "mitigation": "string - How we'll address it"
    }
  ],
  "open_questions": [
    {
      "question": "string - What needs to be answered",
      "owner": "string - Who's responsible",
      "due_date": "string - When it needs resolution",
      "status": "string - open | in-progress | resolved"
    }
  ],
  "appendix": {
    "alternatives_considered": ["array of strings - Other approaches we evaluated"],
    "glossary": [
      {
        "term": "string - Technical term",
        "definition": "string - Plain English explanation"
      }
    ]
  }
}

QUALITY GUIDELINES:
- Be specific and actionable, not generic
- Use real data from the input, don't invent features
- Acceptance criteria must be testable (Given/When/Then)
- Metrics must have specific numeric targets
- Risks must have concrete mitigations
- Pain points should reflect real user frustrations"""

    import json as json_module
    
    user_prompt = f"""Create a comprehensive PRD for:

PRODUCT: {epic.title}

PROBLEM STATEMENT:
{problem_statement or 'Needs to be defined based on the features'}

DESIRED OUTCOME:
{desired_outcome or 'Needs to be defined based on the features'}

TARGET USERS:
{target_users or 'Needs to be defined based on the features'}

EPIC SUMMARY:
{epic_summary or 'Needs to be defined based on the features'}

FEATURES AND USER STORIES:
{json_module.dumps(features_context, indent=2) if features_context else 'No features defined yet - create reasonable MVP features based on the problem'}

Generate the PRD as VALID JSON matching the schema exactly. Include all sections with meaningful content."""

    try:
        full_response = ""
        # Use sessionless streaming
        llm = LLMService()  # No session needed
        async for chunk in llm.stream_with_config(config_data, system_prompt, user_prompt):
            full_response += chunk
        
        if not full_response.strip():
            raise HTTPException(status_code=500, detail="LLM returned empty response")
        
        # Use validate_and_repair for strict schema validation
        strict_service = StrictOutputService()
        
        # Create repair callback for LLM
        async def repair_callback(repair_prompt: str) -> str:
            repair_response = ""
            async for chunk in llm.stream_with_config(config_data, system_prompt, repair_prompt):
                repair_response += chunk
            return repair_response
        
        # Validate and repair the PRD against StructuredPRD schema
        validation_result = await strict_service.validate_and_repair(
            raw_response=full_response,
            schema=StructuredPRD,
            repair_callback=repair_callback,
            max_repairs=2,
            original_prompt=user_prompt
        )
        
        if validation_result.valid and validation_result.data:
            # Successfully validated against StructuredPRD schema
            prd_json = validation_result.data
            prd_data = {
                "prd": prd_json,
                "format": "json",
                "repair_attempts": validation_result.repair_attempts,
                "validated": True
            }
            logger.info(f"PRD validated successfully against StructuredPRD schema (repairs: {validation_result.repair_attempts})")
        else:
            # Schema validation failed - attempt to coerce partial data through Pydantic defaults
            logger.warning(f"PRD schema validation failed after {validation_result.repair_attempts} repairs. Errors: {validation_result.errors}")
            
            # Extract whatever JSON we can
            partial_json = strict_service.extract_json(full_response)
            
            if partial_json:
                # Use Pydantic to fill in defaults for missing fields
                try:
                    # This will use default values for any missing fields
                    coerced_prd = StructuredPRD.model_validate(partial_json)
                    prd_json = coerced_prd.model_dump()
                    prd_data = {
                        "prd": prd_json,
                        "format": "json",
                        "repair_attempts": validation_result.repair_attempts,
                        "validated": True,
                        "coerced": True  # Flag that defaults were applied
                    }
                    logger.info("PRD coerced to valid schema using Pydantic defaults")
                except Exception as coerce_error:
                    # Even coercion failed - this shouldn't happen with our defaults
                    logger.error(f"PRD coercion failed: {coerce_error}")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"PRD generation failed schema validation. Errors: {validation_result.errors[:3]}"
                    )
            else:
                # No valid JSON at all - fail explicitly
                raise HTTPException(
                    status_code=500,
                    detail="PRD generation failed: LLM did not return valid JSON structure"
                )
        
        # Save the generated PRD with a fresh session
        from db import AsyncSessionLocal
        async with AsyncSessionLocal() as new_session:
            existing_result = await new_session.execute(
                select(PRDDocument).where(PRDDocument.epic_id == epic_id)
            )
            existing_prd = existing_result.scalar_one_or_none()
            
            if existing_prd:
                existing_prd.sections = prd_data
                existing_prd.source = "ai_generated"
                existing_prd.updated_at = datetime.now(timezone.utc)
            else:
                new_prd = PRDDocument(
                    epic_id=epic_id,
                    user_id=user_id,
                    sections=prd_data,
                    title=epic.title,
                    version="1.0",
                    status="draft",
                    source="ai_generated"
                )
                new_session.add(new_prd)
            
            await new_session.commit()
        
        return {
            "success": True,
            "epic_id": epic_id,
            "prd": prd_json,
            "format": "json",
            "source": "ai_generated",
            "repair_attempts": validation_result.repair_attempts,
            "validated": True,
            "message": "PRD generated and validated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PRD generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PRD: {str(e)}")
