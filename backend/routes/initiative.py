"""
Magic Moment: New Initiative Generator
3-Pass Pipeline for higher quality output:
  1. PRD Pass - problem, users, metrics, constraints
  2. Decomposition Pass - features → stories with AC
  3. Planning Pass - 2-sprint plan + story points
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
# Pydantic Schemas
# ============================================

def generate_id(prefix: str = "") -> str:
    """Generate a stable short ID"""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class StorySchema(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("story_"))
    title: str
    persona: str
    action: str
    benefit: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    points: int = Field(default=3, ge=1, le=13)
    
    @validator('points', pre=True, always=True)
    def validate_fibonacci(cls, v):
        if v is None:
            return 3
        valid = [1, 2, 3, 5, 8, 13]
        v = int(v) if isinstance(v, (int, float, str)) else 3
        if v not in valid:
            return min(valid, key=lambda x: abs(x - v))
        return v


class FeatureSchema(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("feat_"))
    name: str
    description: str
    priority: str = "should-have"
    stories: List[StorySchema] = Field(default_factory=list)
    
    @validator('priority', pre=True, always=True)
    def validate_priority(cls, v):
        if not v:
            return 'should-have'
        valid = ['must-have', 'should-have', 'nice-to-have']
        v_lower = str(v).lower().strip()
        return v_lower if v_lower in valid else 'should-have'


class PRDSchema(BaseModel):
    problem_statement: str = ""
    target_users: str = ""
    desired_outcome: str = ""
    key_metrics: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class EpicSchema(BaseModel):
    title: str = ""
    description: str = ""
    vision: str = ""


class SprintSchema(BaseModel):
    goal: str = ""
    story_ids: List[str] = Field(default_factory=list)
    total_points: int = 0


class SprintPlanSchema(BaseModel):
    sprint_1: SprintSchema = Field(default_factory=SprintSchema)
    sprint_2: SprintSchema = Field(default_factory=SprintSchema)


class InitiativeSchema(BaseModel):
    product_name: str = ""
    tagline: str = ""
    prd: PRDSchema = Field(default_factory=PRDSchema)
    epic: EpicSchema = Field(default_factory=EpicSchema)
    features: List[FeatureSchema] = Field(default_factory=list)
    sprint_plan: SprintPlanSchema = Field(default_factory=SprintPlanSchema)
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
# Pass 1: PRD Generation
# ============================================

PRD_SYSTEM = """You are JarlPM, an expert Product Manager. Generate a focused PRD from a raw idea.

OUTPUT: Valid JSON only, no markdown or explanation.

{
  "product_name": "short name",
  "tagline": "one-line pitch",
  "prd": {
    "problem_statement": "2-3 sentences on the core problem",
    "target_users": "specific user persona(s)",
    "desired_outcome": "what success looks like",
    "key_metrics": ["metric1", "metric2", "metric3"],
    "out_of_scope": ["excluded1", "excluded2"],
    "risks": ["risk1", "risk2"]
  },
  "epic": {
    "title": "Epic title for this initiative",
    "description": "1-2 sentence epic description",
    "vision": "Product vision statement"
  }
}

Be specific and actionable. Focus on the MVP."""


PRD_USER = """Create a PRD for this idea:

{idea}

{name_hint}

Return only valid JSON matching the schema."""


# ============================================
# Pass 2: Feature Decomposition
# ============================================

DECOMP_SYSTEM = """You are JarlPM. Given a PRD, decompose it into features and user stories.

OUTPUT: Valid JSON only.

{
  "features": [
    {
      "name": "Feature name",
      "description": "What it does",
      "priority": "must-have | should-have | nice-to-have",
      "stories": [
        {
          "title": "Story title",
          "persona": "a [user type]",
          "action": "[what they want to do]",
          "benefit": "[why they want it]",
          "acceptance_criteria": [
            "Given X, When Y, Then Z",
            "Given A, When B, Then C"
          ]
        }
      ]
    }
  ]
}

RULES:
- 3-5 features for MVP
- 2-4 stories per feature
- Each story has 2-4 acceptance criteria in Given/When/Then format
- Priorities: at least 1 must-have, rest should-have or nice-to-have
- Stories should be small enough to complete in 1-3 days"""


DECOMP_USER = """Decompose this PRD into features and user stories:

PRODUCT: {product_name}
TAGLINE: {tagline}

PROBLEM: {problem_statement}
USERS: {target_users}
OUTCOME: {desired_outcome}

OUT OF SCOPE: {out_of_scope}

Generate features with detailed user stories and acceptance criteria. Return only valid JSON."""


# ============================================
# Pass 3: Sprint Planning + Points
# ============================================

PLANNING_SYSTEM = """You are JarlPM. Given features and stories, assign story points and create a 2-sprint plan.

OUTPUT: Valid JSON only.

{
  "estimated_stories": [
    {
      "story_id": "the story id",
      "title": "story title (for reference)",
      "points": 3
    }
  ],
  "sprint_plan": {
    "sprint_1": {
      "goal": "Sprint 1 goal - what's delivered",
      "story_ids": ["story_id1", "story_id2"],
      "total_points": 13
    },
    "sprint_2": {
      "goal": "Sprint 2 goal - what's delivered",
      "story_ids": ["story_id3", "story_id4"],
      "total_points": 8
    }
  }
}

FIBONACCI SCALE:
- 1: Trivial (few hours)
- 2: Small (half day)
- 3: Medium (1-2 days)
- 5: Large (2-3 days)
- 8: Very Large (3-5 days)
- 13: Huge (1 week, consider splitting)

RULES:
- Each sprint should have 13-21 points
- Must-have stories go in Sprint 1
- Nice-to-have stories go in Sprint 2
- Balance the sprints reasonably"""


PLANNING_USER = """Estimate story points and create a 2-sprint plan for:

PRODUCT: {product_name}
GOAL: {desired_outcome}

FEATURES & STORIES:
{stories_list}

Assign Fibonacci points (1,2,3,5,8,13) to each story and organize into 2 sprints. Return only valid JSON."""


# ============================================
# JSON Extraction
# ============================================

def extract_json(text: str) -> Optional[dict]:
    """Extract JSON from text, handling markdown code blocks"""
    if not text:
        return None
        
    # Try markdown code block first
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Find outermost { }
    start = text.find('{')
    if start == -1:
        return None
    
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


async def run_llm_pass(llm_service, user_id: str, system: str, user: str, max_retries: int = 1) -> Optional[dict]:
    """Run a single LLM pass with retry"""
    for attempt in range(max_retries + 1):
        full_response = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt=system,
            user_prompt=user,
            conversation_history=None
        ):
            full_response += chunk
        
        result = extract_json(full_response)
        if result:
            return result
        
        if attempt < max_retries:
            # Retry with a nudge
            user = user + "\n\nIMPORTANT: Return ONLY valid JSON, no other text."
    
    return None


# ============================================
# Main Endpoint
# ============================================

@router.post("/generate")
async def generate_initiative(
    request: Request,
    body: NewInitiativeRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate initiative using 3-pass pipeline:
    1. PRD Pass - problem definition
    2. Decomposition Pass - features & stories
    3. Planning Pass - points & sprints
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

    async def generate():
        try:
            # ========== PASS 1: PRD ==========
            yield f"data: {json.dumps({'type': 'pass', 'pass': 1, 'message': 'Defining the problem...'})}\n\n"
            
            prd_prompt = PRD_USER.format(
                idea=body.idea,
                name_hint=f"Product name hint: {body.product_name}" if body.product_name else ""
            )
            
            prd_result = await run_llm_pass(llm_service, user_id, PRD_SYSTEM, prd_prompt, max_retries=1)
            
            if not prd_result:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to generate PRD. Please try again.'})}\n\n"
                return
            
            # Extract PRD data
            product_name = prd_result.get('product_name', body.product_name or 'New Product')
            tagline = prd_result.get('tagline', '')
            prd_data = prd_result.get('prd', {})
            epic_data = prd_result.get('epic', {})
            
            yield f"data: {json.dumps({'type': 'progress', 'pass': 1, 'message': f'PRD complete: {product_name}'})}\n\n"
            
            # ========== PASS 2: DECOMPOSITION ==========
            yield f"data: {json.dumps({'type': 'pass', 'pass': 2, 'message': 'Breaking down features...'})}\n\n"
            
            decomp_prompt = DECOMP_USER.format(
                product_name=product_name,
                tagline=tagline,
                problem_statement=prd_data.get('problem_statement', ''),
                target_users=prd_data.get('target_users', ''),
                desired_outcome=prd_data.get('desired_outcome', ''),
                out_of_scope=', '.join(prd_data.get('out_of_scope', []))
            )
            
            decomp_result = await run_llm_pass(llm_service, user_id, DECOMP_SYSTEM, decomp_prompt, max_retries=1)
            
            if not decomp_result:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to decompose features. Please try again.'})}\n\n"
                return
            
            # Parse features and assign IDs
            features_raw = decomp_result.get('features', [])
            features = []
            all_stories = []
            
            for f_data in features_raw:
                feature = FeatureSchema(
                    name=f_data.get('name', 'Feature'),
                    description=f_data.get('description', ''),
                    priority=f_data.get('priority', 'should-have'),
                    stories=[]
                )
                
                for s_data in f_data.get('stories', []):
                    story = StorySchema(
                        title=s_data.get('title', 'Story'),
                        persona=s_data.get('persona', 'a user'),
                        action=s_data.get('action', ''),
                        benefit=s_data.get('benefit', ''),
                        acceptance_criteria=s_data.get('acceptance_criteria', [])
                    )
                    feature.stories.append(story)
                    all_stories.append({
                        'id': story.id,
                        'title': story.title,
                        'feature': feature.name,
                        'priority': feature.priority
                    })
                
                features.append(feature)
            
            story_count = sum(len(f.stories) for f in features)
            yield f"data: {json.dumps({'type': 'progress', 'pass': 2, 'message': f'Created {len(features)} features, {story_count} stories'})}\n\n"
            
            # ========== PASS 3: PLANNING ==========
            yield f"data: {json.dumps({'type': 'pass', 'pass': 3, 'message': 'Planning sprints...'})}\n\n"
            
            # Build stories list for planning prompt
            stories_list = ""
            for f in features:
                stories_list += f"\n[{f.priority.upper()}] {f.name}:\n"
                for s in f.stories:
                    stories_list += f"  - {s.id}: {s.title}\n"
                    stories_list += f"    As {s.persona}, I want to {s.action}\n"
            
            planning_prompt = PLANNING_USER.format(
                product_name=product_name,
                desired_outcome=prd_data.get('desired_outcome', ''),
                stories_list=stories_list
            )
            
            planning_result = await run_llm_pass(llm_service, user_id, PLANNING_SYSTEM, planning_prompt, max_retries=1)
            
            # Apply estimates to stories
            if planning_result:
                estimates = {e['story_id']: e['points'] for e in planning_result.get('estimated_stories', [])}
                
                for feature in features:
                    for story in feature.stories:
                        if story.id in estimates:
                            story.points = min(13, max(1, estimates[story.id]))
                
                # Build sprint plan
                sp = planning_result.get('sprint_plan', {})
                sprint_plan = SprintPlanSchema(
                    sprint_1=SprintSchema(
                        goal=sp.get('sprint_1', {}).get('goal', 'MVP Core'),
                        story_ids=sp.get('sprint_1', {}).get('story_ids', []),
                        total_points=sp.get('sprint_1', {}).get('total_points', 0)
                    ),
                    sprint_2=SprintSchema(
                        goal=sp.get('sprint_2', {}).get('goal', 'Polish & Extend'),
                        story_ids=sp.get('sprint_2', {}).get('story_ids', []),
                        total_points=sp.get('sprint_2', {}).get('total_points', 0)
                    )
                )
            else:
                # Default planning if pass 3 fails
                sprint_plan = SprintPlanSchema()
                logger.warning("Planning pass failed, using default sprint plan")
            
            yield f"data: {json.dumps({'type': 'progress', 'pass': 3, 'message': 'Sprint plan complete'})}\n\n"
            
            # ========== BUILD FINAL OUTPUT ==========
            initiative = InitiativeSchema(
                product_name=product_name,
                tagline=tagline,
                prd=PRDSchema(**prd_data),
                epic=EpicSchema(**epic_data),
                features=features,
                sprint_plan=sprint_plan
            )
            initiative.assign_ids()
            initiative.calculate_totals()
            
            # Recalculate sprint totals based on actual story points
            story_points_map = {}
            for f in initiative.features:
                for s in f.stories:
                    story_points_map[s.id] = s.points
            
            initiative.sprint_plan.sprint_1.total_points = sum(
                story_points_map.get(sid, 0) for sid in initiative.sprint_plan.sprint_1.story_ids
            )
            initiative.sprint_plan.sprint_2.total_points = sum(
                story_points_map.get(sid, 0) for sid in initiative.sprint_plan.sprint_2.story_ids
            )
            
            # Send final result
            yield f"data: {json.dumps({'type': 'initiative', 'data': initiative.model_dump()})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'message': 'Initiative generated!'})}\n\n"
            
        except Exception as e:
            logger.error(f"Initiative generation failed: {e}", exc_info=True)
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
    """Save a generated initiative to the database."""
    user_id = await get_current_user_id(request, session)
    
    try:
        validated = InitiativeSchema(**initiative)
        validated.assign_ids()
        validated.calculate_totals()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid initiative data: {e}")
    
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
        
        # Create Features and Stories
        feature_id_map = {}
        story_id_map = {}
        
        for i, feat_data in enumerate(validated.features):
            feature_db_id = feat_data.id
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
            
            for j, story_data in enumerate(feat_data.stories):
                story_db_id = story_data.id
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
            "story_ids": story_id_map
        }
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to save initiative: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@router.get("/schema")
async def get_initiative_schema():
    """Return the initiative JSON schema for reference"""
    return {
        "pipeline": [
            {"pass": 1, "name": "PRD", "output": "product_name, tagline, prd, epic"},
            {"pass": 2, "name": "Decomposition", "output": "features with stories and AC"},
            {"pass": 3, "name": "Planning", "output": "story points and 2-sprint plan"}
        ],
        "schema": InitiativeSchema.model_json_schema()
    }
