"""
Magic Moment: New Initiative Generator
4-Pass Pipeline for production-quality output:
  1. PRD Pass - problem, users, metrics, constraints
  2. Decomposition Pass - features → stories with AC
  3. Planning Pass - 2-sprint plan + story points
  4. Critic Pass - PM reality checks + auto-fixes

Uses delivery context for personalized output:
  - Industry-specific language and metrics
  - Team capacity-aware sprint planning
  - Platform-appropriate story formats (Jira/Linear/Azure DevOps)
  - Methodology-aligned processes (Scrum/Kanban/Hybrid)
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
from db.models import Epic, EpicSnapshot, Subscription, SubscriptionStatus, ProductDeliveryContext
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
# Delivery Context Formatting
# ============================================

def format_delivery_context(context: Optional[ProductDeliveryContext]) -> dict:
    """Format delivery context into usable values for prompts"""
    if not context:
        return {
            "industry": "general",
            "methodology": "scrum",
            "sprint_length": 14,
            "team_size": 5,
            "velocity": 21,  # Default velocity estimate
            "platform": "jira",
            "has_context": False
        }
    
    # Calculate team velocity estimate (story points per sprint)
    devs = context.num_developers or 3
    qas = context.num_qa or 1
    sprint_days = context.sprint_cycle_length or 14
    # Rough estimate: each dev can do ~5-8 points per 2-week sprint
    velocity = int((devs * 6 + qas * 2) * (sprint_days / 14))
    
    return {
        "industry": context.industry or "general",
        "methodology": (context.delivery_methodology or "scrum").lower(),
        "sprint_length": context.sprint_cycle_length or 14,
        "team_size": devs + qas,
        "num_devs": devs,
        "num_qa": qas,
        "velocity": velocity,
        "platform": (context.delivery_platform or "jira").lower(),
        "has_context": True
    }


def build_context_prompt(ctx: dict) -> str:
    """Build a context section for prompts based on user's delivery context"""
    if not ctx.get("has_context"):
        return ""
    
    platform_guidance = {
        "jira": "Use Jira-style story format. Include story type labels (Story, Task, Bug).",
        "azure_devops": "Use Azure DevOps work item format. Include Area Path suggestions.",
        "linear": "Use Linear-style concise format. Include project/team labels.",
        "github": "Use GitHub Issues format. Include labels and milestone suggestions.",
    }
    
    methodology_guidance = {
        "scrum": "Follow Scrum practices. Include Definition of Done, sprint goals.",
        "kanban": "Follow Kanban flow. Focus on WIP limits and cycle time.",
        "hybrid": "Blend Scrum ceremonies with Kanban flow principles.",
    }
    
    industry_metrics = {
        "fintech": ["transaction success rate", "fraud detection rate", "API latency p99"],
        "healthcare": ["patient satisfaction", "appointment completion rate", "HIPAA compliance"],
        "e-commerce": ["conversion rate", "cart abandonment rate", "average order value"],
        "saas": ["monthly active users", "churn rate", "NPS score", "time to value"],
        "education": ["course completion rate", "learner engagement", "assessment scores"],
    }
    
    context_parts = [
        f"\nORGANIZATION CONTEXT:",
        f"- Industry: {ctx['industry'].title()}",
        f"- Methodology: {ctx['methodology'].title()}",
        f"- Sprint Length: {ctx['sprint_length']} days",
        f"- Team: {ctx.get('num_devs', 3)} devs, {ctx.get('num_qa', 1)} QA",
        f"- Estimated Velocity: {ctx['velocity']} points/sprint",
        f"- Platform: {ctx['platform'].replace('_', ' ').title()}",
        "",
        platform_guidance.get(ctx['platform'], ""),
        methodology_guidance.get(ctx['methodology'], ""),
    ]
    
    # Add industry-specific metric suggestions
    industry_key = ctx['industry'].lower()
    if industry_key in industry_metrics:
        context_parts.append(f"Suggested metrics for {ctx['industry']}: {', '.join(industry_metrics[industry_key])}")
    
    return "\n".join(context_parts)


def build_dod_for_methodology(methodology: str) -> List[str]:
    """Build Definition of Done based on methodology"""
    base_dod = [
        "Code reviewed and approved",
        "Unit tests passing (>80% coverage)",
        "Acceptance criteria verified",
        "Documentation updated",
    ]
    
    if methodology == "scrum":
        base_dod.extend([
            "Demo-ready for sprint review",
            "No critical bugs",
            "Product Owner sign-off"
        ])
    elif methodology == "kanban":
        base_dod.extend([
            "Deployed to staging",
            "Monitoring alerts configured",
            "Ready for production deploy"
        ])
    
    return base_dod


# ============================================
# Pass 1: PRD Generation
# ============================================

PRD_SYSTEM = """You are JarlPM, an expert Product Manager. Generate a focused PRD from a raw idea.
{context}

OUTPUT: Valid JSON only, no markdown or explanation.

{{
  "product_name": "short name",
  "tagline": "one-line pitch",
  "prd": {{
    "problem_statement": "2-3 sentences on the core problem",
    "target_users": "specific user persona(s)",
    "desired_outcome": "what success looks like",
    "key_metrics": ["metric1", "metric2", "metric3"],
    "out_of_scope": ["excluded1", "excluded2"],
    "risks": ["risk1", "risk2"]
  }},
  "epic": {{
    "title": "Epic title for this initiative",
    "description": "1-2 sentence epic description",
    "vision": "Product vision statement"
  }}
}}

Use industry-appropriate language and metrics. Be specific and actionable. Focus on the MVP."""


PRD_USER = """Create a PRD for this idea:

{idea}

{name_hint}

Return only valid JSON matching the schema."""


# ============================================
# Pass 2: Feature Decomposition
# ============================================

DECOMP_SYSTEM = """You are JarlPM. Given a PRD, decompose it into features and user stories.
{context}

OUTPUT: Valid JSON only.

{{
  "features": [
    {{
      "name": "Feature name",
      "description": "What it does",
      "priority": "must-have | should-have | nice-to-have",
      "stories": [
        {{
          "title": "Story title",
          "persona": "a [user type]",
          "action": "[what they want to do]",
          "benefit": "[why they want it]",
          "acceptance_criteria": [
            "Given X, When Y, Then Z",
            "Given A, When B, Then C"
          ]
        }}
      ]
    }}
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
# Pass 4: PM Reality Check (Critic)
# ============================================

CRITIC_SYSTEM = """You are a Senior PM reviewing an initiative for quality and completeness.

Review the initiative and identify issues. Then provide fixes.

OUTPUT: Valid JSON only.

{
  "issues": [
    {
      "type": "metric_not_measurable | ac_not_testable | story_too_large | missing_nfr | scope_risk | other",
      "severity": "error | warning",
      "location": "where the issue is (e.g., 'Story: User Login', 'Metric: User satisfaction')",
      "problem": "what's wrong",
      "fix": "suggested fix or null if just a warning"
    }
  ],
  "fixes": {
    "metrics": ["list of improved/added metrics if any were unclear"],
    "split_stories": [
      {
        "original_story_id": "story_xxx",
        "new_stories": [
          {
            "title": "New smaller story 1",
            "persona": "...",
            "action": "...",
            "benefit": "...",
            "acceptance_criteria": ["..."],
            "points": 3
          }
        ]
      }
    ],
    "added_nfr_stories": [
      {
        "title": "NFR story title",
        "persona": "a developer",
        "action": "...",
        "benefit": "...",
        "acceptance_criteria": ["..."],
        "points": 2,
        "nfr_type": "security | performance | accessibility | reliability"
      }
    ],
    "improved_acceptance_criteria": [
      {
        "story_id": "story_xxx",
        "improved_criteria": ["Given X, When Y, Then Z (measurable)"]
      }
    ]
  },
  "summary": {
    "total_issues": 5,
    "errors": 1,
    "warnings": 4,
    "auto_fixed": 3,
    "scope_assessment": "on_track | at_risk | overloaded",
    "recommendation": "Brief recommendation for the PM"
  }
}

CHECKS TO PERFORM:
1. METRICS: Are they specific and measurable? (bad: "user satisfaction", good: "NPS score > 40")
2. ACCEPTANCE CRITERIA: Are they testable? Must be Given/When/Then with observable outcomes
3. STORY SIZE: Flag stories > 8 points - suggest splits into smaller stories
4. NFRs: Check for missing security, performance, accessibility, error handling stories
5. SCOPE: Is total points realistic for 2 sprints (26-42 points ideal)?

Be constructive. Auto-fix what you can, warn about the rest."""


CRITIC_USER = """Review this initiative for PM quality issues:

PRODUCT: {product_name}
PROBLEM: {problem_statement}
TARGET USERS: {target_users}

METRICS:
{metrics}

FEATURES & STORIES:
{stories_detail}

SPRINT PLAN:
- Sprint 1: {sprint1_points} points
- Sprint 2: {sprint2_points} points
- Total: {total_points} points

Review for: measurable metrics, testable ACs, story sizing (split if >8), missing NFRs, scope sanity.
Return only valid JSON with issues and fixes."""


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
    Generate initiative using 4-pass pipeline:
    1. PRD Pass - problem definition
    2. Decomposition Pass - features & stories
    3. Planning Pass - points & sprints
    4. Critic Pass - PM reality checks & auto-fixes
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
            
            # ========== PASS 4: PM REALITY CHECK ==========
            yield f"data: {json.dumps({'type': 'pass', 'pass': 4, 'message': 'Running PM quality checks...'})}\n\n"
            
            # Build detailed stories list for critic
            stories_detail = ""
            for f in features:
                stories_detail += f"\n[{f.priority.upper()}] {f.name}: {f.description}\n"
                for s in f.stories:
                    stories_detail += f"  • {s.id}: {s.title} ({s.points} pts)\n"
                    stories_detail += f"    As {s.persona}, I want to {s.action} so that {s.benefit}\n"
                    stories_detail += f"    AC: {'; '.join(s.acceptance_criteria[:3])}\n"
            
            # Calculate totals for critic
            sprint1_points = sum(
                next((s.points for f in features for s in f.stories if s.id == sid), 0)
                for sid in (sprint_plan.sprint_1.story_ids if planning_result else [])
            )
            sprint2_points = sum(
                next((s.points for f in features for s in f.stories if s.id == sid), 0)
                for sid in (sprint_plan.sprint_2.story_ids if planning_result else [])
            )
            total_points = sum(s.points for f in features for s in f.stories)
            
            critic_prompt = CRITIC_USER.format(
                product_name=product_name,
                problem_statement=prd_data.get('problem_statement', ''),
                target_users=prd_data.get('target_users', ''),
                metrics=', '.join(prd_data.get('key_metrics', [])),
                stories_detail=stories_detail,
                sprint1_points=sprint1_points,
                sprint2_points=sprint2_points,
                total_points=total_points
            )
            
            critic_result = await run_llm_pass(llm_service, user_id, CRITIC_SYSTEM, critic_prompt, max_retries=1)
            
            # Apply critic fixes
            warnings = []
            if critic_result:
                fixes = critic_result.get('fixes', {})
                issues = critic_result.get('issues', [])
                summary = critic_result.get('summary', {})
                
                # Collect warnings for UI
                for issue in issues:
                    if issue.get('severity') == 'warning' or not issue.get('fix'):
                        warnings.append({
                            'type': issue.get('type', 'other'),
                            'location': issue.get('location', ''),
                            'problem': issue.get('problem', '')
                        })
                
                # Apply metric improvements
                if fixes.get('metrics'):
                    prd_data['key_metrics'] = fixes['metrics']
                
                # Apply AC improvements
                for ac_fix in fixes.get('improved_acceptance_criteria', []):
                    story_id = ac_fix.get('story_id')
                    new_criteria = ac_fix.get('improved_criteria', [])
                    for feature in features:
                        for story in feature.stories:
                            if story.id == story_id and new_criteria:
                                story.acceptance_criteria = new_criteria
                
                # Split large stories
                for split in fixes.get('split_stories', []):
                    original_id = split.get('original_story_id')
                    new_stories_data = split.get('new_stories', [])
                    
                    # Find and replace the original story
                    for feature in features:
                        for i, story in enumerate(feature.stories):
                            if story.id == original_id and new_stories_data:
                                # Remove original, add split stories
                                feature.stories.pop(i)
                                for ns_data in new_stories_data:
                                    new_story = StorySchema(
                                        title=ns_data.get('title', 'Split Story'),
                                        persona=ns_data.get('persona', story.persona),
                                        action=ns_data.get('action', ''),
                                        benefit=ns_data.get('benefit', story.benefit),
                                        acceptance_criteria=ns_data.get('acceptance_criteria', []),
                                        points=min(8, ns_data.get('points', 3))
                                    )
                                    feature.stories.insert(i, new_story)
                                break
                
                # Add NFR stories to a new feature or existing
                nfr_stories = fixes.get('added_nfr_stories', [])
                if nfr_stories:
                    # Find or create NFR feature
                    nfr_feature = None
                    for f in features:
                        if 'non-functional' in f.name.lower() or 'nfr' in f.name.lower():
                            nfr_feature = f
                            break
                    
                    if not nfr_feature:
                        nfr_feature = FeatureSchema(
                            name="Non-Functional Requirements",
                            description="Security, performance, and accessibility requirements",
                            priority="should-have",
                            stories=[]
                        )
                        features.append(nfr_feature)
                    
                    for nfr_data in nfr_stories:
                        nfr_story = StorySchema(
                            title=nfr_data.get('title', 'NFR Story'),
                            persona=nfr_data.get('persona', 'a developer'),
                            action=nfr_data.get('action', ''),
                            benefit=nfr_data.get('benefit', ''),
                            acceptance_criteria=nfr_data.get('acceptance_criteria', []),
                            points=nfr_data.get('points', 2)
                        )
                        nfr_feature.stories.append(nfr_story)
                
                auto_fixed_count = summary.get('auto_fixed', 0)
                yield f"data: {json.dumps({'type': 'progress', 'pass': 4, 'message': f'Quality check complete: {auto_fixed_count} auto-fixes applied'})}\n\n"
            else:
                summary = {}
                logger.warning("Critic pass failed, skipping quality checks")
                yield f"data: {json.dumps({'type': 'progress', 'pass': 4, 'message': 'Quality check skipped'})}\n\n"
            
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
            
            # Build final response with warnings
            response_data = initiative.model_dump()
            if warnings:
                response_data['warnings'] = warnings
            if critic_result and critic_result.get('summary'):
                response_data['quality_summary'] = critic_result['summary']
            
            # Send final result
            yield f"data: {json.dumps({'type': 'initiative', 'data': response_data})}\n\n"
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
            {"pass": 3, "name": "Planning", "output": "story points and 2-sprint plan"},
            {"pass": 4, "name": "Critic", "output": "quality checks, auto-fixes, warnings"}
        ],
        "quality_checks": [
            "Metrics are specific and measurable",
            "Acceptance criteria are testable (Given/When/Then)",
            "Stories ≤ 8 points (auto-split if larger)",
            "NFRs included (security, performance, accessibility)",
            "Scope is realistic for 2 sprints (26-42 points)"
        ],
        "schema": InitiativeSchema.model_json_schema()
    }
