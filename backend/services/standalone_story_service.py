"""
Standalone User Story Service for JarlPM
Handles standalone user stories that are not tied to features
"""
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from db.user_story_models import (
    UserStory, UserStoryStage, UserStoryConversationEvent
)


class StandaloneStoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # ============================================
    # CRUD OPERATIONS
    # ============================================
    
    async def create_story(
        self,
        user_id: str,
        persona: str,
        action: str,
        benefit: str,
        title: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
        story_points: Optional[int] = None,
        source: str = "ai_generated"
    ) -> UserStory:
        """Create a standalone user story"""
        
        # Construct story text
        story_text = f"As a {persona}, I want to {action} so that {benefit}"
        
        story = UserStory(
            user_id=user_id,
            feature_id=None,  # Standalone
            is_standalone=True,
            title=title or f"Story: {persona[:30]}",
            persona=persona,
            action=action,
            benefit=benefit,
            story_text=story_text,
            acceptance_criteria=acceptance_criteria,
            story_points=story_points,
            source=source,
            current_stage=UserStoryStage.DRAFT.value
        )
        
        self.session.add(story)
        await self.session.commit()
        
        return await self.get_story(story.story_id)
    
    async def get_story(self, story_id: str) -> Optional[UserStory]:
        """Get a story by ID with relationships loaded"""
        query = select(UserStory).options(
            selectinload(UserStory.conversation_events)
        ).where(UserStory.story_id == story_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_story_for_user(self, story_id: str, user_id: str) -> Optional[UserStory]:
        """Get a standalone story by ID and user_id"""
        query = select(UserStory).options(
            selectinload(UserStory.conversation_events)
        ).where(and_(
            UserStory.story_id == story_id,
            UserStory.user_id == user_id,
            UserStory.is_standalone == True
        ))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_stories(
        self,
        user_id: str,
        stage: Optional[str] = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        limit: int = 100,
        offset: int = 0
    ) -> List[UserStory]:
        """List standalone user stories for a user"""
        query = select(UserStory).where(and_(
            UserStory.user_id == user_id,
            UserStory.is_standalone == True
        ))
        
        if stage:
            query = query.where(UserStory.current_stage == stage)
        
        # Sorting
        sort_column = getattr(UserStory, sort_by, UserStory.updated_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_story(
        self,
        story_id: str,
        title: Optional[str] = None,
        persona: Optional[str] = None,
        action: Optional[str] = None,
        benefit: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
        story_points: Optional[int] = None
    ) -> Optional[UserStory]:
        """Update a standalone story (only in draft/refining stage)"""
        story = await self.get_story(story_id)
        if not story:
            return None
        
        if story.current_stage == UserStoryStage.APPROVED.value:
            raise ValueError("Cannot edit an approved story")
        
        if title is not None:
            story.title = title
        if persona is not None:
            story.persona = persona
        if action is not None:
            story.action = action
        if benefit is not None:
            story.benefit = benefit
        
        # Rebuild story text if any component changed
        if any(x is not None for x in [persona, action, benefit]):
            story.story_text = f"As a {story.persona}, I want to {story.action} so that {story.benefit}"
        
        if acceptance_criteria is not None:
            story.acceptance_criteria = acceptance_criteria
        if story_points is not None:
            story.story_points = story_points
        
        await self.session.commit()
        return await self.get_story(story_id)
    
    async def delete_story(self, story_id: str, user_id: str) -> bool:
        """Delete a standalone story"""
        story = await self.get_story_for_user(story_id, user_id)
        if not story:
            return False
        
        # Delete conversation events first
        for event in story.conversation_events:
            await self.session.delete(event)
        
        await self.session.delete(story)
        await self.session.commit()
        return True
    
    # ============================================
    # STAGE TRANSITIONS
    # ============================================
    
    async def start_refinement(self, story_id: str) -> UserStory:
        """Move story from draft to refining stage"""
        story = await self.get_story(story_id)
        if not story:
            raise ValueError("Story not found")
        
        if story.current_stage != UserStoryStage.DRAFT.value:
            raise ValueError(f"Can only start refinement from draft stage. Current: {story.current_stage}")
        
        story.current_stage = UserStoryStage.REFINING.value
        await self.session.commit()
        return await self.get_story(story_id)
    
    async def approve_story(self, story_id: str) -> UserStory:
        """Approve and lock a story"""
        story = await self.get_story(story_id)
        if not story:
            raise ValueError("Story not found")
        
        if story.current_stage not in [UserStoryStage.DRAFT.value, UserStoryStage.REFINING.value]:
            raise ValueError(f"Can only approve from draft or refining stage. Current: {story.current_stage}")
        
        story.current_stage = UserStoryStage.APPROVED.value
        story.approved_at = datetime.now(timezone.utc)
        story.is_frozen = True
        
        await self.session.commit()
        return await self.get_story(story_id)
    
    # ============================================
    # CONVERSATION EVENTS
    # ============================================
    
    async def add_conversation_event(
        self,
        story_id: str,
        role: str,
        content: str
    ) -> UserStoryConversationEvent:
        """Add a conversation event"""
        event = UserStoryConversationEvent(
            story_id=story_id,
            role=role,
            content=content
        )
        self.session.add(event)
        await self.session.commit()
        
        result = await self.session.execute(
            select(UserStoryConversationEvent).where(
                UserStoryConversationEvent.event_id == event.event_id
            )
        )
        return result.scalar_one()
    
    async def get_conversation(self, story_id: str) -> List[UserStoryConversationEvent]:
        """Get conversation history for a story"""
        result = await self.session.execute(
            select(UserStoryConversationEvent).where(
                UserStoryConversationEvent.story_id == story_id
            ).order_by(UserStoryConversationEvent.created_at.asc())
        )
        return list(result.scalars().all())
