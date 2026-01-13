from typing import Optional, List
from datetime import datetime, timezone
import re

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Epic, EpicStage, EpicSnapshot, EpicTranscriptEvent,
    EpicDecision, Subscription, SubscriptionStatus, STAGE_ORDER
)


class EpicService:
    """Service for Epic lifecycle management with server-side enforcement"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def check_subscription_active(self, user_id: str) -> bool:
        """Check if user has an active subscription"""
        result = await self.session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        sub = result.scalar_one_or_none()
        return sub is not None and sub.status == SubscriptionStatus.ACTIVE.value
    
    async def create_epic(self, user_id: str, title: str) -> Epic:
        """Create a new epic with initial snapshot"""
        epic = Epic(user_id=user_id, title=title)
        self.session.add(epic)
        await self.session.flush()  # Get the epic_id
        
        # Create empty snapshot
        snapshot = EpicSnapshot(epic_id=epic.epic_id)
        self.session.add(snapshot)
        
        await self.session.commit()
        await self.session.refresh(epic)
        return epic
    
    async def get_epic(self, epic_id: str, user_id: str) -> Optional[Epic]:
        """Get an epic by ID (with ownership check)"""
        result = await self.session.execute(
            select(Epic)
            .options(selectinload(Epic.snapshot))
            .where(and_(Epic.epic_id == epic_id, Epic.user_id == user_id))
        )
        return result.scalar_one_or_none()
    
    async def get_user_epics(self, user_id: str) -> List[Epic]:
        """Get all epics for a user"""
        result = await self.session.execute(
            select(Epic)
            .options(selectinload(Epic.snapshot))
            .where(Epic.user_id == user_id)
            .order_by(Epic.updated_at.desc())
        )
        return list(result.scalars().all())
    
    async def delete_epic(self, epic_id: str, user_id: str) -> bool:
        """Delete an epic and all related data (hard delete with cascade)"""
        epic = await self.get_epic(epic_id, user_id)
        if not epic:
            return False
        
        # Enable cascade delete for append-only tables
        await self.session.execute(
            select(1).execution_options(
                schema_translate_map={"jarlpm.allow_cascade_delete": "true"}
            )
        )
        
        # Delete will cascade to all related tables
        await self.session.delete(epic)
        await self.session.commit()
        return True
    
    async def add_transcript_event(
        self,
        epic_id: str,
        role: str,
        content: str,
        stage: EpicStage,
        event_metadata: dict = None
    ) -> EpicTranscriptEvent:
        """Add an event to the transcript (append-only)"""
        event = EpicTranscriptEvent(
            epic_id=epic_id,
            role=role,
            content=content,
            stage=stage,
            event_metadata=event_metadata
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
    
    async def get_transcript(self, epic_id: str) -> List[EpicTranscriptEvent]:
        """Get full transcript for an epic"""
        result = await self.session.execute(
            select(EpicTranscriptEvent)
            .where(EpicTranscriptEvent.epic_id == epic_id)
            .order_by(EpicTranscriptEvent.created_at.asc())
        )
        return list(result.scalars().all())
    
    async def get_conversation_history(self, epic_id: str, limit: int = 20) -> List[dict]:
        """Get recent conversation history for LLM context"""
        result = await self.session.execute(
            select(EpicTranscriptEvent)
            .where(
                and_(
                    EpicTranscriptEvent.epic_id == epic_id,
                    EpicTranscriptEvent.role.in_(['user', 'assistant'])
                )
            )
            .order_by(EpicTranscriptEvent.created_at.desc())
            .limit(limit)
        )
        events = list(result.scalars().all())
        events.reverse()  # Oldest first
        return [{"role": e.role, "content": e.content} for e in events]
    
    async def add_decision(
        self,
        epic_id: str,
        user_id: str,
        decision_type: str,
        from_stage: EpicStage,
        to_stage: EpicStage = None,
        proposal_id: str = None,
        content_snapshot: str = None
    ) -> EpicDecision:
        """Record a decision (append-only)"""
        decision = EpicDecision(
            epic_id=epic_id,
            user_id=user_id,
            decision_type=decision_type,
            from_stage=from_stage,
            to_stage=to_stage,
            proposal_id=proposal_id,
            content_snapshot=content_snapshot
        )
        self.session.add(decision)
        await self.session.commit()
        await self.session.refresh(decision)
        return decision
    
    async def get_decisions(self, epic_id: str) -> List[EpicDecision]:
        """Get all decisions for an epic"""
        result = await self.session.execute(
            select(EpicDecision)
            .where(EpicDecision.epic_id == epic_id)
            .order_by(EpicDecision.created_at.asc())
        )
        return list(result.scalars().all())
    
    def can_advance_stage(self, current_stage: str, target_stage: str) -> bool:
        """Check if stage advancement is valid (monotonic progression only)"""
        # Convert string to enum for comparison
        try:
            current_enum = EpicStage(current_stage) if isinstance(current_stage, str) else current_stage
            target_enum = EpicStage(target_stage) if isinstance(target_stage, str) else target_stage
        except ValueError:
            return False
        current_order = STAGE_ORDER.get(current_enum, -1)
        target_order = STAGE_ORDER.get(target_enum, -1)
        # Can only advance forward by exactly one stage
        return target_order == current_order + 1
    
    def get_next_stage(self, current_stage: str) -> Optional[EpicStage]:
        """Get the next stage in the progression"""
        try:
            current_enum = EpicStage(current_stage) if isinstance(current_stage, str) else current_stage
        except ValueError:
            return None
        current_order = STAGE_ORDER.get(current_enum, -1)
        for stage, order in STAGE_ORDER.items():
            if order == current_order + 1:
                return stage
        return None
    
    async def set_pending_proposal(
        self,
        epic_id: str,
        user_id: str,
        field: str,
        content: str,
        target_stage: EpicStage
    ) -> dict:
        """Set a pending proposal on an epic"""
        epic = await self.get_epic(epic_id, user_id)
        if not epic:
            raise ValueError("Epic not found")
        
        import uuid
        target_stage_value = target_stage.value if isinstance(target_stage, EpicStage) else target_stage
        proposal = {
            "proposal_id": f"prop_{uuid.uuid4().hex[:12]}",
            "field": field,
            "proposed_content": content,
            "proposed_at": datetime.now(timezone.utc).isoformat(),
            "target_stage": target_stage_value
        }
        
        epic.pending_proposal = proposal
        epic.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        
        return proposal
    
    async def confirm_proposal(self, epic_id: str, user_id: str, proposal_id: str) -> Epic:
        """Confirm a pending proposal and advance the stage (TRANSACTIONAL)"""
        async with self.session.begin_nested():
            epic = await self.get_epic(epic_id, user_id)
            if not epic:
                raise ValueError("Epic not found")
            
            if not epic.pending_proposal:
                raise ValueError("No pending proposal to confirm")
            
            if epic.pending_proposal.get("proposal_id") != proposal_id:
                raise ValueError("Proposal ID mismatch")
            
            proposal = epic.pending_proposal
            target_stage = EpicStage(proposal["target_stage"])
            
            # Validate stage advancement (also enforced by DB trigger)
            if not self.can_advance_stage(epic.current_stage, target_stage):
                raise ValueError(f"Cannot advance from {epic.current_stage} to {target_stage}")
            
            # Get or create snapshot
            snapshot = epic.snapshot
            if not snapshot:
                snapshot = EpicSnapshot(epic_id=epic.epic_id)
                self.session.add(snapshot)
            
            # Update snapshot based on field
            field = proposal["field"]
            content = proposal["proposed_content"]
            now = datetime.now(timezone.utc)
            
            if field == "problem_statement":
                snapshot.problem_statement = content
                snapshot.problem_confirmed_at = now
            elif field == "desired_outcome":
                snapshot.desired_outcome = content
                snapshot.outcome_confirmed_at = now
            elif field == "epic_final":
                parsed = self._parse_epic_final(content)
                snapshot.epic_summary = parsed.get("summary", content)
                snapshot.acceptance_criteria = parsed.get("criteria", [])
                snapshot.epic_locked_at = now
            
            # Advance stage (enforced by DB trigger for monotonic progression)
            epic.current_stage = target_stage
            epic.pending_proposal = None
            epic.updated_at = now
            
            # Record decision (append-only)
            decision = EpicDecision(
                epic_id=epic_id,
                user_id=user_id,
                decision_type="confirm_proposal",
                from_stage=EpicStage(proposal["target_stage"]),  # Previous stage
                to_stage=target_stage,
                proposal_id=proposal_id,
                content_snapshot=content
            )
            self.session.add(decision)
        
        await self.session.commit()
        await self.session.refresh(epic)
        return epic
    
    async def reject_proposal(self, epic_id: str, user_id: str, proposal_id: str) -> Epic:
        """Reject a pending proposal"""
        epic = await self.get_epic(epic_id, user_id)
        if not epic:
            raise ValueError("Epic not found")
        
        if not epic.pending_proposal:
            raise ValueError("No pending proposal to reject")
        
        if epic.pending_proposal.get("proposal_id") != proposal_id:
            raise ValueError("Proposal ID mismatch")
        
        content = epic.pending_proposal.get("proposed_content", "")
        
        # Record rejection decision
        decision = EpicDecision(
            epic_id=epic_id,
            user_id=user_id,
            decision_type="reject_proposal",
            from_stage=epic.current_stage,
            proposal_id=proposal_id,
            content_snapshot=content
        )
        self.session.add(decision)
        
        # Clear proposal
        epic.pending_proposal = None
        epic.updated_at = datetime.now(timezone.utc)
        
        await self.session.commit()
        await self.session.refresh(epic)
        return epic
    
    def _parse_epic_final(self, content: str) -> dict:
        """Parse epic final proposal into summary and criteria"""
        result = {"summary": "", "criteria": []}
        
        # Try to extract summary
        summary_match = re.search(r'Summary:\s*(.+?)(?=Acceptance Criteria:|$)', content, re.DOTALL | re.IGNORECASE)
        if summary_match:
            result["summary"] = summary_match.group(1).strip()
        else:
            result["summary"] = content
        
        # Try to extract criteria
        criteria_match = re.search(r'Acceptance Criteria:\s*(.+)', content, re.DOTALL | re.IGNORECASE)
        if criteria_match:
            criteria_text = criteria_match.group(1).strip()
            criteria = re.findall(r'^\\s*[-\\d.]+\\s*(.+)$', criteria_text, re.MULTILINE)
            result["criteria"] = [c.strip() for c in criteria if c.strip()]
        
        return result
