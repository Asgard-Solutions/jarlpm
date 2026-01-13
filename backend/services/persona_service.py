"""
Persona Service for JarlPM
Handles persona generation and management
"""
import os
import json
import base64
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.persona_models import Persona, PersonaGenerationSettings
from db.models import Epic
from db.feature_models import Feature
from db.user_story_models import UserStory

logger = logging.getLogger(__name__)


class PersonaService:
    """Service for Persona generation and management"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_epic_with_children(self, epic_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a completed epic with all its features and user stories"""
        from sqlalchemy.orm import selectinload
        
        # Get epic with snapshot eagerly loaded
        result = await self.session.execute(
            select(Epic)
            .options(selectinload(Epic.snapshot))
            .where(and_(Epic.epic_id == epic_id, Epic.user_id == user_id))
        )
        epic = result.scalar_one_or_none()
        
        if not epic:
            return None
        
        # Check if epic is locked (completed)
        if epic.current_stage != "epic_locked":
            return None
        
        # Access all needed fields NOW while session is active to avoid lazy loading
        # Convert snapshot relationship to dict
        snapshot_dict = None
        if epic.snapshot:
            snapshot_dict = {
                "problem_statement": epic.snapshot.problem_statement,
                "desired_outcomes": epic.snapshot.desired_outcomes,
                "acceptance_criteria": epic.snapshot.acceptance_criteria,
            }
        
        epic_dict = {
            "epic_id": epic.epic_id,
            "title": epic.title,
            "current_stage": epic.current_stage,
            "snapshot": snapshot_dict,
        }
        
        # Get features
        result = await self.session.execute(
            select(Feature).where(Feature.epic_id == epic_id).order_by(Feature.created_at)
        )
        features = list(result.scalars().all())
        
        # Convert features to dicts to avoid lazy loading issues
        features_data = []
        for f in features:
            features_data.append({
                "feature_id": f.feature_id,
                "title": f.title,
                "description": f.description,
                "acceptance_criteria": f.acceptance_criteria,
            })
        
        # Get user stories for all features
        feature_ids = [f["feature_id"] for f in features_data]
        stories_data = []
        if feature_ids:
            result = await self.session.execute(
                select(UserStory).where(UserStory.feature_id.in_(feature_ids)).order_by(UserStory.created_at)
            )
            stories = list(result.scalars().all())
            for s in stories:
                stories_data.append({
                    "feature_id": s.feature_id,
                    "story_text": s.story_text,
                    "acceptance_criteria": s.acceptance_criteria,
                })
        
        return {
            "epic": epic_dict,
            "features": features_data,
            "stories": stories_data
        }
    
    async def get_user_settings(self, user_id: str) -> PersonaGenerationSettings:
        """Get or create user's persona generation settings"""
        result = await self.session.execute(
            select(PersonaGenerationSettings).where(PersonaGenerationSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = PersonaGenerationSettings(user_id=user_id)
            self.session.add(settings)
            await self.session.commit()
            await self.session.refresh(settings)
        
        return settings
    
    async def update_user_settings(
        self,
        user_id: str,
        image_provider: Optional[str] = None,
        image_model: Optional[str] = None,
        default_persona_count: Optional[int] = None
    ) -> PersonaGenerationSettings:
        """Update user's persona generation settings"""
        settings = await self.get_user_settings(user_id)
        
        if image_provider is not None:
            settings.image_provider = image_provider
        if image_model is not None:
            settings.image_model = image_model
        if default_persona_count is not None:
            # Enforce 1-5 range
            settings.default_persona_count = max(1, min(5, default_persona_count))
        
        await self.session.commit()
        await self.session.refresh(settings)
        return settings
    
    def build_context_for_generation(self, epic_data: Dict[str, Any]) -> str:
        """Build context string from epic, features, and stories for LLM"""
        epic = epic_data["epic"]
        features = epic_data["features"]
        stories = epic_data["stories"]
        
        # Build stories by feature map (using dict access since we converted to dicts)
        stories_by_feature = {}
        for story in stories:
            fid = story["feature_id"]
            if fid not in stories_by_feature:
                stories_by_feature[fid] = []
            stories_by_feature[fid].append(story)
        
        context_parts = []
        
        # Epic info (accessing as dict now)
        context_parts.append("=== EPIC ===")
        context_parts.append(f"Title: {epic['title']}")
        if epic.get("snapshot"):
            snapshot = epic["snapshot"] if isinstance(epic["snapshot"], dict) else json.loads(epic["snapshot"]) if epic["snapshot"] else {}
            if snapshot.get("problem_statement"):
                context_parts.append(f"Problem Statement: {snapshot.get('problem_statement')}")
            if snapshot.get("desired_outcomes"):
                context_parts.append(f"Desired Outcomes: {snapshot.get('desired_outcomes')}")
            if snapshot.get("acceptance_criteria"):
                context_parts.append("Acceptance Criteria:")
                for ac in snapshot.get("acceptance_criteria", []):
                    context_parts.append(f"  - {ac}")
        
        # Features and their stories (accessing as dicts)
        context_parts.append("\n=== FEATURES ===")
        for feature in features:
            context_parts.append(f"\nFeature: {feature['title']}")
            if feature.get("description"):
                context_parts.append(f"Description: {feature['description']}")
            if feature.get("acceptance_criteria"):
                context_parts.append("Acceptance Criteria:")
                for ac in feature["acceptance_criteria"]:
                    context_parts.append(f"  - {ac}")
            
            # Stories for this feature
            feature_stories = stories_by_feature.get(feature["feature_id"], [])
            if feature_stories:
                context_parts.append("User Stories:")
                for story in feature_stories:
                    context_parts.append(f"  - {story['story_text']}")
                    if story.get("acceptance_criteria"):
                        for sac in story["acceptance_criteria"][:2]:  # Limit to 2 for brevity
                            context_parts.append(f"      • {sac}")
        
        return "\n".join(context_parts)
    
    async def generate_personas(
        self,
        user_id: str,
        epic_id: str,
        count: int = 3,
        llm_service = None
    ) -> List[Dict[str, Any]]:
        """
        Generate personas for a completed epic using LLM.
        Returns list of persona data dictionaries (without images).
        """
        # Get epic data
        epic_data = await self.get_epic_with_children(epic_id, user_id)
        if not epic_data:
            raise ValueError("Epic not found or not completed")
        
        # Build context
        context = self.build_context_for_generation(epic_data)
        
        # Build system prompt
        system_prompt = """You are an expert UX researcher and product strategist. Your task is to create detailed, actionable user personas based on the provided Epic, Features, and User Stories.

Each persona should be:
1. Distinct from other personas (different roles, needs, behaviors)
2. Grounded in the actual user stories and features
3. Actionable for development teams
4. Realistic and relatable

OUTPUT FORMAT:
Return a JSON array of persona objects. Each persona must have:
{
  "name": "First name (realistic, diverse)",
  "role": "Job title or user type (from the user stories)",
  "age_range": "e.g., '25-34', '35-44'",
  "location": "e.g., 'Urban, USA', 'Remote worker, Europe'",
  "tech_proficiency": "High | Medium | Low",
  "goals_and_motivations": ["Goal 1", "Goal 2", "Goal 3"],
  "pain_points": ["Pain point 1", "Pain point 2", "Pain point 3"],
  "key_behaviors": ["Behavior 1", "Behavior 2", "Behavior 3"],
  "jobs_to_be_done": ["JTBD 1", "JTBD 2"],
  "product_interaction_context": "When and why they use this product (2-3 sentences)",
  "representative_quote": "A quote that captures their perspective (in first person)",
  "portrait_prompt": "A detailed prompt for generating their portrait image (professional, friendly, realistic style)"
}

IMPORTANT:
- Derive personas directly from the user stories' personas (e.g., "As a [persona]...")
- Make personas diverse in demographics and tech proficiency
- Keep pain points and goals specific to the product context
- Portrait prompts should describe a professional headshot style, mentioning age, gender, expression, and setting

Return ONLY the JSON array, no additional text."""

        user_prompt = f"""Based on the following Epic, Features, and User Stories, generate {count} distinct user personas.

{context}

Generate {count} personas that represent the key user types for this product. Return as a JSON array."""

        # Call LLM
        if not llm_service:
            raise ValueError("LLM service required for generation")
        
        full_response = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        ):
            full_response += chunk
        
        # Parse JSON from response
        try:
            # Try to extract JSON array from response
            import re
            json_match = re.search(r'\[[\s\S]*\]', full_response)
            if json_match:
                personas_data = json.loads(json_match.group(0))
            else:
                raise ValueError("No JSON array found in response")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse persona JSON: {e}")
            logger.error(f"Response was: {full_response[:500]}")
            raise ValueError("Failed to parse LLM response as JSON")
        
        return personas_data
    
    async def generate_portrait_image(
        self,
        portrait_prompt: str,
        settings: PersonaGenerationSettings
    ) -> Optional[str]:
        """Generate a portrait image for a persona using the configured provider"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.environ.get("EMERGENT_LLM_KEY")
            if not api_key:
                logger.warning("No EMERGENT_LLM_KEY found for image generation")
                return None
            
            if settings.image_provider == "openai":
                from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
                
                image_gen = OpenAIImageGeneration(api_key=api_key)
                
                # Enhance prompt for professional portrait
                enhanced_prompt = f"Professional headshot portrait photograph. {portrait_prompt}. Clean background, soft lighting, friendly expression, high quality, realistic."
                
                images = await image_gen.generate_images(
                    prompt=enhanced_prompt,
                    model=settings.image_model or "gpt-image-1",
                    number_of_images=1
                )
                
                if images and len(images) > 0:
                    image_base64 = base64.b64encode(images[0]).decode('utf-8')
                    return image_base64
            
            elif settings.image_provider == "gemini":
                # Gemini Nano Banana support can be added here
                logger.warning("Gemini image generation not yet implemented")
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return None
    
    async def create_persona(
        self,
        user_id: str,
        epic_id: str,
        persona_data: Dict[str, Any],
        portrait_image_base64: Optional[str] = None
    ) -> Persona:
        """Create a new persona from generated data"""
        persona = Persona(
            epic_id=epic_id,
            user_id=user_id,
            name=persona_data.get("name", "Unknown"),
            role=persona_data.get("role", "User"),
            age_range=persona_data.get("age_range"),
            location=persona_data.get("location"),
            tech_proficiency=persona_data.get("tech_proficiency"),
            goals_and_motivations=persona_data.get("goals_and_motivations", []),
            pain_points=persona_data.get("pain_points", []),
            key_behaviors=persona_data.get("key_behaviors", []),
            jobs_to_be_done=persona_data.get("jobs_to_be_done", []),
            product_interaction_context=persona_data.get("product_interaction_context"),
            representative_quote=persona_data.get("representative_quote"),
            portrait_image_base64=portrait_image_base64,
            portrait_prompt=persona_data.get("portrait_prompt"),
            source="ai_generated"
        )
        
        self.session.add(persona)
        await self.session.commit()
        await self.session.refresh(persona)
        return persona
    
    async def get_personas_for_epic(self, epic_id: str, user_id: str) -> List[Persona]:
        """Get all personas for an epic"""
        result = await self.session.execute(
            select(Persona).where(
                and_(
                    Persona.epic_id == epic_id,
                    Persona.user_id == user_id,
                    Persona.is_active.is_(True)
                )
            ).order_by(Persona.created_at)
        )
        return list(result.scalars().all())
    
    async def get_all_personas_for_user(
        self,
        user_id: str,
        epic_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Persona]:
        """Get all personas for a user with optional filtering"""
        conditions = [Persona.user_id == user_id, Persona.is_active.is_(True)]
        
        if epic_id:
            conditions.append(Persona.epic_id == epic_id)
        
        query = select(Persona).where(and_(*conditions)).order_by(Persona.created_at.desc())
        
        result = await self.session.execute(query)
        personas = list(result.scalars().all())
        
        # Client-side search filtering (for now)
        if search:
            search_lower = search.lower()
            personas = [
                p for p in personas
                if search_lower in p.name.lower() or 
                   search_lower in p.role.lower() or
                   (p.representative_quote and search_lower in p.representative_quote.lower())
            ]
        
        return personas
    
    async def get_persona(self, persona_id: str, user_id: str) -> Optional[Persona]:
        """Get a specific persona by ID"""
        result = await self.session.execute(
            select(Persona).where(
                and_(
                    Persona.persona_id == persona_id,
                    Persona.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def update_persona(
        self,
        persona_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Persona]:
        """Update a persona (marks as human_modified)"""
        persona = await self.get_persona(persona_id, user_id)
        if not persona:
            return None
        
        # Apply updates
        updatable_fields = [
            "name", "role", "age_range", "location", "tech_proficiency",
            "goals_and_motivations", "pain_points", "key_behaviors",
            "jobs_to_be_done", "product_interaction_context", "representative_quote"
        ]
        
        for field in updatable_fields:
            if field in updates:
                setattr(persona, field, updates[field])
        
        # Mark as human-modified
        persona.source = "human_modified"
        persona.updated_at = datetime.now(timezone.utc)
        
        await self.session.commit()
        await self.session.refresh(persona)
        return persona
    
    async def delete_persona(self, persona_id: str, user_id: str) -> bool:
        """Soft delete a persona"""
        persona = await self.get_persona(persona_id, user_id)
        if not persona:
            return False
        
        persona.is_active = False
        await self.session.commit()
        return True
    
    async def regenerate_portrait(
        self,
        persona_id: str,
        user_id: str,
        new_prompt: Optional[str] = None
    ) -> Optional[Persona]:
        """Regenerate the portrait image for a persona"""
        persona = await self.get_persona(persona_id, user_id)
        if not persona:
            return None
        
        settings = await self.get_user_settings(user_id)
        
        prompt = new_prompt or persona.portrait_prompt
        if not prompt:
            prompt = f"Professional headshot of a {persona.age_range} {persona.role}, friendly expression"
        
        image_base64 = await self.generate_portrait_image(prompt, settings)
        
        if image_base64:
            persona.portrait_image_base64 = image_base64
            persona.portrait_prompt = prompt
            persona.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(persona)
        
        return persona
