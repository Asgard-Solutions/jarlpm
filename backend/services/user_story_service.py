"""
User Story Service for JarlPM
Handles user story lifecycle management with conversation-based refinement
Supports both feature-bound and standalone user stories
"""
from typing import Optional, List
from datetime import datetime, timezone
import json
import re

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.user_story_models import UserStory, UserStoryStage, UserStoryConversationEvent
from db.feature_models import Feature, FeatureStage
from db.models import Epic


class UserStoryService:
    """Service for User Story lifecycle management"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get a feature by ID"""
        result = await self.session.execute(
            select(Feature)
            .where(Feature.feature_id == feature_id)
        )
        return result.scalar_one_or_none()
    
    async def get_epic_for_feature(self, feature_id: str, user_id: str) -> Optional[Epic]:
        """Get the epic that owns a feature (with ownership check)"""
        result = await self.session.execute(
            select(Epic)
            .join(Feature, Feature.epic_id == Epic.epic_id)
            .where(and_(Feature.feature_id == feature_id, Epic.user_id == user_id))
        )
        return result.scalar_one_or_none()
    
    # ============================================
    # STANDALONE STORY OPERATIONS
    # ============================================
    
    async def create_standalone_story(
        self,
        user_id: str,
        title: str,
        persona: str,
        action: str,
        benefit: str,
        acceptance_criteria: Optional[List[str]] = None,
        story_points: Optional[int] = None,
        source: str = "ai_generated"
    ) -> UserStory:
        """Create a standalone user story (not linked to a feature)"""
        story_text = f"As a {persona}, I want to {action} so that {benefit}."
        
        story = UserStory(
            feature_id=None,  # Standalone - not linked to feature
            user_id=user_id,
            title=title,
            persona=persona,
            action=action,
            benefit=benefit,
            story_text=story_text,
            acceptance_criteria=acceptance_criteria,
            story_points=story_points,
            source=source,
            is_standalone=True,
            current_stage=UserStoryStage.DRAFT.value
        )
        self.session.add(story)
        await self.session.commit()
        await self.session.refresh(story)
        return story
    
    async def get_standalone_stories(self, user_id: str, include_all: bool = False) -> List[UserStory]:
        """Get all standalone user stories for a user"""
        query = select(UserStory).options(
            selectinload(UserStory.conversation_events)
        ).where(
            and_(
                UserStory.user_id == user_id,
                UserStory.is_standalone.is_(True)
            )
        ).order_by(UserStory.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_all_stories_for_user(
        self,
        user_id: str,
        standalone_only: bool = False,
        stage: Optional[str] = None
    ) -> List[UserStory]:
        """Get all stories for a user (both standalone and feature-bound optionally)"""
        # Build base query for standalone stories
        conditions = [UserStory.user_id == user_id, UserStory.is_standalone.is_(True)]
        
        if stage:
            conditions.append(UserStory.current_stage == stage)
        
        query = select(UserStory).options(
            selectinload(UserStory.conversation_events)
        ).where(and_(*conditions)).order_by(UserStory.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_story_for_user(self, story_id: str, user_id: str) -> Optional[UserStory]:
        """Get a story by ID with ownership verification for standalone stories"""
        story = await self.get_user_story(story_id)
        if not story:
            return None
        
        # For standalone stories, check direct ownership
        if story.is_standalone:
            if story.user_id != user_id:
                return None
            return story
        
        # For feature-bound stories, check via epic ownership
        if story.feature_id:
            epic = await self.get_epic_for_feature(story.feature_id, user_id)
            if not epic:
                return None
        
        return story
    
    # ============================================
    # FEATURE-BOUND STORY OPERATIONS
    # ============================================
    
    async def create_user_story(
        self,
        feature_id: str,
        persona: str,
        action: str,
        benefit: str,
        acceptance_criteria: Optional[List[str]] = None,
        story_points: Optional[int] = None,
        source: str = "ai_generated"
    ) -> UserStory:
        """Create a new user story in draft stage (feature-bound)"""
        # Build the standard user story text
        story_text = f"As a {persona}, I want to {action} so that {benefit}."
        
        story = UserStory(
            feature_id=feature_id,
            persona=persona,
            action=action,
            benefit=benefit,
            story_text=story_text,
            acceptance_criteria=acceptance_criteria,
            story_points=story_points,
            source=source,
            is_standalone=False,
            current_stage=UserStoryStage.DRAFT.value
        )
        self.session.add(story)
        await self.session.commit()
        await self.session.refresh(story)
        return story
    
    async def get_user_story(self, story_id: str) -> Optional[UserStory]:
        """Get a user story by ID with conversation events"""
        result = await self.session.execute(
            select(UserStory)
            .options(selectinload(UserStory.conversation_events))
            .where(UserStory.story_id == story_id)
        )
        return result.scalar_one_or_none()
    
    async def get_feature_stories(self, feature_id: str) -> List[UserStory]:
        """Get all user stories for a feature"""
        result = await self.session.execute(
            select(UserStory)
            .options(selectinload(UserStory.conversation_events))
            .where(UserStory.feature_id == feature_id)
            .order_by(UserStory.priority.asc().nullslast(), UserStory.created_at.asc())
        )
        return list(result.scalars().all())
    
    async def update_user_story(
        self,
        story_id: str,
        persona: Optional[str] = None,
        action: Optional[str] = None,
        benefit: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
        story_points: Optional[int] = None
    ) -> Optional[UserStory]:
        """Update user story content (only if not approved)"""
        story = await self.get_user_story(story_id)
        if not story:
            return None
        
        # Cannot update approved stories
        if story.current_stage == UserStoryStage.APPROVED.value:
            raise ValueError("Cannot update approved user stories")
        
        if persona is not None:
            story.persona = persona
        if action is not None:
            story.action = action
        if benefit is not None:
            story.benefit = benefit
        if acceptance_criteria is not None:
            story.acceptance_criteria = acceptance_criteria
        if story_points is not None:
            story.story_points = story_points
        
        # Rebuild story text if any component changed
        if any([persona, action, benefit]):
            story.story_text = f"As a {story.persona}, I want to {story.action} so that {story.benefit}."
        
        story.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(story)
        return story
    
    async def start_refinement(self, story_id: str) -> UserStory:
        """Move user story to refining stage"""
        story = await self.get_user_story(story_id)
        if not story:
            raise ValueError("User story not found")
        
        if story.current_stage == UserStoryStage.APPROVED.value:
            raise ValueError("Cannot refine approved user stories")
        
        story.current_stage = UserStoryStage.REFINING.value
        story.updated_at = datetime.now(timezone.utc)
        
        # Add system message to conversation
        await self.add_conversation_event(
            story_id=story_id,
            role="system",
            content=f"Started refinement conversation for user story: {story.story_text}"
        )
        
        await self.session.commit()
        await self.session.refresh(story)
        return story
    
    async def approve_user_story(self, story_id: str) -> UserStory:
        """Approve and lock a user story"""
        story = await self.get_user_story(story_id)
        if not story:
            raise ValueError("User story not found")
        
        if story.current_stage == UserStoryStage.APPROVED.value:
            raise ValueError("User story is already approved")
        
        story.current_stage = UserStoryStage.APPROVED.value
        story.approved_at = datetime.now(timezone.utc)
        story.updated_at = datetime.now(timezone.utc)
        
        # Add system message to conversation
        await self.add_conversation_event(
            story_id=story_id,
            role="system",
            content=f"User story approved and locked: {story.story_text}"
        )
        
        await self.session.commit()
        await self.session.refresh(story)
        return story
    
    async def delete_user_story(self, story_id: str) -> bool:
        """Delete a user story"""
        story = await self.get_user_story(story_id)
        if not story:
            return False
        
        # Enable cascade delete for append-only tables by setting session variable
        from sqlalchemy import text
        await self.session.execute(text("SET LOCAL jarlpm.allow_cascade_delete = 'true'"))
        
        await self.session.delete(story)
        await self.session.commit()
        return True
    
    async def add_conversation_event(
        self,
        story_id: str,
        role: str,
        content: str,
        event_metadata: dict = None
    ) -> UserStoryConversationEvent:
        """Add an event to the user story's conversation (append-only)"""
        event = UserStoryConversationEvent(
            story_id=story_id,
            role=role,
            content=content,
            event_metadata=event_metadata
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
    
    async def get_conversation_history(self, story_id: str, limit: int = 20) -> List[dict]:
        """Get recent conversation history for LLM context"""
        result = await self.session.execute(
            select(UserStoryConversationEvent)
            .where(
                and_(
                    UserStoryConversationEvent.story_id == story_id,
                    UserStoryConversationEvent.role.in_(['user', 'assistant'])
                )
            )
            .order_by(UserStoryConversationEvent.created_at.desc())
            .limit(limit)
        )
        events = list(result.scalars().all())
        events.reverse()  # Oldest first
        return [{"role": e.role, "content": e.content} for e in events]
