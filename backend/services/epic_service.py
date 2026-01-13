from typing import Optional, List
from datetime import datetime, timezone
import re

from models.epic import (
    Epic, EpicStage, EpicSnapshot, EpicTranscriptEvent,
    EpicDecision, PendingProposal, STAGE_ORDER, LOCKED_STAGES
)
from models.subscription import SubscriptionStatus


class EpicService:
    """Service for Epic lifecycle management with server-side enforcement"""
    
    def __init__(self, db):
        self.db = db
    
    async def check_subscription_active(self, user_id: str) -> bool:
        """Check if user has an active subscription"""
        sub_doc = await self.db.subscriptions.find_one(
            {"user_id": user_id},
            {"_id": 0}
        )
        if not sub_doc:
            return False
        return sub_doc.get("status") == SubscriptionStatus.ACTIVE.value
    
    async def create_epic(self, user_id: str, title: str) -> Epic:
        """Create a new epic"""
        epic = Epic(user_id=user_id, title=title)
        await self.db.epics.insert_one(epic.model_dump())
        return epic
    
    async def get_epic(self, epic_id: str, user_id: str) -> Optional[Epic]:
        """Get an epic by ID (with ownership check)"""
        epic_doc = await self.db.epics.find_one(
            {"epic_id": epic_id, "user_id": user_id},
            {"_id": 0}
        )
        if epic_doc:
            return Epic(**epic_doc)
        return None
    
    async def get_user_epics(self, user_id: str) -> List[Epic]:
        """Get all epics for a user"""
        cursor = self.db.epics.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("updated_at", -1)
        epics = await cursor.to_list(1000)
        return [Epic(**e) for e in epics]
    
    async def delete_epic(self, epic_id: str, user_id: str) -> bool:
        """Delete an epic and all related data (hard delete)"""
        # Verify ownership
        epic = await self.get_epic(epic_id, user_id)
        if not epic:
            return False
        
        # Delete epic and cascade to related collections
        await self.db.epics.delete_one({"epic_id": epic_id})
        await self.db.epic_transcript_events.delete_many({"epic_id": epic_id})
        await self.db.epic_decisions.delete_many({"epic_id": epic_id})
        await self.db.epic_artifacts.delete_many({"epic_id": epic_id})
        
        return True
    
    async def add_transcript_event(
        self,
        epic_id: str,
        role: str,
        content: str,
        stage: EpicStage,
        metadata: dict = None
    ) -> EpicTranscriptEvent:
        """Add an event to the transcript (append-only)"""
        event = EpicTranscriptEvent(
            epic_id=epic_id,
            role=role,
            content=content,
            stage=stage,
            metadata=metadata
        )
        await self.db.epic_transcript_events.insert_one(event.model_dump())
        return event
    
    async def get_transcript(self, epic_id: str) -> List[EpicTranscriptEvent]:
        """Get full transcript for an epic"""
        cursor = self.db.epic_transcript_events.find(
            {"epic_id": epic_id},
            {"_id": 0}
        ).sort("created_at", 1)
        events = await cursor.to_list(10000)
        return [EpicTranscriptEvent(**e) for e in events]
    
    async def get_conversation_history(self, epic_id: str, limit: int = 20) -> List[dict]:
        """Get recent conversation history for LLM context"""
        cursor = self.db.epic_transcript_events.find(
            {"epic_id": epic_id, "role": {"$in": ["user", "assistant"]}},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        events = await cursor.to_list(limit)
        events.reverse()  # Oldest first
        
        return [{"role": e["role"], "content": e["content"]} for e in events]
    
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
        await self.db.epic_decisions.insert_one(decision.model_dump())
        return decision
    
    async def get_decisions(self, epic_id: str) -> List[EpicDecision]:
        """Get all decisions for an epic"""
        cursor = self.db.epic_decisions.find(
            {"epic_id": epic_id},
            {"_id": 0}
        ).sort("created_at", 1)
        decisions = await cursor.to_list(1000)
        return [EpicDecision(**d) for d in decisions]
    
    def can_advance_stage(self, current_stage: EpicStage, target_stage: EpicStage) -> bool:
        """Check if stage advancement is valid (monotonic progression only)"""
        current_order = STAGE_ORDER.get(current_stage, -1)
        target_order = STAGE_ORDER.get(target_stage, -1)
        
        # Can only advance forward by exactly one stage
        return target_order == current_order + 1
    
    def get_next_stage(self, current_stage: EpicStage) -> Optional[EpicStage]:
        """Get the next stage in the progression"""
        current_order = STAGE_ORDER.get(current_stage, -1)
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
    ) -> PendingProposal:
        """Set a pending proposal on an epic"""
        epic = await self.get_epic(epic_id, user_id)
        if not epic:
            raise ValueError("Epic not found")
        
        proposal = PendingProposal(
            field=field,
            proposed_content=content,
            target_stage=target_stage
        )
        
        await self.db.epics.update_one(
            {"epic_id": epic_id},
            {
                "$set": {
                    "pending_proposal": proposal.model_dump(),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return proposal
    
    async def confirm_proposal(self, epic_id: str, user_id: str, proposal_id: str) -> Epic:
        """Confirm a pending proposal and advance the stage"""
        epic = await self.get_epic(epic_id, user_id)
        if not epic:
            raise ValueError("Epic not found")
        
        if not epic.pending_proposal:
            raise ValueError("No pending proposal to confirm")
        
        if epic.pending_proposal.proposal_id != proposal_id:
            raise ValueError("Proposal ID mismatch")
        
        proposal = epic.pending_proposal
        
        # Validate stage advancement
        if not self.can_advance_stage(epic.current_stage, proposal.target_stage):
            raise ValueError(f"Cannot advance from {epic.current_stage} to {proposal.target_stage}")
        
        # Build update based on field
        snapshot_update = {}
        if proposal.field == "problem_statement":
            snapshot_update["snapshot.problem_statement"] = proposal.proposed_content
            snapshot_update["snapshot.problem_confirmed_at"] = datetime.now(timezone.utc)
        elif proposal.field == "desired_outcome":
            snapshot_update["snapshot.desired_outcome"] = proposal.proposed_content
            snapshot_update["snapshot.outcome_confirmed_at"] = datetime.now(timezone.utc)
        elif proposal.field == "epic_final":
            # Parse epic summary and acceptance criteria
            parsed = self._parse_epic_final(proposal.proposed_content)
            snapshot_update["snapshot.epic_summary"] = parsed.get("summary", proposal.proposed_content)
            snapshot_update["snapshot.acceptance_criteria"] = parsed.get("criteria", [])
            snapshot_update["snapshot.epic_locked_at"] = datetime.now(timezone.utc)
        
        # Update epic
        await self.db.epics.update_one(
            {"epic_id": epic_id},
            {
                "$set": {
                    **snapshot_update,
                    "current_stage": proposal.target_stage.value,
                    "pending_proposal": None,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Record decision
        await self.add_decision(
            epic_id=epic_id,
            user_id=user_id,
            decision_type="confirm_proposal",
            from_stage=epic.current_stage,
            to_stage=proposal.target_stage,
            proposal_id=proposal_id,
            content_snapshot=proposal.proposed_content
        )
        
        return await self.get_epic(epic_id, user_id)
    
    async def reject_proposal(self, epic_id: str, user_id: str, proposal_id: str) -> Epic:
        """Reject a pending proposal"""
        epic = await self.get_epic(epic_id, user_id)
        if not epic:
            raise ValueError("Epic not found")
        
        if not epic.pending_proposal:
            raise ValueError("No pending proposal to reject")
        
        if epic.pending_proposal.proposal_id != proposal_id:
            raise ValueError("Proposal ID mismatch")
        
        # Clear proposal
        await self.db.epics.update_one(
            {"epic_id": epic_id},
            {
                "$set": {
                    "pending_proposal": None,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Record decision
        await self.add_decision(
            epic_id=epic_id,
            user_id=user_id,
            decision_type="reject_proposal",
            from_stage=epic.current_stage,
            proposal_id=proposal_id,
            content_snapshot=epic.pending_proposal.proposed_content
        )
        
        return await self.get_epic(epic_id, user_id)
    
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
            # Split by lines starting with - or numbers
            criteria = re.findall(r'^\s*[-\d.]+\s*(.+)$', criteria_text, re.MULTILINE)
            result["criteria"] = [c.strip() for c in criteria if c.strip()]
        
        return result
