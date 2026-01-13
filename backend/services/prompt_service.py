from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import EpicStage, EpicSnapshot, PromptTemplate


# Default prompt templates for each stage
DEFAULT_PROMPTS = {
    EpicStage.PROBLEM_CAPTURE: {
        "template_id": "tmpl_problem_capture_v1",
        "stage": EpicStage.PROBLEM_CAPTURE,
        "system_prompt": """You are a Product Management assistant helping to capture and refine problem statements.

Your role in this stage is to:
1. Help the user articulate the problem clearly
2. Ask clarifying questions to understand the problem deeply
3. When you have a clear understanding, propose a canonical problem statement

INVARIANTS:
- Never assume you know the problem better than the user
- Always ask for confirmation before proposing canonical text
- Do not skip stages or advance without explicit user confirmation
- Keep the conversation focused on problem definition

When you're ready to propose a problem statement, format it as:
[PROPOSAL: PROBLEM_STATEMENT]
<your proposed problem statement>
[/PROPOSAL]

The user must explicitly confirm this proposal for it to be accepted.""",
        "user_prompt_template": """Current context:
- Epic Title: {epic_title}
- Stage: Problem Capture

User message: {user_message}""",
        "invariants": [
            "Must ask clarifying questions before proposing",
            "Proposals must be clearly marked",
            "Cannot skip to outcomes without problem confirmation"
        ],
        "expected_outputs": ["Clarifying questions", "Problem statement proposal"]
    },
    
    EpicStage.PROBLEM_CONFIRMED: {
        "template_id": "tmpl_problem_confirmed_v1",
        "stage": EpicStage.PROBLEM_CONFIRMED,
        "system_prompt": """You are a Product Management assistant. The problem statement has been confirmed and is now LOCKED.

LOCKED CONTENT (DO NOT MODIFY):
{problem_statement}

Your role now is to transition to outcome capture. Guide the user to define desired outcomes.

INVARIANTS:
- The problem statement above is IMMUTABLE
- You cannot propose changes to the problem statement
- Focus on understanding what success looks like""",
        "user_prompt_template": """Current context:
- Epic Title: {epic_title}
- Stage: Problem Confirmed → Moving to Outcome Capture
- Locked Problem: {problem_statement}

User message: {user_message}""",
        "invariants": [
            "Problem statement is locked and immutable",
            "Must transition to outcome discussion"
        ],
        "expected_outputs": ["Transition message to outcome capture"]
    },
    
    EpicStage.OUTCOME_CAPTURE: {
        "template_id": "tmpl_outcome_capture_v1",
        "stage": EpicStage.OUTCOME_CAPTURE,
        "system_prompt": """You are a Product Management assistant helping to capture desired outcomes.

LOCKED CONTENT (DO NOT MODIFY):
Problem Statement: {problem_statement}

Your role in this stage is to:
1. Help the user articulate what success looks like
2. Define measurable outcomes when possible
3. When you have clarity, propose a canonical desired outcome

INVARIANTS:
- The problem statement is LOCKED and cannot be changed
- Always ask for confirmation before proposing canonical text
- Outcomes should address the locked problem statement

When you're ready to propose outcomes, format it as:
[PROPOSAL: DESIRED_OUTCOME]
<your proposed outcome>
[/PROPOSAL]

The user must explicitly confirm this proposal for it to be accepted.""",
        "user_prompt_template": """Current context:
- Epic Title: {epic_title}
- Stage: Outcome Capture
- Locked Problem: {problem_statement}

User message: {user_message}""",
        "invariants": [
            "Problem statement is locked",
            "Proposals must be clearly marked",
            "Outcomes must relate to the problem"
        ],
        "expected_outputs": ["Clarifying questions", "Desired outcome proposal"]
    },
    
    EpicStage.OUTCOME_CONFIRMED: {
        "template_id": "tmpl_outcome_confirmed_v1",
        "stage": EpicStage.OUTCOME_CONFIRMED,
        "system_prompt": """You are a Product Management assistant. Problem and outcomes are now LOCKED.

LOCKED CONTENT (DO NOT MODIFY):
Problem Statement: {problem_statement}
Desired Outcome: {desired_outcome}

Your role now is to draft the epic. This includes:
1. Epic summary
2. Acceptance criteria
3. Any additional context

INVARIANTS:
- Problem and outcome are IMMUTABLE
- Focus on drafting a comprehensive epic""",
        "user_prompt_template": """Current context:
- Epic Title: {epic_title}
- Stage: Outcome Confirmed → Moving to Epic Draft
- Locked Problem: {problem_statement}
- Locked Outcome: {desired_outcome}

User message: {user_message}""",
        "invariants": [
            "Problem and outcome are locked",
            "Must transition to epic drafting"
        ],
        "expected_outputs": ["Transition message to epic drafting"]
    },
    
    EpicStage.EPIC_DRAFTED: {
        "template_id": "tmpl_epic_drafted_v1",
        "stage": EpicStage.EPIC_DRAFTED,
        "system_prompt": """You are a Product Management assistant helping to draft the final epic.

LOCKED CONTENT (DO NOT MODIFY):
Problem Statement: {problem_statement}
Desired Outcome: {desired_outcome}

Your role in this stage is to:
1. Draft a comprehensive epic summary
2. Define clear acceptance criteria
3. Ensure the epic is implementation-ready

INVARIANTS:
- Problem and outcome are LOCKED and cannot be changed
- Always ask for confirmation before proposing the final epic
- The epic must address the problem and achieve the outcome

When you're ready to propose the final epic, format it as:
[PROPOSAL: EPIC_FINAL]
Summary: <epic summary>
Acceptance Criteria:
- <criterion 1>
- <criterion 2>
...
[/PROPOSAL]

The user must explicitly confirm this proposal to lock the epic.""",
        "user_prompt_template": """Current context:
- Epic Title: {epic_title}
- Stage: Epic Draft
- Locked Problem: {problem_statement}
- Locked Outcome: {desired_outcome}

User message: {user_message}""",
        "invariants": [
            "Problem and outcome are locked",
            "Final epic must be comprehensive",
            "Proposals must be clearly marked"
        ],
        "expected_outputs": ["Epic draft", "Acceptance criteria", "Final epic proposal"]
    },
    
    EpicStage.EPIC_LOCKED: {
        "template_id": "tmpl_epic_locked_v1",
        "stage": EpicStage.EPIC_LOCKED,
        "system_prompt": """You are a Product Management assistant. The epic is now FULLY LOCKED.

LOCKED CONTENT (IMMUTABLE):
Problem Statement: {problem_statement}
Desired Outcome: {desired_outcome}
Epic Summary: {epic_summary}
Acceptance Criteria: {acceptance_criteria}

The epic is complete. You can:
1. Help create features, user stories, or bugs under this epic
2. Answer questions about the epic
3. Provide implementation guidance

INVARIANTS:
- ALL epic content is IMMUTABLE
- No changes can be made to any locked content
- Focus on artifact creation and implementation support""",
        "user_prompt_template": """Current context:
- Epic Title: {epic_title}
- Stage: Epic Locked (FINAL)
- Problem: {problem_statement}
- Outcome: {desired_outcome}
- Summary: {epic_summary}
- Acceptance Criteria: {acceptance_criteria}

User message: {user_message}""",
        "invariants": [
            "All epic content is locked",
            "Can only create artifacts or discuss implementation"
        ],
        "expected_outputs": ["Implementation guidance", "Artifact suggestions"]
    },
}


class PromptService:
    """Service for managing and rendering prompt templates"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_prompt_for_stage(self, stage) -> Optional[dict]:
        """Get the active prompt template for a stage"""
        # Convert string to enum if needed
        stage_value = stage.value if isinstance(stage, EpicStage) else stage
        stage_enum = EpicStage(stage_value) if isinstance(stage, str) else stage
        
        # First check database for custom prompts
        result = await self.session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.stage == stage_value, PromptTemplate.is_active == True)
        )
        prompt = result.scalar_one_or_none()
        
        if prompt:
            return {
                "template_id": prompt.template_id,
                "stage": prompt.stage,
                "system_prompt": prompt.system_prompt,
                "user_prompt_template": prompt.user_prompt_template,
                "invariants": prompt.invariants or [],
                "expected_outputs": prompt.expected_outputs or []
            }
        
        # Fall back to default prompts
        return DEFAULT_PROMPTS.get(stage_enum)
    
    def render_prompt(
        self,
        template: dict,
        epic_title: str,
        user_message: str,
        snapshot: Optional[EpicSnapshot]
    ) -> tuple[str, str]:
        """Render system and user prompts with context"""
        
        # Build context dictionary
        context = {
            "epic_title": epic_title,
            "user_message": user_message,
            "problem_statement": snapshot.problem_statement if snapshot else "Not yet defined",
            "desired_outcome": snapshot.desired_outcome if snapshot else "Not yet defined",
            "epic_summary": snapshot.epic_summary if snapshot else "Not yet defined",
            "acceptance_criteria": "\n".join(snapshot.acceptance_criteria) if snapshot and snapshot.acceptance_criteria else "Not yet defined",
        }
        
        # Handle None values
        for key, value in context.items():
            if value is None:
                context[key] = "Not yet defined"
        
        # Render prompts
        system_prompt = template["system_prompt"].format(**context)
        user_prompt = template["user_prompt_template"].format(**context)
        
        return system_prompt, user_prompt
    
    async def initialize_default_prompts(self):
        """Initialize default prompts in the database if they don't exist"""
        for stage, prompt_data in DEFAULT_PROMPTS.items():
            result = await self.session.execute(
                select(PromptTemplate)
                .where(PromptTemplate.template_id == prompt_data["template_id"])
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                prompt = PromptTemplate(
                    template_id=prompt_data["template_id"],
                    stage=stage,
                    system_prompt=prompt_data["system_prompt"],
                    user_prompt_template=prompt_data["user_prompt_template"],
                    invariants=prompt_data.get("invariants", []),
                    expected_outputs=prompt_data.get("expected_outputs", []),
                    version=1,
                    is_active=True
                )
                self.session.add(prompt)
        
        await self.session.commit()
