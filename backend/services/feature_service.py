"""
Feature Service for JarlPM
Handles feature lifecycle management with conversation-based refinement
"""
from typing import Optional, List
from datetime import datetime, timezone
import json
import re

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.feature_models import Feature, FeatureStage, FeatureConversationEvent, FEATURE_STAGE_ORDER
from db.models import Epic


class FeatureService:
    """Service for Feature lifecycle management"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_epic(self, epic_id: str, user_id: str) -> Optional[Epic]:
        """Get an epic by ID (with ownership check)"""
        result = await self.session.execute(
            select(Epic)
            .where(and_(Epic.epic_id == epic_id, Epic.user_id == user_id))
        )
        return result.scalar_one_or_none()
    
    async def create_feature(
        self,
        epic_id: str,
        title: str,
        description: str,
        acceptance_criteria: Optional[List[str]] = None,
        source: str = "ai_generated"
    ) -> Feature:
        """Create a new feature in draft stage"""
        feature = Feature(
            epic_id=epic_id,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria,
            source=source,
            current_stage=FeatureStage.DRAFT.value
        )
        self.session.add(feature)
        await self.session.commit()
        await self.session.refresh(feature)
        return feature
    
    async def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get a feature by ID with conversation events"""
        result = await self.session.execute(
            select(Feature)
            .options(selectinload(Feature.conversation_events))
            .where(Feature.feature_id == feature_id)
        )
        return result.scalar_one_or_none()
    
    async def get_epic_features(self, epic_id: str) -> List[Feature]:
        """Get all features for an epic"""
        result = await self.session.execute(
            select(Feature)
            .options(selectinload(Feature.conversation_events))
            .where(Feature.epic_id == epic_id)
            .order_by(Feature.created_at.asc())
        )
        return list(result.scalars().all())
    
    async def update_feature(
        self,
        feature_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None
    ) -> Optional[Feature]:
        """Update feature content (only if not approved)"""
        feature = await self.get_feature(feature_id)
        if not feature:
            return None
        
        # Cannot update approved features
        if feature.current_stage == FeatureStage.APPROVED.value:
            raise ValueError("Cannot update approved features")
        
        if title is not None:
            feature.title = title
        if description is not None:
            feature.description = description
        if acceptance_criteria is not None:
            feature.acceptance_criteria = acceptance_criteria
        
        feature.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(feature)
        return feature
    
    async def start_refinement(self, feature_id: str) -> Feature:
        """Move feature to refining stage"""
        feature = await self.get_feature(feature_id)
        if not feature:
            raise ValueError("Feature not found")
        
        if feature.current_stage == FeatureStage.APPROVED.value:
            raise ValueError("Cannot refine approved features")
        
        feature.current_stage = FeatureStage.REFINING.value
        feature.updated_at = datetime.now(timezone.utc)
        
        # Add system message to conversation
        await self.add_conversation_event(
            feature_id=feature_id,
            role="system",
            content=f"Started refinement conversation for feature: {feature.title}"
        )
        
        await self.session.commit()
        await self.session.refresh(feature)
        return feature
    
    async def approve_feature(self, feature_id: str) -> Feature:
        """Approve and lock a feature"""
        feature = await self.get_feature(feature_id)
        if not feature:
            raise ValueError("Feature not found")
        
        if feature.current_stage == FeatureStage.APPROVED.value:
            raise ValueError("Feature is already approved")
        
        feature.current_stage = FeatureStage.APPROVED.value
        feature.approved_at = datetime.now(timezone.utc)
        feature.updated_at = datetime.now(timezone.utc)
        
        # Add system message to conversation
        await self.add_conversation_event(
            feature_id=feature_id,
            role="system",
            content=f"Feature approved and locked: {feature.title}"
        )
        
        await self.session.commit()
        await self.session.refresh(feature)
        return feature
    
    async def delete_feature(self, feature_id: str) -> bool:
        """Delete a feature"""
        feature = await self.get_feature(feature_id)
        if not feature:
            return False
        
        # Enable cascade delete for append-only tables by setting session variable
        from sqlalchemy import text
        await self.session.execute(text("SET LOCAL jarlpm.allow_cascade_delete = 'true'"))
        
        await self.session.delete(feature)
        await self.session.commit()
        return True
    
    async def add_conversation_event(
        self,
        feature_id: str,
        role: str,
        content: str,
        event_metadata: dict = None
    ) -> FeatureConversationEvent:
        """Add an event to the feature's conversation (append-only)"""
        event = FeatureConversationEvent(
            feature_id=feature_id,
            role=role,
            content=content,
            event_metadata=event_metadata
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
    
    async def get_conversation_history(self, feature_id: str, limit: int = 20) -> List[dict]:
        """Get recent conversation history for LLM context"""
        result = await self.session.execute(
            select(FeatureConversationEvent)
            .where(
                and_(
                    FeatureConversationEvent.feature_id == feature_id,
                    FeatureConversationEvent.role.in_(['user', 'assistant'])
                )
            )
            .order_by(FeatureConversationEvent.created_at.desc())
            .limit(limit)
        )
        events = list(result.scalars().all())
        events.reverse()  # Oldest first
        return [{"role": e.role, "content": e.content} for e in events]
    
    def parse_feature_update(self, content: str) -> dict:
        """Parse AI response for feature updates"""
        result = {
            "title": None,
            "description": None,
            "acceptance_criteria": None
        }
        
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                result["title"] = parsed.get("title")
                result["description"] = parsed.get("description")
                result["acceptance_criteria"] = parsed.get("acceptance_criteria")
                return result
            except json.JSONDecodeError:
                pass
        
        return result
