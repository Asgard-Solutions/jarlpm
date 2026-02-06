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
from db.models import Epic, EpicSnapshot, EpicStage, Subscription, SubscriptionStatus, ProductDeliveryContext
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


# --- Pass 3: Critic Output Schema ---
# NOTE: Old Pass 3 (Planning) was removed - scoring happens via Scoring/Poker features
class Pass3CriticOutput(BaseModel):
    """Schema for Pass 3 (Critic) output validation"""
    issues: List[dict] = Field(default_factory=list)
    fixes: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    
    class Config:
        extra = "allow"


class StorySchema(BaseModel):
    """Export-ready user story schema with all fields needed for Jira/Azure DevOps/Linear export"""
    id: str = Field(default_factory=lambda: generate_id("story_"))
    title: str  # Short, actionable title
    description: str = ""  # PM-level context: success criteria, non-goals, edge cases
    persona: str
    action: str
    benefit: str
    acceptance_criteria: List[str] = Field(default_factory=list)  # Gherkin format: Given/When/Then
    labels: List[str] = Field(default_factory=list)  # e.g., ["backend", "api", "auth", "mvp"]
    priority: str = "should-have"  # must-have, should-have, nice-to-have (feature priority, NOT scoring)
    dependencies: List[str] = Field(default_factory=list)  # Story IDs or descriptions
    risks: List[str] = Field(default_factory=list)  # Risk descriptions
    
    # Senior PM-level fields
    success_criteria: str = ""  # What "done" looks like beyond AC
    non_goals: List[str] = Field(default_factory=list)  # What this story explicitly does NOT do
    edge_cases: List[str] = Field(default_factory=list)  # Edge cases to handle or explicitly ignore
    ux_notes: str = ""  # UX considerations, loading states, error handling
    instrumentation: List[str] = Field(default_factory=list)  # Analytics events/metrics to track
    notes_for_engineering: str = ""  # Technical tradeoffs, data storage, perf/security considerations
    
    # NOTE: story_points, RICE scores, and MoSCoW are NOT included here.
    # Those are only assigned via Scoring or Poker Planning features, not during creation.
    
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


class UserPersonaSchema(BaseModel):
    """Detailed user persona for PM-quality PRDs"""
    persona: str = ""  # e.g., "Busy pharmacy manager"
    context: str = ""  # e.g., "Managing a small independent pharmacy with 2-3 staff"
    pain_points: List[str] = Field(default_factory=list)  # Specific frustrations
    current_workaround: str = ""  # How they solve this today
    jtbd: str = ""  # Job-to-be-done framing


class ConstraintSchema(BaseModel):
    """Product constraint with rationale"""
    constraint: str = ""
    rationale: str = ""
    impact: str = ""  # high/medium/low


class AssumptionSchema(BaseModel):
    """Assumption that needs validation"""
    assumption: str = ""
    risk_if_wrong: str = ""
    validation_approach: str = ""


class PositioningSchema(BaseModel):
    """Competitive positioning statement"""
    for_who: str = ""  # Target user
    who_struggle_with: str = ""  # Current problem
    our_solution: str = ""  # Product name/type
    unlike: str = ""  # Key competitor or alternative
    key_benefit: str = ""  # Primary differentiator


class MVPScopeItemSchema(BaseModel):
    """MVP scope item with rationale"""
    item: str = ""
    rationale: str = ""


class PRDSchema(BaseModel):
    """Senior PM-quality PRD schema with depth for teams without a PM"""
    # Core problem definition
    problem_statement: str = ""  # 2-4 sentences, specific and actionable
    problem_evidence: str = ""  # Data/quotes/research supporting the problem
    
    # User understanding (rich, structured)
    target_users: List[UserPersonaSchema] = Field(default_factory=list)
    
    # Success definition
    desired_outcome: str = ""  # What success looks like
    key_metrics: List[str] = Field(default_factory=list)  # Measurable KPIs
    
    # Scope boundaries with rationale
    mvp_scope: List[MVPScopeItemSchema] = Field(default_factory=list)  # What's IN MVP
    not_now: List[MVPScopeItemSchema] = Field(default_factory=list)  # What's OUT with rationale
    out_of_scope: List[str] = Field(default_factory=list)  # Hard boundaries (legacy field)
    
    # Risk and validation
    assumptions: List[AssumptionSchema] = Field(default_factory=list)
    constraints: List[ConstraintSchema] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)  # Legacy field
    riskiest_unknown: str = ""  # Single biggest uncertainty
    validation_plan: str = ""  # How to de-risk before full build
    
    # Market context
    positioning: PositioningSchema = Field(default_factory=PositioningSchema)
    alternatives: List[str] = Field(default_factory=list)  # Competitor/workaround list
    
    # Optional GTM notes
    gtm_notes: str = ""  # Go-to-market considerations


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
    # NOTE: sprint_plan and total_points removed - scoring happens via Scoring/Poker features
    
    def assign_ids(self):
        """Ensure all entities have stable IDs"""
        for feature in self.features:
            if not feature.id or not feature.id.startswith('feat_'):
                feature.id = generate_id('feat_')
            for story in feature.stories:
                if not story.id or not story.id.startswith('story_'):
                    story.id = generate_id('story_')
        return self


class NewInitiativeRequest(BaseModel):
    idea: str
    product_name: Optional[str] = None
    quality_mode: Optional[str] = None  # "standard" or "quality" - overrides delivery context setting


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
        "\nORGANIZATION CONTEXT:",
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

PRD_SYSTEM = """You are JarlPM, a Senior Product Manager creating production-ready PRDs for teams that don't have a PM.

Your output must be comprehensive enough that an engineering team can build confidently without ambiguity.

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
  "tagline": "one-line pitch that captures the value prop",
  "prd": {{
    "problem_statement": "2-4 sentences describing the core problem with specificity. Include who feels the pain and when.",
    "problem_evidence": "Data, quotes, or research that validates this problem exists. Be specific.",
    "target_users": [
      {{
        "persona": "Specific role/type (e.g., 'Independent pharmacy owner')",
        "context": "Their situation (team size, industry, workflow)",
        "pain_points": ["Specific frustration 1", "Specific frustration 2"],
        "current_workaround": "How they solve this today (manual process, competitor, spreadsheet, etc.)",
        "jtbd": "When [situation], I want to [motivation], so I can [outcome]"
      }}
    ],
    "desired_outcome": "What success looks like in measurable, observable terms",
    "key_metrics": [
      "Primary metric with target (e.g., 'Reduce message response time from 4hr to <30min')",
      "Secondary metric with target",
      "Leading indicator"
    ],
    "mvp_scope": [
      {{"item": "Core capability 1", "rationale": "Why this is essential for MVP"}},
      {{"item": "Core capability 2", "rationale": "Why this is essential for MVP"}}
    ],
    "not_now": [
      {{"item": "Deferred feature 1", "rationale": "Why we're deferring (complexity, uncertainty, dependency)"}},
      {{"item": "Deferred feature 2", "rationale": "Why we're deferring"}}
    ],
    "assumptions": [
      {{
        "assumption": "What we believe is true but haven't validated",
        "risk_if_wrong": "Impact if this assumption is false",
        "validation_approach": "How we'll test this (user interview, prototype, data analysis)"
      }}
    ],
    "constraints": [
      {{
        "constraint": "Technical, business, or timeline constraint",
        "rationale": "Why this constraint exists",
        "impact": "high | medium | low"
      }}
    ],
    "riskiest_unknown": "The single biggest uncertainty that could derail the project",
    "validation_plan": "Concrete steps to de-risk before full build (spike, prototype, interviews)",
    "positioning": {{
      "for_who": "Target user segment",
      "who_struggle_with": "The problem they face",
      "our_solution": "Product name/category",
      "unlike": "Primary alternative or competitor",
      "key_benefit": "Primary differentiator"
    }},
    "alternatives": ["Competitor 1 or workaround", "Competitor 2 or alternative approach"],
    "gtm_notes": "Brief notes on go-to-market approach (optional but valuable)"
  }},
  "epic": {{
    "title": "Epic title for this initiative",
    "description": "2-3 sentence epic description covering the what and why",
    "vision": "Product vision statement (aspirational, future-focused)"
  }}
}}

QUALITY REQUIREMENTS:
- problem_statement: Must be specific enough that someone outside your company understands the pain
- target_users: At least 1 detailed persona with all fields populated
- key_metrics: 3-5 metrics, each MUST include a target number, %, $, or timeframe
- mvp_scope: 3-5 items with clear rationale for inclusion
- not_now: 2-4 items explaining what's being deferred and WHY
- assumptions: 2-4 assumptions with validation approaches
- constraints: 1-3 real constraints (not generic "limited budget")
- riskiest_unknown: Be specific - what's the one thing that keeps you up at night?
- positioning: Complete the "For [who], who [problem], our [product] is a [category] that [benefit], unlike [alternative]" framework

Focus on creating a PRD that enables confident decision-making. Depth over brevity."""


PRD_USER = """Create a comprehensive PRD for this idea:

{idea}

{name_hint}

Generate a Senior PM-quality PRD with:
- Specific user personas with pain points and current workarounds
- Clear MVP scope with rationale for what's in and what's deferred
- Assumptions that need validation with concrete approaches
- Real constraints and their impact
- Competitive positioning

Return only valid JSON matching the schema. No markdown fences, no commentary."""


# ============================================
# Pass 2: Feature Decomposition
# ============================================

DECOMP_SYSTEM = """You are JarlPM, a Senior Product Manager. Given a PRD, decompose it into features and user stories with enough detail that engineers can build confidently without a PM in the room.
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
      "description": "What it does and why it matters (2-3 sentences)",
      "priority": "must-have | should-have | nice-to-have",
      "stories": [
        {{
          "title": "Short, actionable title (5-10 words)",
          "description": "PM-level context: what success looks like, key behaviors, important edge cases to consider (2-4 sentences)",
          "persona": "a [specific user type]",
          "action": "[what they want to do]",
          "benefit": "[why they want it]",
          "acceptance_criteria": [
            "Given X, When Y, Then Z",
            "Given A, When B, Then C"
          ],
          "success_criteria": "What 'done' looks like beyond the AC - the real-world outcome",
          "non_goals": ["What this story explicitly does NOT do", "Scope boundary"],
          "edge_cases": ["Edge case to handle", "Edge case to explicitly ignore with reason"],
          "ux_notes": "Loading states, error messages, empty states, accessibility considerations",
          "instrumentation": ["track_event: user_did_X", "metric: time_to_complete_Y"],
          "notes_for_engineering": "Technical tradeoffs, data storage approach, perf/security considerations, known constraints",
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

STORY QUALITY REQUIREMENTS:
- description: Concrete context, not just restating the title. Include the "why" and key behaviors.
- success_criteria: Observable outcome (e.g., "User can send 100+ messages/day without errors")
- non_goals: At least 1 scope boundary per story (what you're NOT building)
- edge_cases: At least 1 edge case to handle OR explicitly note "out of scope for MVP"
- ux_notes: Required for any frontend-touching story (loading, errors, empty states)
- instrumentation: At least 1 analytics event for must-have stories
- notes_for_engineering: Required for backend/api stories (data model hints, API design, perf considerations)

PRIORITY RULES:
- must-have: Required for launch, no workarounds
- should-have: Important, but can launch without
- nice-to-have: Enhances UX, defer if needed

Write stories that would make a senior engineer say "I know exactly what to build"."""


DECOMP_USER = """Decompose this PRD into features and user stories with Senior PM-level detail:

PRODUCT: {product_name}
TAGLINE: {tagline}

PROBLEM: {problem_statement}
USERS: {target_users}
OUTCOME: {desired_outcome}

OUT OF SCOPE: {out_of_scope}

{dod_section}

Generate features with detailed user stories including:
- Rich descriptions with context and key behaviors
- Clear success criteria and non-goals
- Edge cases to handle or explicitly defer
- UX notes for frontend stories
- Instrumentation/analytics events
- Engineering notes with technical considerations

IMPORTANT: Include at least 1 NFR story for security, performance, or reliability.
Return only valid JSON. No markdown fences, no commentary."""


# ============================================
# Pass 3: PM Reality Check (Critic)
# NOTE: Pass 3 (Planning) was removed - scoring happens via Scoring/Poker features
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
      "type": "metric_not_measurable | ac_not_testable | missing_nfr | scope_risk | other",
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
    "added_nfr_stories": [
      {{
        "title": "NFR story title",
        "persona": "a developer",
        "action": "...",
        "benefit": "...",
        "acceptance_criteria": ["Given X, When Y, Then Z"],
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
3. NFRs: Is there at least 1 security/performance/reliability story?
4. Dependencies: Are there any circular or missing dependencies?
5. Story quality: Are descriptions clear? Are acceptance criteria testable?

NOTE: Story points and sprint planning are NOT part of this review. 
Points are assigned later via Scoring or Poker Planning features.

HARD CONSTRAINTS:
- ALWAYS return all top-level keys: issues, fixes, summary, confidence_assessment
- If no fixes needed, return empty arrays/objects (not null, not omitted)
- confidence_score: integer 0-100
- top_risks: exactly 3 items
- key_assumptions: exactly 3 items
- validate_first: exactly 3 items

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

Review for: industry-appropriate metrics, testable ACs, missing NFRs, clear descriptions.
NOTE: Do NOT assess story points or sprint capacity - those are handled separately via Scoring/Poker.
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
    DEPRECATED: Use run_llm_pass_with_validation_sessionless instead.
    This function holds DB sessions open during LLM streaming and should not be used.
    Kept for reference only.
    """
    # Log deprecation warning
    logger.warning(f"DEPRECATED: run_llm_pass_with_validation called from {pass_name}. Use sessionless version instead.")
    return None


async def run_llm_pass_with_validation_sessionless(
    config_data: dict,
    strict_service: StrictOutputService,
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
    This version does NOT hold a DB session - uses pre-fetched config_data.
    
    Features:
    - Uses task-specific temperature for guardrails
    - Validates against Pydantic schema
    - Auto-repairs invalid JSON (up to 2 retries)
    - Optionally runs quality pass for 2-pass mode
    - Tracks all metrics for analytics
    """
    start_time = time.time()
    temperature = strict_service.get_temperature(task_type)
    
    logger.info(f"[{pass_name}] Starting (sessionless) with temp={temperature}, schema={schema.__name__}")
    
    # Create session-less LLM service for streaming
    llm = LLMService()  # No session needed
    
    # Collect full response
    full_response = ""
    async for chunk in llm.stream_with_config(
        config_data=config_data,
        system_prompt=system,
        user_prompt=user,
        conversation_history=None,
        temperature=temperature
    ):
        full_response += chunk
    
    logger.debug(f"[{pass_name}] Got {len(full_response)} chars response")
    
    # Define repair callback (also sessionless)
    async def repair_callback(repair_prompt: str) -> str:
        logger.info(f"[{pass_name}] Attempting repair...")
        repair_response = ""
        repair_llm = LLMService()  # No session
        async for chunk in repair_llm.stream_with_config(
            config_data=config_data,
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
        quality_llm = LLMService()  # No session
        async for chunk in quality_llm.stream_with_config(
            config_data=config_data,
            system_prompt="You are a quality reviewer. Improve the output while keeping the same JSON structure. Return ONLY the improved JSON, no commentary.",
            user_prompt=quality_prompt,
            conversation_history=None,
            temperature=0.3
        ):
            quality_response += chunk
        
        # Extract and RE-VALIDATE the improved JSON against the schema
        improved_data = strict_service.extract_json(quality_response)
        if improved_data:
            # Re-validate to ensure quality pass didn't break structure
            async def quality_repair_callback(repair_prompt: str) -> str:
                repair_response = ""
                qr_llm = LLMService()  # No session
                async for chunk in qr_llm.stream_with_config(
                    config_data=config_data,
                    system_prompt="Fix the JSON to match the required schema. Return ONLY valid JSON.",
                    user_prompt=repair_prompt,
                    conversation_history=None,
                    temperature=0.1
                ):
                    repair_response += chunk
                return repair_response
            
            quality_validation = await strict_service.validate_and_repair(
                raw_response=quality_response,
                schema=schema,
                repair_callback=quality_repair_callback,
                max_repairs=1,  # One repair attempt for quality pass
                original_prompt=quality_prompt
            )
            
            if quality_validation.valid:
                result.data = quality_validation.data
                logger.info(f"[{pass_name}] Quality pass improved and validated output")
            else:
                # Quality pass broke structure - keep original valid result
                logger.warning(f"[{pass_name}] Quality pass failed validation, keeping original: {quality_validation.errors[:2]}")
        else:
            logger.warning(f"[{pass_name}] Quality pass returned no valid JSON, keeping original")
    
    # Update metrics
    if pass_metrics:
        pass_metrics.tokens_in = len(system + user) // 4
        pass_metrics.tokens_out = len(full_response) // 4
        pass_metrics.retries = result.repair_attempts
        pass_metrics.duration_ms = int((time.time() - start_time) * 1000)
        pass_metrics.success = result.valid
        if not result.valid:
            pass_metrics.error = "; ".join(result.errors[:2])
    
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
    """
    DEPRECATED: Use run_llm_pass_with_validation_sessionless instead.
    This function holds DB sessions open during LLM streaming and should not be used.
    Kept for reference only.
    """
    # Log deprecation warning
    logger.warning("DEPRECATED: run_llm_pass called. Use sessionless version instead.")
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
    NOTE: Uses session-less streaming to avoid DB pool exhaustion.
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
    
    # Prepare for streaming - extract all needed data BEFORE releasing session
    config_data = llm_service.prepare_for_streaming(llm_config)
    
    # Initialize strict output service (doesn't need session for validation)
    strict_service = get_strict_output_service(None)
    
    # Check for weak model warning - capture the value before streaming
    strict_service_with_session = get_strict_output_service(session)
    model_warning = await strict_service_with_session.get_model_warning(
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
    
    # Get quality mode - request body overrides delivery context
    if body.quality_mode and body.quality_mode in ("standard", "quality"):
        quality_mode = body.quality_mode
    elif delivery_context and delivery_context.quality_mode:
        quality_mode = delivery_context.quality_mode
    else:
        quality_mode = "standard"
    
    # Initialize analytics and capture metrics structure
    # Note: We'll save analytics after streaming with a fresh session
    metrics_data = {
        "user_id": user_id,
        "idea": body.idea,
        "product_name_provided": bool(body.product_name),
        "llm_provider": llm_config.provider,
        "model_name": llm_config.model_name,
        "delivery_context": ctx
    }
    
    # Pre-capture all the data we need for the streaming generator
    request_idea = body.idea
    request_product_name = body.product_name

    async def generate():
        # Create local metrics tracking (will save to DB at the end with a fresh session)
        metrics = GenerationMetrics(
            user_id=user_id,
            idea=request_idea,
            product_name_provided=bool(request_product_name),
            llm_provider=metrics_data["llm_provider"],
            model_name=metrics_data["model_name"],
        )
        
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
                idea=request_idea,
                name_hint=f"Product name hint: {request_product_name}" if request_product_name else ""
            )
            
            # Format PRD system prompt with context
            prd_system = PRD_SYSTEM.format(context=context_prompt)
            
            # Use sessionless strict output with schema validation
            prd_result = await run_llm_pass_with_validation_sessionless(
                config_data=config_data,
                strict_service=strict_service,
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
            product_name = prd_result.get('product_name', request_product_name or 'New Product')
            tagline = prd_result.get('tagline', '')
            prd_data = prd_result.get('prd', {})
            epic_data = prd_result.get('epic', {})
            
            yield f"data: {json.dumps({'type': 'progress', 'pass': 1, 'message': f'PRD complete: {product_name}'})}\n\n"
            
            # ========== PASS 2: DECOMPOSITION ==========
            yield f"data: {json.dumps({'type': 'pass', 'pass': 2, 'message': 'Breaking down features...'})}\n\n"
            
            # Build DoD section
            dod_section = "DEFINITION OF DONE:\n" + "\n".join(f"- {d}" for d in dod)
            
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
            
            # Use sessionless strict output with schema validation
            decomp_result = await run_llm_pass_with_validation_sessionless(
                config_data=config_data,
                strict_service=strict_service,
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
            
            # ========== PASS 3: PM REALITY CHECK ==========
            # NOTE: Planning pass was removed - scoring happens via Scoring/Poker features
            yield f"data: {json.dumps({'type': 'pass', 'pass': 3, 'message': 'Running PM quality checks...'})}\n\n"
            
            # Build detailed stories list for critic
            stories_detail = ""
            for f in features:
                stories_detail += f"\n[{f.priority.upper()}] {f.name}: {f.description}\n"
                for s in f.stories:
                    stories_detail += f"  • {s.id}: {s.title}\n"
                    stories_detail += f"    As {s.persona}, I want to {s.action} so that {s.benefit}\n"
                    ac_preview = '; '.join(s.acceptance_criteria[:3]) if s.acceptance_criteria else 'None'
                    stories_detail += f"    AC: {ac_preview}\n"
            
            # Format critic system with context
            critic_system = CRITIC_SYSTEM.format(
                context=context_prompt
            )
            
            critic_prompt = CRITIC_USER.format(
                product_name=product_name,
                industry=ctx['industry'],
                problem_statement=prd_data.get('problem_statement', ''),
                target_users=prd_data.get('target_users', ''),
                metrics=', '.join(prd_data.get('key_metrics', [])),
                stories_detail=stories_detail,
                methodology=ctx['methodology']
            )
            
            # Use sessionless strict output with schema validation (very low temp for analytical critic)
            critic_result = await run_llm_pass_with_validation_sessionless(
                config_data=config_data,
                strict_service=strict_service,
                system=critic_system,
                user=critic_prompt,
                schema=Pass3CriticOutput,
                task_type=TaskType.CRITIC,
                pass_metrics=metrics.pass_3,
                quality_mode="standard",  # No quality pass for critic
                pass_name="Pass3-Critic"
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
                            acceptance_criteria=nfr_data.get('acceptance_criteria', [])
                            # NOTE: No points - scoring happens via Scoring/Poker features
                        )
                        nfr_feature.stories.append(nfr_story)
                
                auto_fixed_count = summary.get('auto_fixed', 0)
                yield f"data: {json.dumps({'type': 'progress', 'pass': 3, 'message': f'Quality check complete: {auto_fixed_count} auto-fixes applied'})}\n\n"
            else:
                summary = {}
                logger.warning("Critic pass failed, skipping quality checks")
                yield f"data: {json.dumps({'type': 'progress', 'pass': 3, 'message': 'Quality check skipped'})}\n\n"
            
            # ========== BUILD FINAL OUTPUT ==========
            initiative = InitiativeSchema(
                product_name=product_name,
                tagline=tagline,
                prd=PRDSchema(**prd_data),
                epic=EpicSchema(**epic_data),
                features=features
                # NOTE: sprint_plan removed - scoring happens via Scoring/Poker features
            )
            initiative.assign_ids()
            
            # Update metrics for successful generation
            metrics.success = True
            metrics.features_generated = len(initiative.features)
            metrics.stories_generated = sum(len(f.stories) for f in initiative.features)
            # NOTE: total_points not tracked - scoring happens via Scoring/Poker features
            
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
            
            # Save analytics with a fresh session (fire and forget - don't block response)
            try:
                from db import AsyncSessionLocal
                async with AsyncSessionLocal() as new_session:
                    new_analytics = AnalyticsService(new_session)
                    log_id = await new_analytics.save_generation_log(metrics)
                    response_data['_analytics'] = {'log_id': log_id}
            except Exception as e:
                logger.warning(f"Failed to save analytics: {e}")
            
            # Send final result
            yield f"data: {json.dumps({'type': 'initiative', 'data': response_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'message': 'Initiative generated!'})}\n\n"
            
        except Exception as e:
            logger.error(f"Initiative generation failed: {e}", exc_info=True)
            # Save failed generation metrics with a fresh session
            try:
                metrics.error_message = str(e)
                from db import AsyncSessionLocal
                async with AsyncSessionLocal() as new_session:
                    new_analytics = AnalyticsService(new_session)
                    await new_analytics.save_generation_log(metrics)
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
            current_stage=EpicStage.EPIC_LOCKED.value,  # New initiatives start as locked
            created_at=now,
            updated_at=now
        )
        session.add(epic)
        
        # Create snapshot with PRD data
        snapshot = EpicSnapshot(
            epic_id=epic.epic_id,
            problem_statement=validated.prd.problem_statement,
            desired_outcome=validated.prd.desired_outcome,
            epic_summary=f"{validated.epic.vision}\n\nTarget Users: {validated.prd.target_users}\n\nOut of Scope: {', '.join(validated.prd.out_of_scope)}\n\nRisks: {', '.join(validated.prd.risks)}\n\nKey Metrics: {', '.join(validated.prd.key_metrics)}",
            acceptance_criteria=[],  # Acceptance criteria at epic level
            # Lock the epic since it's being created from a complete initiative
            problem_confirmed_at=now,
            outcome_confirmed_at=now,
            epic_locked_at=now,
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
                title=feat_data.name,
                description=feat_data.description,
                acceptance_criteria=[],
                current_stage="approved",  # Features from initiative are pre-approved
                source="ai_generated",
                priority=i,
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
                    source="ai_generated",
                    story_points=story_data.points,
                    priority=j,
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
