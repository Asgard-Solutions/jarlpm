"""
Magic Moment: New Initiative Generator
4-Pass Pipeline for production-quality output:
  1. PRD Pass - problem, users, metrics, constraints
  2. Decomposition Pass - features → stories with AC
  3. Planning Pass - 2-sprint plan + story points
  4. Critic Pass - PM reality checks + auto-fixes

Key Features:
  - Strict Output Layer: Schema validation + auto-repair (1-2 retries)
  - Quality Mode Toggle: Standard (1-pass) vs Quality (2-pass with critique)
  - Guardrail Defaults: Temperature tuning per task type
  - Weak Model Detection: Warns if model struggles with structured output
  - Delivery Context Injection: Every prompt personalized to team context

Observability:
  - Logs all generations with token usage, cost, and timing
  - Tracks parse/validation success rates per prompt version
  - Records user edits for quality feedback loop
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Type, TypeVar
import json
import logging
import uuid
import re
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db import get_db
from db.models import Epic, EpicSnapshot, Subscription, SubscriptionStatus, ProductDeliveryContext
from db.feature_models import Feature
from db.user_story_models import UserStory
from services.llm_service import LLMService
from services.analytics_service import AnalyticsService, GenerationMetrics, PassMetrics, CURRENT_PROMPT_VERSION
from services.strict_output_service import (
    StrictOutputService, get_strict_output_service,
    TaskType, QualityMode, TASK_TEMPERATURE
)
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/initiative", tags=["initiative"])

T = TypeVar('T', bound=BaseModel)


# ============================================
# Pydantic Schemas
# ============================================

def generate_id(prefix: str = "") -> str:
    """Generate a stable short ID"""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


# --- Pass 1: PRD Output Schema ---
class Pass1PRDOutput(BaseModel):
    """Schema for Pass 1 (PRD) output validation"""
    product_name: str
    tagline: str = ""
    prd: dict  # Will contain problem_statement, target_users, etc.
    epic: dict = Field(default_factory=dict)
    
    class Config:
        extra = "allow"


# --- Pass 2: Decomposition Output Schema ---
class Pass2DecompOutput(BaseModel):
    """Schema for Pass 2 (Decomposition) output validation"""
    features: List[dict]
    
    class Config:
        extra = "allow"


# --- Pass 3: Planning Output Schema ---
class Pass3PlanningOutput(BaseModel):
    """Schema for Pass 3 (Planning) output validation"""
    estimated_stories: List[dict] = Field(default_factory=list)
    sprint_plan: dict = Field(default_factory=dict)
    
    class Config:
        extra = "allow"


# --- Pass 4: Critic Output Schema ---
class Pass4CriticOutput(BaseModel):
    """Schema for Pass 4 (Critic) output validation"""
    issues: List[dict] = Field(default_factory=list)
    fixes: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    
    class Config:
        extra = "allow"


class StorySchema(BaseModel):
    """Export-ready user story schema with all fields needed for Jira/Azure DevOps/Linear export"""
    id: str = Field(default_factory=lambda: generate_id("story_"))
    title: str  # Short, actionable title
    description: str = ""  # Structured description (auto-generated from user story format)
    persona: str
    action: str
    benefit: str
    acceptance_criteria: List[str] = Field(default_factory=list)  # Gherkin format: Given/When/Then
    labels: List[str] = Field(default_factory=list)  # e.g., ["backend", "api", "auth", "mvp"]
    priority: str = "should-have"  # must-have, should-have, nice-to-have
    points: int = Field(default=3, ge=1, le=13)
    dependencies: List[str] = Field(default_factory=list)  # Story IDs or descriptions
    risks: List[str] = Field(default_factory=list)  # Risk descriptions
    
    @validator('points', pre=True, always=True)
    def validate_fibonacci(cls, v):
        if v is None:
            return 3
        valid = [1, 2, 3, 5, 8, 13]
        v = int(v) if isinstance(v, (int, float, str)) else 3
        if v not in valid:
            return min(valid, key=lambda x: abs(x - v))
        return v
    
    @validator('priority', pre=True, always=True)
    def validate_priority(cls, v):
        if not v:
            return 'should-have'
        valid = ['must-have', 'should-have', 'nice-to-have']
        v_lower = str(v).lower().strip()
        return v_lower if v_lower in valid else 'should-have'
    
    @validator('labels', pre=True, always=True)
    def validate_labels(cls, v):
        if not v:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)[:10]  # Max 10 labels
    
    def generate_description(self) -> str:
        """Generate structured description from user story components"""
        return f"As {self.persona}, I want to {self.action} so that {self.benefit}"


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

OUTPUT FORMAT:
- Return ONLY valid JSON, nothing else
- No markdown code fences (no ```json)
- No commentary before or after the JSON
- Use double quotes for all strings
- No trailing commas

SCHEMA:
{{
  "product_name": "short name (2-5 words)",
  "tagline": "one-line pitch (max 100 chars)",
  "prd": {{
    "problem_statement": "2-3 sentences on the core problem (max 400 chars)",
    "target_users": "specific user persona(s) with context",
    "desired_outcome": "what success looks like (measurable)",
    "key_metrics": ["metric1 (with target number/% or SLA)", "metric2", "metric3"],
    "out_of_scope": ["excluded1", "excluded2"],
    "risks": ["risk1", "risk2"]
  }},
  "epic": {{
    "title": "Epic title for this initiative",
    "description": "1-2 sentence epic description",
    "vision": "Product vision statement"
  }}
}}

CONSTRAINTS:
- product_name: 2-5 words, no special characters
- tagline: max 100 characters
- problem_statement: max 400 characters, specific and actionable
- key_metrics: exactly 3-5 metrics, each MUST be measurable (contain a number, %, $, SLA, or timeframe)
- out_of_scope: 2-4 items to clarify boundaries
- risks: 2-4 risks with likelihood/impact hints

Use industry-appropriate language. Focus on the MVP."""


PRD_USER = """Create a PRD for this idea:

{idea}

{name_hint}

Return only valid JSON matching the schema. No markdown fences, no commentary."""


# ============================================
# Pass 2: Feature Decomposition
# ============================================

DECOMP_SYSTEM = """You are JarlPM. Given a PRD, decompose it into features and user stories.
{context}

OUTPUT FORMAT:
- Return ONLY valid JSON, nothing else
- No markdown code fences (no ```json)
- No commentary before or after the JSON
- Use double quotes for all strings
- No trailing commas

SCHEMA:
{{
  "features": [
    {{
      "name": "Feature name (2-5 words)",
      "description": "What it does (1-2 sentences)",
      "priority": "must-have | should-have | nice-to-have",
      "stories": [
        {{
          "title": "Short, actionable title (5-10 words)",
          "persona": "a [specific user type]",
          "action": "[what they want to do]",
          "benefit": "[why they want it]",
          "acceptance_criteria": [
            "Given X, When Y, Then Z",
            "Given A, When B, Then C"
          ],
          "labels": ["backend", "frontend", "api"],
          "priority": "must-have | should-have | nice-to-have",
          "dependencies": ["Description of what this story depends on"],
          "risks": ["Potential risks or blockers for this story"]
        }}
      ]
    }}
  ]
}}

HARD CONSTRAINTS:
- 3-5 features for MVP (no more, no less)
- 2-4 stories per feature
- Each story MUST have exactly 2-4 acceptance criteria in Gherkin format (Given/When/Then)
- Each AC must contain the tokens: Given, When, Then
- Labels: choose from [backend, frontend, api, auth, database, integration, mvp, ui, performance, security, nfr]
- At least 1 feature must be must-have
- Stories should be small enough to complete in 1-3 days
- REQUIRED: Include at least 1 NFR story (security/performance/reliability/accessibility) in MVP features

PRIORITY RULES:
- must-have: Required for launch, no workarounds
- should-have: Important, but can launch without
- nice-to-have: Enhances UX, defer if needed

Use platform-appropriate story format."""


DECOMP_USER = """Decompose this PRD into features and user stories:

PRODUCT: {product_name}
TAGLINE: {tagline}

PROBLEM: {problem_statement}
USERS: {target_users}
OUTCOME: {desired_outcome}

OUT OF SCOPE: {out_of_scope}

{dod_section}

Generate features with detailed user stories and acceptance criteria. 
IMPORTANT: Include at least 1 NFR story for security, performance, or reliability.
Return only valid JSON. No markdown fences, no commentary."""


# ============================================
# Pass 3: Sprint Planning + Points
# ============================================

PLANNING_SYSTEM = """You are JarlPM. Given features and stories, assign story points and create a sprint plan.
{context}

OUTPUT FORMAT:
- Return ONLY valid JSON, nothing else
- No markdown code fences (no ```json)
- No commentary before or after the JSON
- Use double quotes for all strings
- No trailing commas

SCHEMA:
{{
  "estimated_stories": [
    {{
      "story_id": "the story id from input",
      "title": "story title (for reference)",
      "points": 3
    }}
  ],
  "sprint_plan": {{
    "sprint_1": {{
      "goal": "Sprint 1 goal - what's delivered",
      "story_ids": ["story_id1", "story_id2"],
      "total_points": 13
    }},
    "sprint_2": {{
      "goal": "Sprint 2 goal - what's delivered",
      "story_ids": ["story_id3", "story_id4"],
      "total_points": 8
    }}
  }}
}}

FIBONACCI SCALE:
- 1: Trivial (few hours)
- 2: Small (half day)
- 3: Medium (1-2 days)
- 5: Large (2-3 days)
- 8: Very Large (3-5 days)
- 13: Huge (1 week, consider splitting)

HARD CONSTRAINTS:
- Points MUST be Fibonacci: 1, 2, 3, 5, 8, or 13 only
- Respect team velocity: target {velocity} points per sprint
- Sprint length: {sprint_length} days
- CRITICAL: story_ids in sprint_plan MUST be a subset of the story_ids provided in FEATURES & STORIES
- Do NOT invent new story IDs - only use the exact IDs given to you
- Every story from the input MUST appear in estimated_stories

SPRINT ALLOCATION RULES:
- Must-have stories → Sprint 1 (prioritize)
- Should-have stories → Split between sprints based on capacity
- Nice-to-have stories → Sprint 2 (if capacity allows)
- Balance sprints for sustainable pace (avoid one overloaded sprint)"""


PLANNING_USER = """Estimate story points and create a sprint plan for:

PRODUCT: {product_name}
GOAL: {desired_outcome}

TEAM CAPACITY:
- Sprint Length: {sprint_length} days
- Team Velocity: ~{velocity} points/sprint
- Team: {num_devs} developers, {num_qa} QA

FEATURES & STORIES (use these exact story_ids):
{stories_list}

Assign Fibonacci points (1,2,3,5,8,13) to each story.
Organize into 2 sprints respecting team capacity.
CRITICAL: Only use story_ids from the list above - do not invent new IDs.
Return only valid JSON. No markdown fences, no commentary."""


# ============================================
# Pass 4: PM Reality Check (Critic)
# ============================================

CRITIC_SYSTEM = """You are a Senior PM reviewing an initiative for quality and completeness.
{context}

Review the initiative and identify issues. Then provide fixes AND a confidence assessment.

OUTPUT FORMAT:
- Return ONLY valid JSON, nothing else
- No markdown code fences (no ```json)
- No commentary before or after the JSON
- Use double quotes for all strings
- No trailing commas
- ALWAYS include all top-level keys, even if empty (issues: [], fixes: {{}}, summary: {{}}, confidence_assessment: {{}})

SCHEMA:
{{
  "issues": [
    {{
      "type": "metric_not_measurable | ac_not_testable | story_too_large | missing_nfr | scope_risk | other",
      "severity": "error | warning",
      "location": "where the issue is (e.g., 'Story: User Login', 'Metric: User satisfaction')",
      "problem": "what's wrong",
      "fix": "suggested fix or null if just a warning"
    }}
  ],
  "fixes": {{
    "metrics": [],
    "split_stories": [],
    "added_nfr_stories": [],
    "improved_acceptance_criteria": []
  }},
  "summary": {{
    "total_issues": 0,
    "errors": 0,
    "warnings": 0,
    "auto_fixed": 0,
    "scope_assessment": "on_track | at_risk | overloaded",
    "recommendation": "Brief recommendation for the PM"
  }},
  "confidence_assessment": {{
    "confidence_score": 75,
    "top_risks": [],
    "key_assumptions": [],
    "validate_first": []
  }}
}}

DETAILED SCHEMA FOR fixes:
{{
  "fixes": {{
    "metrics": ["list of improved/added metrics if any were unclear - empty array if none"],
    "split_stories": [
      {{
        "original_story_id": "story_xxx",
        "new_stories": [
          {{
            "title": "New smaller story 1",
            "persona": "...",
            "action": "...",
            "benefit": "...",
            "acceptance_criteria": ["Given X, When Y, Then Z"],
            "points": 3
          }}
        ]
      }}
    ],
    "added_nfr_stories": [
      {{
        "title": "NFR story title",
        "persona": "a developer",
        "action": "...",
        "benefit": "...",
        "acceptance_criteria": ["Given X, When Y, Then Z"],
        "points": 2,
        "nfr_type": "security | performance | accessibility | reliability"
      }}
    ],
    "improved_acceptance_criteria": [
      {{
        "story_id": "story_xxx",
        "improved_criteria": ["Given X, When Y, Then Z (measurable)"]
      }}
    ]
  }}
}}

REVIEW CHECKLIST:
1. Metrics: Are they measurable (have a number, %, $, SLA)?
2. Acceptance Criteria: Do they follow Given/When/Then? Are they testable?
3. Story Size: Any story > 8 points should be flagged for splitting
4. NFRs: Is there at least 1 security/performance/reliability story?
5. Scope: Does total points fit team capacity? Calculate scope_assessment
6. Dependencies: Are there any circular or missing dependencies?

HARD CONSTRAINTS:
- ALWAYS return all top-level keys: issues, fixes, summary, confidence_assessment
- If no fixes needed, return empty arrays/objects (not null, not omitted)
- confidence_score: integer 0-100
- top_risks: exactly 3 items
- key_assumptions: exactly 3 items
- validate_first: exactly 3 items"""
    ],
    "success_factors": [
      "Critical success factor 1",
      "Critical success factor 2"
    ]
  }}
}}

CHECKS TO PERFORM:
1. METRICS: Are they industry-appropriate and measurable? (bad: "user satisfaction", good: "NPS score > 40")
2. ACCEPTANCE CRITERIA: Are they testable? Must be Given/When/Then with observable outcomes
3. STORY SIZE: Flag stories > 8 points - suggest splits into smaller stories
4. NFRs: Check for missing security, performance, accessibility, error handling stories
5. SCOPE: Is total points realistic for team velocity of {velocity} points/sprint?

Be constructive. Auto-fix what you can, warn about the rest."""


CRITIC_USER = """Review this initiative for PM quality issues:

PRODUCT: {product_name}
INDUSTRY: {industry}
PROBLEM: {problem_statement}
TARGET USERS: {target_users}

METRICS:
{metrics}

FEATURES & STORIES:
{stories_detail}

TEAM CONTEXT:
- Methodology: {methodology}
- Sprint Length: {sprint_length} days
- Team Velocity: ~{velocity} points/sprint

SPRINT PLAN:
- Sprint 1: {sprint1_points} points
- Sprint 2: {sprint2_points} points
- Total: {total_points} points (target: ~{target_points} for 2 sprints)

Review for: industry-appropriate metrics, testable ACs, story sizing (split if >8), missing NFRs, scope vs capacity.
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


async def run_llm_pass_with_validation(
    llm_service: LLMService,
    strict_service: StrictOutputService,
    user_id: str,
    system: str,
    user: str,
    schema: Type[T],
    task_type: TaskType,
    pass_metrics: Optional[PassMetrics] = None,
    quality_mode: str = "standard",
    pass_name: str = "unknown"
) -> Optional[dict]:
    """
    Run a single LLM pass with strict output validation and auto-repair.
    
    Features:
    - Uses task-specific temperature for guardrails
    - Validates against Pydantic schema
    - Auto-repairs invalid JSON (up to 2 retries)
    - Optionally runs quality pass for 2-pass mode
    - Tracks all metrics for analytics
    - Logs retries consistently for debugging
    """
    start_time = time.time()
    temperature = strict_service.get_temperature(task_type)
    
    logger.info(f"[{pass_name}] Starting with temp={temperature}, schema={schema.__name__}")
    
    # Collect full response
    full_response = ""
    async for chunk in llm_service.generate_stream(
        user_id=user_id,
        system_prompt=system,
        user_prompt=user,
        conversation_history=None,
        temperature=temperature
    ):
        full_response += chunk
    
    logger.debug(f"[{pass_name}] Got {len(full_response)} chars response")
    
    # Define repair callback with logging
    async def repair_callback(repair_prompt: str) -> str:
        logger.info(f"[{pass_name}] Attempting repair...")
        repair_response = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt=system,
            user_prompt=repair_prompt,
            conversation_history=None,
            temperature=0.1  # Very low temp for repairs
        ):
            repair_response += chunk
        logger.debug(f"[{pass_name}] Repair got {len(repair_response)} chars")
        return repair_response
    
    # Validate and repair
    result = await strict_service.validate_and_repair(
        raw_response=full_response,
        schema=schema,
        repair_callback=repair_callback,
        max_repairs=2,
        original_prompt=user
    )
    
    # Log validation result
    if result.valid:
        if result.repair_attempts > 0:
            logger.info(f"[{pass_name}] ✓ Valid after {result.repair_attempts} repair(s)")
        else:
            logger.info(f"[{pass_name}] ✓ Valid on first attempt")
    else:
        logger.warning(f"[{pass_name}] ✗ Failed validation after {result.repair_attempts} repairs: {result.errors[:2]}")
    
    # Quality mode: 2-pass with critique
    if result.valid and quality_mode == "quality" and result.data:
        logger.info(f"[{pass_name}] Running quality pass (2-pass mode)")
        quality_prompt = strict_service.build_quality_prompt(result.data)
        quality_response = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt="You are a quality reviewer. Improve the output while keeping the same JSON structure.",
            user_prompt=quality_prompt,
            conversation_history=None,
            temperature=0.3
        ):
            quality_response += chunk
        
        improved_data = strict_service.extract_json(quality_response)
        if improved_data:
            result.data = improved_data
            logger.info(f"[{pass_name}] Quality pass improved output")
    
    # Update metrics
    if pass_metrics:
        pass_metrics.tokens_in = len(system + user) // 4
        pass_metrics.tokens_out = len(full_response) // 4
        pass_metrics.retries = result.repair_attempts
        pass_metrics.duration_ms = int((time.time() - start_time) * 1000)
        pass_metrics.success = result.valid
        if not result.valid:
            pass_metrics.error = "; ".join(result.errors[:2])
    
    # Track model health for weak model detection (persisted to DB)
    config = await llm_service.get_user_llm_config(user_id)
    if config:
        await strict_service.track_call(
            user_id=user_id,
            provider=config.provider,
            model_name=config.model_name or "",
            success=result.valid,
            repaired=result.repair_attempts > 0 and result.valid
        )
    
    return result.data if result.valid else None


async def run_llm_pass(
    llm_service,
    user_id: str,
    system: str,
    user: str,
    max_retries: int = 1,
    pass_metrics: Optional[PassMetrics] = None,
    temperature: float = None
) -> Optional[dict]:
    """Run a single LLM pass with retry, tracking metrics (legacy fallback)"""
    start_time = time.time()
    retries = 0
    
    for attempt in range(max_retries + 1):
        full_response = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt=system,
            user_prompt=user,
            conversation_history=None,
            temperature=temperature
        ):
            full_response += chunk
        
        result = extract_json(full_response)
        if result:
            # Update metrics if provided
            if pass_metrics:
                pass_metrics.tokens_in = len(system + user) // 4  # Rough estimate
                pass_metrics.tokens_out = len(full_response) // 4
                pass_metrics.retries = retries
                pass_metrics.duration_ms = int((time.time() - start_time) * 1000)
                pass_metrics.success = True
            return result
        
        retries += 1
        if attempt < max_retries:
            # Retry with a nudge
            user = user + "\n\nIMPORTANT: Return ONLY valid JSON, no other text."
    
    # Failed all attempts
    if pass_metrics:
        pass_metrics.tokens_in = len(system + user) // 4
        pass_metrics.tokens_out = len(full_response) // 4 if full_response else 0
        pass_metrics.retries = retries
        pass_metrics.duration_ms = int((time.time() - start_time) * 1000)
        pass_metrics.success = False
        pass_metrics.error = "JSON parse failed"
    
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
    
    Features:
    - Strict Output: Schema validation + auto-repair (up to 2 retries)
    - Quality Mode: Optional 2-pass with critique
    - Guardrails: Task-specific temperature settings
    - Weak Model Detection: Warns if model struggles
    - Delivery Context: Every prompt is personalized
    
    Logs all generation metrics for quality analysis.
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
    
    # Initialize strict output service with DB session for persistent metrics
    strict_service = get_strict_output_service(session)
    
    # Check for weak model warning (async, from DB - keyed by user+provider+model)
    model_warning = await strict_service.get_model_warning(
        user_id, 
        llm_config.provider, 
        llm_config.model_name
    )
    
    # Fetch delivery context for personalization
    ctx_result = await session.execute(
        select(ProductDeliveryContext).where(ProductDeliveryContext.user_id == user_id)
    )
    delivery_context = ctx_result.scalar_one_or_none()
    ctx = format_delivery_context(delivery_context)
    context_prompt = build_context_prompt(ctx)
    dod = build_dod_for_methodology(ctx['methodology'])
    
    # Get quality mode from delivery context (defaults to standard)
    quality_mode = delivery_context.quality_mode if delivery_context and delivery_context.quality_mode else "standard"
    
    # Initialize analytics
    analytics = AnalyticsService(session)
    metrics = analytics.create_metrics(
        user_id=user_id,
        idea=body.idea,
        product_name_provided=bool(body.product_name),
        llm_provider=llm_config.provider,
        model_name=llm_config.model_name,
        delivery_context=ctx
    )

    async def generate():
        try:
            # Send model warning if detected
            if model_warning:
                yield f"data: {json.dumps({'type': 'warning', 'message': model_warning})}\n\n"
            
            # Send quality mode info
            if quality_mode == "quality":
                yield f"data: {json.dumps({'type': 'info', 'message': 'Quality Mode: Using 2-pass generation with critique'})}\n\n"
            
            # ========== PASS 1: PRD ==========
            yield f"data: {json.dumps({'type': 'pass', 'pass': 1, 'message': 'Defining the problem...'})}\n\n"
            
            prd_prompt = PRD_USER.format(
                idea=body.idea,
                name_hint=f"Product name hint: {body.product_name}" if body.product_name else ""
            )
            
            # Format PRD system prompt with context
            prd_system = PRD_SYSTEM.format(context=context_prompt)
            
            # Use strict output with schema validation
            prd_result = await run_llm_pass_with_validation(
                llm_service=llm_service,
                strict_service=strict_service,
                user_id=user_id,
                system=prd_system,
                user=prd_prompt,
                schema=Pass1PRDOutput,
                task_type=TaskType.PRD_GENERATION,
                pass_metrics=metrics.pass_1,
                quality_mode=quality_mode,
                pass_name="Pass1-PRD"
            )
            
            if not prd_result:
                metrics.error_message = "Failed to generate PRD"
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
            
            # Build DoD section
            dod_section = f"DEFINITION OF DONE:\n" + "\n".join(f"- {d}" for d in dod)
            
            decomp_prompt = DECOMP_USER.format(
                product_name=product_name,
                tagline=tagline,
                problem_statement=prd_data.get('problem_statement', ''),
                target_users=prd_data.get('target_users', ''),
                desired_outcome=prd_data.get('desired_outcome', ''),
                out_of_scope=', '.join(prd_data.get('out_of_scope', [])),
                dod_section=dod_section
            )
            
            # Format decomp system prompt with context
            decomp_system = DECOMP_SYSTEM.format(context=context_prompt)
            
            # Use strict output with schema validation
            decomp_result = await run_llm_pass_with_validation(
                llm_service=llm_service,
                strict_service=strict_service,
                user_id=user_id,
                system=decomp_system,
                user=decomp_prompt,
                schema=Pass2DecompOutput,
                task_type=TaskType.DECOMPOSITION,
                pass_metrics=metrics.pass_2,
                quality_mode=quality_mode,
                pass_name="Pass2-Decomp"
            )
            
            if not decomp_result:
                metrics.error_message = "Failed to decompose features"
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
                        acceptance_criteria=s_data.get('acceptance_criteria', []),
                        labels=s_data.get('labels', []),
                        priority=s_data.get('priority', feature.priority),  # Inherit from feature
                        dependencies=s_data.get('dependencies', []),
                        risks=s_data.get('risks', [])
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
            
            # Format planning system with context
            planning_system = PLANNING_SYSTEM.format(
                context=context_prompt,
                velocity=ctx['velocity'],
                sprint_length=ctx['sprint_length']
            )
            
            planning_prompt = PLANNING_USER.format(
                product_name=product_name,
                desired_outcome=prd_data.get('desired_outcome', ''),
                sprint_length=ctx['sprint_length'],
                velocity=ctx['velocity'],
                num_devs=ctx.get('num_devs', 3),
                num_qa=ctx.get('num_qa', 1),
                stories_list=stories_list
            )
            
            # Use strict output with schema validation (low temperature for planning)
            planning_result = await run_llm_pass_with_validation(
                llm_service=llm_service,
                strict_service=strict_service,
                user_id=user_id,
                system=planning_system,
                user=planning_prompt,
                schema=Pass3PlanningOutput,
                task_type=TaskType.PLANNING,
                pass_metrics=metrics.pass_3,
                quality_mode="standard",  # No quality pass for planning - must be deterministic
                pass_name="Pass3-Planning"
            )
            
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
                    ac_preview = '; '.join(s.acceptance_criteria[:3]) if s.acceptance_criteria else 'None'
                    stories_detail += f"    AC: {ac_preview}\n"
            
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
            target_points = ctx['velocity'] * 2  # 2 sprints
            
            # Format critic system with context
            critic_system = CRITIC_SYSTEM.format(
                context=context_prompt,
                velocity=ctx['velocity']
            )
            
            critic_prompt = CRITIC_USER.format(
                product_name=product_name,
                industry=ctx['industry'],
                problem_statement=prd_data.get('problem_statement', ''),
                target_users=prd_data.get('target_users', ''),
                metrics=', '.join(prd_data.get('key_metrics', [])),
                stories_detail=stories_detail,
                methodology=ctx['methodology'],
                sprint_length=ctx['sprint_length'],
                velocity=ctx['velocity'],
                sprint1_points=sprint1_points,
                sprint2_points=sprint2_points,
                total_points=total_points,
                target_points=target_points
            )
            
            # Use strict output with schema validation (very low temp for analytical critic)
            critic_result = await run_llm_pass_with_validation(
                llm_service=llm_service,
                strict_service=strict_service,
                user_id=user_id,
                system=critic_system,
                user=critic_prompt,
                schema=Pass4CriticOutput,
                task_type=TaskType.CRITIC,
                pass_metrics=metrics.pass_4,
                quality_mode="standard",  # No quality pass for critic
                pass_name="Pass4-Critic"
            )
            
            # Apply critic fixes
            warnings = []
            if critic_result:
                fixes = critic_result.get('fixes', {})
                issues = critic_result.get('issues', [])
                summary = critic_result.get('summary', {})
                
                # Track critic metrics
                metrics.critic_issues_found = summary.get('total_issues', len(issues))
                metrics.critic_auto_fixed = summary.get('auto_fixed', 0)
                metrics.scope_assessment = summary.get('scope_assessment')
                
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
            
            # Update metrics for successful generation
            metrics.success = True
            metrics.features_generated = len(initiative.features)
            metrics.stories_generated = sum(len(f.stories) for f in initiative.features)
            metrics.total_points = initiative.total_points
            
            # Build final response with warnings and context
            response_data = initiative.model_dump()
            if warnings:
                response_data['warnings'] = warnings
            if critic_result and critic_result.get('summary'):
                response_data['quality_summary'] = critic_result['summary']
            
            # Add confidence assessment from critic (premium PM feature)
            if critic_result and critic_result.get('confidence_assessment'):
                response_data['confidence_assessment'] = critic_result['confidence_assessment']
            
            # Add delivery context for UI personalization
            response_data['delivery_context'] = {
                'industry': ctx['industry'],
                'methodology': ctx['methodology'],
                'sprint_length': ctx['sprint_length'],
                'team_velocity': ctx['velocity'],
                'team_size': ctx['team_size'],
                'platform': ctx['platform'],
                'definition_of_done': dod
            }
            
            # Save analytics (fire and forget - don't block response)
            try:
                log_id = await analytics.save_generation_log(metrics)
                response_data['_analytics'] = {'log_id': log_id}
            except Exception as e:
                logger.warning(f"Failed to save analytics: {e}")
            
            # Send final result
            yield f"data: {json.dumps({'type': 'initiative', 'data': response_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'message': 'Initiative generated!'})}\n\n"
            
        except Exception as e:
            logger.error(f"Initiative generation failed: {e}", exc_info=True)
            # Save failed generation metrics
            try:
                metrics.error_message = str(e)
                await analytics.save_generation_log(metrics)
            except Exception:
                pass
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
                    labels=story_data.labels,
                    story_priority=story_data.priority,
                    dependencies=story_data.dependencies,
                    risks=story_data.risks,
                    current_stage="draft",
                    story_points=story_data.points,
                    priority=j,  # Use priority for ordering
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
        "prompt_version": CURRENT_PROMPT_VERSION,
        "schema": InitiativeSchema.model_json_schema()
    }


# ============================================
# Analytics Endpoints (Private - Admin only in future)
# ============================================

@router.get("/analytics/stats")
async def get_generation_stats(
    request: Request,
    days: int = 30,
    session: AsyncSession = Depends(get_db)
):
    """
    Get aggregated generation statistics.
    Returns: success rates, token usage, costs, provider breakdown.
    """
    user_id = await get_current_user_id(request, session)
    
    analytics = AnalyticsService(session)
    stats = await analytics.get_generation_stats(days=days, user_id=user_id)
    
    return stats


@router.get("/analytics/edit-patterns")
async def get_edit_patterns(
    request: Request,
    days: int = 30,
    session: AsyncSession = Depends(get_db)
):
    """
    Get patterns of what users edit most after generation.
    Helps identify areas for prompt improvement.
    """
    user_id = await get_current_user_id(request, session)
    
    analytics = AnalyticsService(session)
    patterns = await analytics.get_edit_patterns(days=days, user_id=user_id)
    
    return patterns
