from typing import Optional

from models.epic import EpicStage, EpicSnapshot
from models.prompt_template import PromptTemplate, DEFAULT_PROMPTS


class PromptService:
    """Service for managing and rendering prompt templates"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_prompt_for_stage(self, stage: EpicStage) -> PromptTemplate:
        """Get the active prompt template for a stage"""
        # First check database for custom prompts
        prompt_doc = await self.db.prompt_templates.find_one(
            {"stage": stage.value, "is_active": True},
            {"_id": 0}
        )
        
        if prompt_doc:
            return PromptTemplate(**prompt_doc)
        
        # Fall back to default prompts
        return DEFAULT_PROMPTS.get(stage)
    
    def render_prompt(
        self,
        template: PromptTemplate,
        epic_title: str,
        user_message: str,
        snapshot: EpicSnapshot
    ) -> tuple[str, str]:
        """Render system and user prompts with context"""
        
        # Build context dictionary
        context = {
            "epic_title": epic_title,
            "user_message": user_message,
            "problem_statement": snapshot.problem_statement or "Not yet defined",
            "desired_outcome": snapshot.desired_outcome or "Not yet defined",
            "epic_summary": snapshot.epic_summary or "Not yet defined",
            "acceptance_criteria": "\n".join(snapshot.acceptance_criteria) if snapshot.acceptance_criteria else "Not yet defined",
        }
        
        # Render prompts
        system_prompt = template.system_prompt.format(**context)
        user_prompt = template.user_prompt_template.format(**context)
        
        return system_prompt, user_prompt
    
    async def initialize_default_prompts(self):
        """Initialize default prompts in the database if they don't exist"""
        for stage, prompt in DEFAULT_PROMPTS.items():
            existing = await self.db.prompt_templates.find_one(
                {"template_id": prompt.template_id},
                {"_id": 0}
            )
            if not existing:
                await self.db.prompt_templates.insert_one(prompt.model_dump())
