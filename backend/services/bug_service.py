"""
Bug Service for JarlPM
Handles bug CRUD, lifecycle management, and linking operations
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from db.models import (
    Bug, BugLink, BugStatusHistory, BugConversationEvent,
    BugStatus, BugSeverity, BugPriority, BugLinkEntityType,
    BUG_STATUS_TRANSITIONS
)


class BugService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # ============================================
    # CRUD OPERATIONS
    # ============================================
    
    async def create_bug(
        self,
        user_id: str,
        title: str,
        description: str,
        severity: str = BugSeverity.MEDIUM.value,
        steps_to_reproduce: Optional[str] = None,
        expected_behavior: Optional[str] = None,
        actual_behavior: Optional[str] = None,
        environment: Optional[str] = None,
        priority: Optional[str] = None,
        due_date: Optional[datetime] = None,
        links: Optional[List[Dict[str, str]]] = None  # [{"entity_type": "epic", "entity_id": "..."}]
    ) -> Bug:
        """Create a new bug with optional links"""
        
        bug = Bug(
            user_id=user_id,
            title=title,
            description=description,
            severity=severity,
            status=BugStatus.DRAFT.value,
            steps_to_reproduce=steps_to_reproduce,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            environment=environment,
            priority=priority,
            due_date=due_date
        )
        
        self.session.add(bug)
        await self.session.flush()  # Get bug_id
        
        # Add initial status history
        initial_history = BugStatusHistory(
            bug_id=bug.bug_id,
            from_status=None,
            to_status=BugStatus.DRAFT.value,
            changed_by=user_id,
            notes="Bug created"
        )
        self.session.add(initial_history)
        
        # Add links if provided
        if links:
            for link_data in links:
                link = BugLink(
                    bug_id=bug.bug_id,
                    entity_type=link_data["entity_type"],
                    entity_id=link_data["entity_id"]
                )
                self.session.add(link)
        
        await self.session.commit()
        
        # Reload with relationships
        return await self.get_bug(bug.bug_id)
    
    async def get_bug(self, bug_id: str, include_deleted: bool = False) -> Optional[Bug]:
        """Get a bug by ID with relationships loaded"""
        query = select(Bug).options(
            selectinload(Bug.links),
            selectinload(Bug.status_history)
        ).where(Bug.bug_id == bug_id)
        
        if not include_deleted:
            query = query.where(Bug.is_deleted == False)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_bug_for_user(self, bug_id: str, user_id: str, include_deleted: bool = False) -> Optional[Bug]:
        """Get a bug by ID and user_id"""
        query = select(Bug).options(
            selectinload(Bug.links),
            selectinload(Bug.status_history)
        ).where(and_(Bug.bug_id == bug_id, Bug.user_id == user_id))
        
        if not include_deleted:
            query = query.where(Bug.is_deleted == False)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_bugs(
        self,
        user_id: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        assignee_id: Optional[str] = None,
        linked_only: Optional[bool] = None,  # True = has links, False = standalone, None = all
        include_deleted: bool = False,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        limit: int = 100,
        offset: int = 0
    ) -> List[Bug]:
        """List bugs with filtering and sorting"""
        query = select(Bug).options(
            selectinload(Bug.links)
        ).where(Bug.user_id == user_id)
        
        if not include_deleted:
            query = query.where(Bug.is_deleted == False)
        
        if status:
            query = query.where(Bug.status == status)
        
        if severity:
            query = query.where(Bug.severity == severity)
        
        if assignee_id:
            query = query.where(Bug.assignee_id == assignee_id)
        
        # Filter by linked status
        if linked_only is True:
            # Has at least one link
            query = query.where(Bug.links.any())
        elif linked_only is False:
            # No links (standalone)
            query = query.where(~Bug.links.any())
        
        # Sorting
        sort_column = getattr(Bug, sort_by, Bug.updated_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_bug(
        self,
        bug_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        severity: Optional[str] = None,
        steps_to_reproduce: Optional[str] = None,
        expected_behavior: Optional[str] = None,
        actual_behavior: Optional[str] = None,
        environment: Optional[str] = None,
        assignee_id: Optional[str] = None,
        priority: Optional[str] = None,
        due_date: Optional[datetime] = None
    ) -> Optional[Bug]:
        """Update bug fields (status changes use transition_status)"""
        bug = await self.get_bug(bug_id)
        if not bug:
            return None
        
        # Only allow edits in Draft status
        if bug.status != BugStatus.DRAFT.value:
            raise ValueError(f"Bug can only be edited in Draft status. Current status: {bug.status}")
        
        if title is not None:
            bug.title = title
        if description is not None:
            bug.description = description
        if severity is not None:
            bug.severity = severity
        if steps_to_reproduce is not None:
            bug.steps_to_reproduce = steps_to_reproduce
        if expected_behavior is not None:
            bug.expected_behavior = expected_behavior
        if actual_behavior is not None:
            bug.actual_behavior = actual_behavior
        if environment is not None:
            bug.environment = environment
        if assignee_id is not None:
            bug.assignee_id = assignee_id
        if priority is not None:
            bug.priority = priority
        if due_date is not None:
            bug.due_date = due_date
        
        await self.session.commit()
        
        # Reload with relationships
        return await self.get_bug(bug_id)
    
    async def soft_delete_bug(self, bug_id: str, user_id: str) -> bool:
        """Soft delete a bug"""
        bug = await self.get_bug_for_user(bug_id, user_id)
        if not bug:
            return False
        
        bug.is_deleted = True
        bug.deleted_at = datetime.now(timezone.utc)
        await self.session.commit()
        return True
    
    # ============================================
    # STATUS TRANSITIONS
    # ============================================
    
    async def transition_status(
        self,
        bug_id: str,
        user_id: str,
        new_status: str,
        notes: Optional[str] = None
    ) -> Bug:
        """Transition bug to a new status with validation"""
        bug = await self.get_bug(bug_id)
        if not bug:
            raise ValueError("Bug not found")
        
        current_status = BugStatus(bug.status)
        target_status = BugStatus(new_status)
        
        # Validate transition
        allowed_transitions = BUG_STATUS_TRANSITIONS.get(current_status, [])
        if target_status not in allowed_transitions:
            allowed_str = ", ".join([s.value for s in allowed_transitions]) or "none"
            raise ValueError(
                f"Invalid transition from {current_status.value} to {target_status.value}. "
                f"Allowed transitions: {allowed_str}"
            )
        
        # Record history
        history = BugStatusHistory(
            bug_id=bug_id,
            from_status=current_status.value,
            to_status=target_status.value,
            changed_by=user_id,
            notes=notes
        )
        self.session.add(history)
        
        # Update status
        bug.status = target_status.value
        
        await self.session.commit()
        await self.session.refresh(bug)
        return bug
    
    async def get_status_history(self, bug_id: str) -> List[BugStatusHistory]:
        """Get status history for a bug"""
        query = select(BugStatusHistory).where(
            BugStatusHistory.bug_id == bug_id
        ).order_by(BugStatusHistory.created_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # ============================================
    # LINKING OPERATIONS
    # ============================================
    
    async def add_link(
        self,
        bug_id: str,
        entity_type: str,
        entity_id: str
    ) -> BugLink:
        """Add a link from bug to an entity"""
        # Validate entity type
        if entity_type not in [e.value for e in BugLinkEntityType]:
            raise ValueError(f"Invalid entity type: {entity_type}")
        
        # Check if link already exists
        existing = await self.session.execute(
            select(BugLink).where(and_(
                BugLink.bug_id == bug_id,
                BugLink.entity_type == entity_type,
                BugLink.entity_id == entity_id
            ))
        )
        if existing.scalar_one_or_none():
            raise ValueError("Link already exists")
        
        link = BugLink(
            bug_id=bug_id,
            entity_type=entity_type,
            entity_id=entity_id
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link
    
    async def add_links(
        self,
        bug_id: str,
        links: List[Dict[str, str]]
    ) -> List[BugLink]:
        """Add multiple links at once"""
        created_links = []
        for link_data in links:
            try:
                link = await self.add_link(
                    bug_id=bug_id,
                    entity_type=link_data["entity_type"],
                    entity_id=link_data["entity_id"]
                )
                created_links.append(link)
            except ValueError:
                # Skip duplicates
                pass
        return created_links
    
    async def remove_link(self, bug_id: str, link_id: str) -> bool:
        """Remove a specific link"""
        result = await self.session.execute(
            select(BugLink).where(and_(
                BugLink.bug_id == bug_id,
                BugLink.link_id == link_id
            ))
        )
        link = result.scalar_one_or_none()
        if not link:
            return False
        
        await self.session.delete(link)
        await self.session.commit()
        return True
    
    async def get_links(self, bug_id: str) -> List[BugLink]:
        """Get all links for a bug"""
        result = await self.session.execute(
            select(BugLink).where(BugLink.bug_id == bug_id)
        )
        return list(result.scalars().all())
    
    async def get_bugs_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        user_id: str
    ) -> List[Bug]:
        """Get all bugs linked to a specific entity"""
        query = select(Bug).join(BugLink).where(and_(
            BugLink.entity_type == entity_type,
            BugLink.entity_id == entity_id,
            Bug.user_id == user_id,
            Bug.is_deleted == False
        )).options(selectinload(Bug.links))
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # ============================================
    # AI CONVERSATION (Optional)
    # ============================================
    
    async def add_conversation_event(
        self,
        bug_id: str,
        role: str,
        content: str
    ) -> BugConversationEvent:
        """Add a conversation event for AI assistance"""
        event = BugConversationEvent(
            bug_id=bug_id,
            role=role,
            content=content
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
    
    async def get_conversation(self, bug_id: str) -> List[BugConversationEvent]:
        """Get conversation history for a bug"""
        result = await self.session.execute(
            select(BugConversationEvent).where(
                BugConversationEvent.bug_id == bug_id
            ).order_by(BugConversationEvent.created_at.asc())
        )
        return list(result.scalars().all())
