"""
Magic Moment: New Initiative Generator
Paste a messy idea → get PRD + Epic + Features + Stories + 2-sprint plan

Features:
- Strict Pydantic schema validation
- Retry loop for JSON repair
- Stable IDs for all entities
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import json
import logging
import uuid
import re
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


# ============================================
# Pydantic Schema for Initiative
# ============================================

def generate_id(prefix: str = "") -> str:
    """Generate a stable short ID"""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class StorySchema(BaseModel):
    """User story with acceptance criteria"""
    id: str = Field(default_factory=lambda: generate_id("story_"))
    title: str
    persona: str = Field(description="As a [user type]")
    action: str = Field(description="I want to [action]")
    benefit: str = Field(description="So that [benefit]")
    acceptance_criteria: List[str] = Field(default_factory=list)
    points: int = Field(ge=1, le=13, description="Fibonacci: 1,2,3,5,8,13")
    
    @validator('points')
    def validate_fibonacci(cls, v):
        valid = [1, 2, 3, 5, 8, 13]
        if v not in valid:
            # Snap to nearest valid Fibonacci
            return min(valid, key=lambda x: abs(x - v))
        return v


class FeatureSchema(BaseModel):
    """Feature with stories"""
    id: str = Field(default_factory=lambda: generate_id("feat_"))
    name: str
    description: str
    priority: str = Field(description="must-have, should-have, or nice-to-have")
    stories: List[StorySchema] = Field(default_factory=list)
    
    @validator('priority')
    def validate_priority(cls, v):
        valid = ['must-have', 'should-have', 'nice-to-have']
        v_lower = v.lower().strip()
        if v_lower not in valid:
            # Default to should-have if invalid
            return 'should-have'
        return v_lower


class PRDSchema(BaseModel):
    """Product Requirements Document"""
    problem_statement: str
    target_users: str
    desired_outcome: str
    key_metrics: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class EpicSchema(BaseModel):
    """Epic definition"""
    title: str
    description: str
    vision: str = ""


class SprintSchema(BaseModel):
    """Sprint plan"""
    goal: str
    stories: List[str] = Field(default_factory=list, description="Story titles")
    total_points: int = 0


class SprintPlanSchema(BaseModel):
    """2-sprint delivery plan"""
    sprint_1: SprintSchema
    sprint_2: SprintSchema


class InitiativeSchema(BaseModel):
    """Complete initiative - the full output schema"""
    product_name: str
    tagline: str = ""
    prd: PRDSchema
    epic: EpicSchema
    features: List[FeatureSchema] = Field(default_factory=list)
    sprint_plan: SprintPlanSchema
    total_points: int = 0
    
    def assign_ids(self):
        """Ensure all entities have stable IDs"""
        for feature in self.features:
            if not feature.id or not feature.id.startswith('feat_'):
                feature.id = generate_id('feat_')
            for story in feature.stories:
                if not story.id or not story.id.startswith('story_'):
                    story.id = generate_id('story_')
        return self
    
    def calculate_totals(self):
        """Calculate total points"""
        total = 0
        for feature in self.features:
            for story in feature.stories:
                total += story.points
        self.total_points = total
        return self


class NewInitiativeRequest(BaseModel):
    idea: str
    product_name: Optional[str] = None


# ============================================
# Schema as JSON for LLM prompt
# ============================================

SCHEMA_JSON = '''{
  "product_name": "string (short product name)",
  "tagline": "string (one-line description)",
  "prd": {
    "problem_statement": "string (clear problem being solved)",
    "target_users": "string (who has this problem)",
    "desired_outcome": "string (what success looks like)",
    "key_metrics": ["string array of metrics"],
    "out_of_scope": ["string array of excluded items"],
    "risks": ["string array of risks"]
  },
  "epic": {
    "title": "string (epic title)",
    "description": "string (epic description)",
    "vision": "string (product vision statement)"
  },
  "features": [
    {
      "name": "string (feature name)",
      "description": "string (what this feature does)",
      "priority": "must-have | should-have | nice-to-have",
      "stories": [
        {
          "title": "string (story title)",
          "persona": "string (As a [user type])",
          "action": "string (I want to [action])",
          "benefit": "string (So that [benefit])",
          "acceptance_criteria": ["Given X, When Y, Then Z", "..."],
          "points": "number (1, 2, 3, 5, 8, or 13)"
        }
      ]
    }
  ],
  "sprint_plan": {
    "sprint_1": {
      "goal": "string (sprint 1 goal)",
      "stories": ["story title 1", "story title 2"],
      "total_points": "number"
    },
    "sprint_2": {
      "goal": "string (sprint 2 goal)",
      "stories": ["story title 3", "story title 4"],
      "total_points": "number"
    }
  },
  "total_points": "number (sum of all story points)"
}'''


SYSTEM_PROMPT = f"""You are JarlPM, an expert Product Manager AI. Transform messy ideas into structured, actionable product plans.

OUTPUT: Valid JSON matching this exact schema (no markdown, no explanation):

{SCHEMA_JSON}

RULES:
- Story points must be Fibonacci: 1, 2, 3, 5, 8, 13 (max 13)
- Feature priority must be: must-have, should-have, or nice-to-have
- Include 3-5 features with 2-4 stories each
- Sprint plans should fit ~13-21 points per sprint
- Be concise but thorough"""


REPAIR_PROMPT = """The JSON you provided failed validation. Please fix these errors and return ONLY valid JSON:

ERRORS:
{errors}

ORIGINAL (partial):
{original}

Return the complete, corrected JSON matching the schema. No explanation, just JSON."""


# ============================================
# JSON Extraction & Validation
# ============================================

def extract_json(text: str) -> Optional[dict]:
    """Extract JSON from text, handling markdown code blocks"""
    # Try markdown code block first
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find raw JSON object
    # Find the outermost { }
    start = text.find('{')
    if start == -1:
        return None
    
    # Count braces to find matching close
    depth = 0
    end = start
    for i, char in enumerate(text[start:], start):
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


def validate_initiative(data: dict) -> tuple[Optional[InitiativeSchema], List[str]]:
    """Validate initiative data against schema, return (model, errors)"""
    errors = []
    
    try:
        initiative = InitiativeSchema(**data)
        initiative.assign_ids()
        initiative.calculate_totals()
        return initiative, []
    except Exception as e:
        errors.append(str(e))
        return None, errors


# ============================================
# Endpoints
# ============================================

@router.post("/generate")
async def generate_initiative(
    request: Request,
    body: NewInitiativeRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate a complete initiative from a messy idea.
    Uses strict schema validation with retry for repair.
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

Generate JSON matching the schema exactly. Include realistic story points and a 2-sprint plan."""

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'message': 'Analyzing your idea...'})}\n\n"
        
        full_response = ""
        features_started = False
        stories_started = False
        sprint_started = False
        
        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Generating PRD and epic...'})}\n\n"
            
            # First attempt
            async for chunk in llm_service.generate_stream(
                user_id=user_id,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                conversation_history=None
            ):
                full_response += chunk
                
                # Progress updates
                if '"features"' in full_response and not features_started:
                    features_started = True
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Breaking down features...'})}\n\n"
                elif '"stories"' in full_response and not stories_started:
                    stories_started = True
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Writing user stories...'})}\n\n"
                elif '"sprint_plan"' in full_response and not sprint_started:
                    sprint_started = True
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Planning sprints...'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Validating output...'})}\n\n"
            
            # Extract and validate JSON
            raw_data = extract_json(full_response)
            
            if not raw_data:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to extract JSON from response. Please try again.'})}\n\n"
                return
            
            initiative, errors = validate_initiative(raw_data)
            
            # Retry loop for repair (max 2 attempts)
            retry_count = 0
            max_retries = 2
            
            while errors and retry_count < max_retries:
                retry_count += 1
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Repairing output (attempt {retry_count})...'})}\n\n"
                
                repair_prompt = REPAIR_PROMPT.format(
                    errors="\n".join(errors),
                    original=json.dumps(raw_data, indent=2)[:2000]  # Truncate to avoid token limits
                )
                
                repair_response = ""
                async for chunk in llm_service.generate_stream(
                    user_id=user_id,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=repair_prompt,
                    conversation_history=None
                ):
                    repair_response += chunk
                
                raw_data = extract_json(repair_response)
                if raw_data:
                    initiative, errors = validate_initiative(raw_data)
            
            if errors:
                logger.warning(f"Initiative validation failed after retries: {errors}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'Validation failed: {errors[0]}'})}\n\n"
                return
            
            if not initiative:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to generate valid initiative. Please try again.'})}\n\n"
                return
            
            # Success! Return validated initiative
            yield f"data: {json.dumps({'type': 'initiative', 'data': initiative.model_dump()})}\n\n"
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
    Save a generated initiative to the database.
    Uses the stable IDs from the validated schema.
    """
    user_id = await get_current_user_id(request, session)
    
    # Validate the initiative data
    validated, errors = validate_initiative(initiative)
    if errors or not validated:
        raise HTTPException(status_code=400, detail=f"Invalid initiative data: {errors}")
    
    now = datetime.now(timezone.utc)
    
    try:
        # Create Epic
        epic = Epic(
            epic_id=generate_id("epic_"),
            user_id=user_id,
            title=validated.product_name or validated.epic.title,
            description=validated.epic.description,
            status="in_progress",
            created_at=now,
            updated_at=now
        )
        session.add(epic)
        
        # Create snapshot with PRD data
        snapshot = EpicSnapshot(
            snapshot_id=generate_id("snap_"),
            epic_id=epic.epic_id,
            version=1,
            problem_statement=validated.prd.problem_statement,
            vision=validated.epic.vision,
            desired_outcome=validated.prd.desired_outcome,
            target_users=validated.prd.target_users,
            out_of_scope=validated.prd.out_of_scope,
            risks=validated.prd.risks,
            assumptions=[],
            success_metrics=validated.prd.key_metrics,
            created_at=now
        )
        session.add(snapshot)
        
        # Create Features and Stories with stable IDs
        feature_id_map = {}  # Map generated IDs to DB IDs
        story_id_map = {}
        
        for i, feat_data in enumerate(validated.features):
            # Use the stable ID from validation, or generate new one
            feature_db_id = feat_data.id if feat_data.id.startswith('feat_') else generate_id('feat_')
            feature_id_map[feat_data.id] = feature_db_id
            
            feature = Feature(
                feature_id=feature_db_id,
                epic_id=epic.epic_id,
                name=feat_data.name,
                description=feat_data.description,
                priority=feat_data.priority,
                status="planned",
                order_index=i,
                created_at=now,
                updated_at=now
            )
            session.add(feature)
            
            # Create stories for this feature
            for j, story_data in enumerate(feat_data.stories):
                story_db_id = story_data.id if story_data.id.startswith('story_') else generate_id('story_')
                story_id_map[story_data.id] = story_db_id
                
                story = UserStory(
                    story_id=story_db_id,
                    feature_id=feature_db_id,
                    title=story_data.title,
                    persona=story_data.persona,
                    action=story_data.action,
                    benefit=story_data.benefit,
                    story_text=f"As {story_data.persona}, I want to {story_data.action} so that {story_data.benefit}",
                    acceptance_criteria=story_data.acceptance_criteria,
                    status="draft",
                    story_points=story_data.points,
                    order_index=j,
                    created_at=now,
                    updated_at=now
                )
                session.add(story)
        
        await session.commit()
        
        return {
            "success": True,
            "epic_id": epic.epic_id,
            "features_created": len(validated.features),
            "stories_created": sum(len(f.stories) for f in validated.features),
            "total_points": validated.total_points,
            "feature_ids": feature_id_map,
            "story_ids": story_id_map,
            "message": f"Created epic with {len(validated.features)} features and {sum(len(f.stories) for f in validated.features)} stories"
        }
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to save initiative: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save initiative: {str(e)}")


@router.get("/schema")
async def get_initiative_schema():
    """Return the initiative JSON schema for reference"""
    return {
        "schema": SCHEMA_JSON,
        "example": {
            "product_name": "TaskFlow",
            "tagline": "Simple task management for busy teams",
            "prd": {
                "problem_statement": "Teams waste time tracking tasks across multiple tools",
                "target_users": "Small teams (2-10 people)",
                "desired_outcome": "Single source of truth for team tasks",
                "key_metrics": ["Weekly active users", "Tasks completed per user"],
                "out_of_scope": ["Time tracking", "Invoicing"],
                "risks": ["Market saturation", "Integration complexity"]
            },
            "epic": {
                "title": "TaskFlow MVP",
                "description": "Core task management features",
                "vision": "The simplest way to keep your team aligned"
            },
            "features": [
                {
                    "id": "feat_abc12345",
                    "name": "Task Board",
                    "description": "Kanban-style task board",
                    "priority": "must-have",
                    "stories": [
                        {
                            "id": "story_def67890",
                            "title": "Create Task",
                            "persona": "a team member",
                            "action": "create a new task",
                            "benefit": "I can track my work",
                            "acceptance_criteria": [
                                "Given I'm on the board, When I click Add, Then a task form appears"
                            ],
                            "points": 3
                        }
                    ]
                }
            ],
            "sprint_plan": {
                "sprint_1": {"goal": "Basic board", "stories": ["Create Task"], "total_points": 13},
                "sprint_2": {"goal": "Collaboration", "stories": ["Assign Task"], "total_points": 8}
            },
            "total_points": 21
        }
    }
