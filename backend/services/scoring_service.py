"""
Scoring Service for JarlPM
Handles RICE and MoSCoW scoring with AI assistance
"""
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging

from db.models import Epic, Bug
from db.feature_models import Feature
from db.user_story_models import UserStory
from db.scoring_models import MoSCoWScore, IMPACT_VALUES, CONFIDENCE_VALUES, IMPACT_LABELS, CONFIDENCE_LABELS, MOSCOW_LABELS

logger = logging.getLogger(__name__)


class ScoringService:
    """Service for managing RICE and MoSCoW scores"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    @staticmethod
    def calculate_rice_total(reach: int, impact: float, confidence: float, effort: float) -> float:
        """Calculate RICE score: (Reach * Impact * Confidence) / Effort"""
        if effort <= 0:
            return 0
        return round((reach * impact * confidence) / effort, 2)
    
    @staticmethod
    def validate_rice_values(reach: int, impact: float, confidence: float, effort: float) -> tuple[bool, str]:
        """Validate RICE component values"""
        if reach < 1 or reach > 10:
            return False, "Reach must be between 1 and 10"
        if impact not in IMPACT_VALUES:
            return False, f"Impact must be one of: {IMPACT_VALUES}"
        if confidence not in CONFIDENCE_VALUES:
            return False, f"Confidence must be one of: {CONFIDENCE_VALUES}"
        if effort < 0.5 or effort > 10:
            return False, "Effort must be between 0.5 and 10"
        return True, ""
    
    @staticmethod
    def validate_moscow_value(score: str) -> tuple[bool, str]:
        """Validate MoSCoW score value"""
        valid_values = [e.value for e in MoSCoWScore]
        if score not in valid_values:
            return False, f"MoSCoW score must be one of: {valid_values}"
        return True, ""
    
    # ============================================
    # Epic MoSCoW Scoring
    # ============================================
    
    async def get_epic(self, epic_id: str, user_id: str) -> Optional[Epic]:
        """Get an epic by ID and user"""
        result = await self.session.execute(
            select(Epic)
            .options(selectinload(Epic.snapshot))
            .where(Epic.epic_id == epic_id, Epic.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_epic_moscow(self, epic_id: str, user_id: str, moscow_score: str, reasoning: str = None) -> Epic:
        """Update MoSCoW score for an Epic"""
        epic = await self.get_epic(epic_id, user_id)
        if not epic:
            raise ValueError("Epic not found")
        
        is_valid, error = self.validate_moscow_value(moscow_score)
        if not is_valid:
            raise ValueError(error)
        
        epic.moscow_score = moscow_score
        if reasoning:
            epic.moscow_reasoning = reasoning
        await self.session.commit()
        await self.session.refresh(epic)
        return epic
    
    # ============================================
    # Feature Scoring (MoSCoW + RICE)
    # ============================================
    
    async def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get a feature by ID"""
        result = await self.session.execute(
            select(Feature).where(Feature.feature_id == feature_id)
        )
        return result.scalar_one_or_none()
    
    async def update_feature_moscow(self, feature_id: str, moscow_score: str) -> Feature:
        """Update MoSCoW score for a Feature"""
        feature = await self.get_feature(feature_id)
        if not feature:
            raise ValueError("Feature not found")
        
        is_valid, error = self.validate_moscow_value(moscow_score)
        if not is_valid:
            raise ValueError(error)
        
        feature.moscow_score = moscow_score
        await self.session.commit()
        await self.session.refresh(feature)
        return feature
    
    async def update_feature_rice(
        self, feature_id: str, reach: int, impact: float, confidence: float, effort: float
    ) -> Feature:
        """Update RICE score for a Feature"""
        feature = await self.get_feature(feature_id)
        if not feature:
            raise ValueError("Feature not found")
        
        is_valid, error = self.validate_rice_values(reach, impact, confidence, effort)
        if not is_valid:
            raise ValueError(error)
        
        feature.rice_reach = reach
        feature.rice_impact = impact
        feature.rice_confidence = confidence
        feature.rice_effort = effort
        feature.rice_total = self.calculate_rice_total(reach, impact, confidence, effort)
        
        await self.session.commit()
        await self.session.refresh(feature)
        return feature
    
    # ============================================
    # User Story RICE Scoring
    # ============================================
    
    async def get_user_story(self, story_id: str) -> Optional[UserStory]:
        """Get a user story by ID"""
        result = await self.session.execute(
            select(UserStory).where(UserStory.story_id == story_id)
        )
        return result.scalar_one_or_none()
    
    async def update_story_rice(
        self, story_id: str, reach: int, impact: float, confidence: float, effort: float
    ) -> UserStory:
        """Update RICE score for a User Story"""
        story = await self.get_user_story(story_id)
        if not story:
            raise ValueError("User story not found")
        
        is_valid, error = self.validate_rice_values(reach, impact, confidence, effort)
        if not is_valid:
            raise ValueError(error)
        
        story.rice_reach = reach
        story.rice_impact = impact
        story.rice_confidence = confidence
        story.rice_effort = effort
        story.rice_total = self.calculate_rice_total(reach, impact, confidence, effort)
        
        await self.session.commit()
        await self.session.refresh(story)
        return story
    
    # ============================================
    # Bug RICE Scoring
    # ============================================
    
    async def get_bug(self, bug_id: str, user_id: str) -> Optional[Bug]:
        """Get a bug by ID and user"""
        result = await self.session.execute(
            select(Bug).where(Bug.bug_id == bug_id, Bug.user_id == user_id, Bug.is_deleted == False)
        )
        return result.scalar_one_or_none()
    
    async def update_bug_rice(
        self, bug_id: str, user_id: str, reach: int, impact: float, confidence: float, effort: float
    ) -> Bug:
        """Update RICE score for a Bug"""
        bug = await self.get_bug(bug_id, user_id)
        if not bug:
            raise ValueError("Bug not found")
        
        is_valid, error = self.validate_rice_values(reach, impact, confidence, effort)
        if not is_valid:
            raise ValueError(error)
        
        bug.rice_reach = reach
        bug.rice_impact = impact
        bug.rice_confidence = confidence
        bug.rice_effort = effort
        bug.rice_total = self.calculate_rice_total(reach, impact, confidence, effort)
        
        await self.session.commit()
        await self.session.refresh(bug)
        return bug
    
    # ============================================
    # Helper Methods for AI Prompts
    # ============================================
    
    def build_epic_context_for_ai(self, epic: Epic) -> str:
        """Build context string for AI scoring suggestions"""
        context = f"""Epic: {epic.title}
Stage: {epic.current_stage}"""
        
        if epic.snapshot:
            context += f"""
Problem Statement: {epic.snapshot.problem_statement or 'Not defined'}
Desired Outcome: {epic.snapshot.desired_outcome or 'Not defined'}
Epic Summary: {epic.snapshot.epic_summary or 'Not defined'}"""
            if epic.snapshot.acceptance_criteria:
                context += f"""
Acceptance Criteria:
{chr(10).join(f'- {c}' for c in epic.snapshot.acceptance_criteria)}"""
        
        return context
    
    def build_feature_context_for_ai(self, feature: Feature) -> str:
        """Build context string for AI scoring suggestions"""
        context = f"""Feature: {feature.title}
Description: {feature.description}
Stage: {feature.current_stage}"""
        
        if feature.acceptance_criteria:
            context += f"""
Acceptance Criteria:
{chr(10).join(f'- {c}' for c in feature.acceptance_criteria)}"""
        
        return context
    
    def build_story_context_for_ai(self, story: UserStory) -> str:
        """Build context string for AI scoring suggestions"""
        context = f"""User Story: {story.story_text}
Persona: {story.persona}
Action: {story.action}
Benefit: {story.benefit}
Stage: {story.current_stage}"""
        
        if story.acceptance_criteria:
            context += f"""
Acceptance Criteria:
{chr(10).join(f'- {c}' for c in story.acceptance_criteria)}"""
        
        if story.story_points:
            context += f"""
Story Points: {story.story_points}"""
        
        return context
    
    def build_bug_context_for_ai(self, bug: Bug) -> str:
        """Build context string for AI scoring suggestions"""
        context = f"""Bug: {bug.title}
Description: {bug.description}
Severity: {bug.severity}
Status: {bug.status}"""
        
        if bug.steps_to_reproduce:
            context += f"""
Steps to Reproduce: {bug.steps_to_reproduce}"""
        
        if bug.expected_behavior:
            context += f"""
Expected Behavior: {bug.expected_behavior}"""
        
        if bug.actual_behavior:
            context += f"""
Actual Behavior: {bug.actual_behavior}"""
        
        return context
