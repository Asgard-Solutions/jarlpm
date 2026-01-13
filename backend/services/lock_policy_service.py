"""
JarlPM Lock Policy Service

Central policy module for enforcing state-driven locking rules across
Epic → Feature → User Story hierarchy.

Design Intent:
- Epics lock WHAT/WHY (Problem + Outcome)
- Features organize scope
- Stories evolve HOW — until Epic locks

This module is the SINGLE SOURCE OF TRUTH for all mutation permissions.
Backend is the bouncer - no UI-only enforcement.
"""
from enum import Enum as PyEnum
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass


class EpicStatus(str, PyEnum):
    """
    High-level Epic status for locking decisions.
    Derived from current_stage but simpler for policy decisions.
    """
    DRAFT = "draft"           # Problem/Outcome editable, full CRUD on children
    IN_PROGRESS = "in_progress"  # Problem/Outcome locked, limited edits
    LOCKED = "locked"         # Everything immutable
    ARCHIVED = "archived"     # Soft delete (optional)


# Map EpicStage to EpicStatus
STAGE_TO_STATUS = {
    "problem_capture": EpicStatus.DRAFT,
    "problem_confirmed": EpicStatus.IN_PROGRESS,  # Problem is now locked
    "outcome_capture": EpicStatus.IN_PROGRESS,
    "outcome_confirmed": EpicStatus.IN_PROGRESS,
    "epic_drafted": EpicStatus.IN_PROGRESS,
    "epic_locked": EpicStatus.LOCKED,
}


@dataclass
class PolicyResult:
    """Result of a policy check"""
    allowed: bool
    reason: Optional[str] = None
    field_errors: Optional[Dict[str, str]] = None


class LockPolicyService:
    """
    Central policy service for all mutation permissions.
    
    Usage:
        policy = LockPolicyService()
        result = policy.can_edit_epic_field(epic_status, "problem_statement")
        if not result.allowed:
            raise HTTPException(409, result.reason)
    """
    
    @staticmethod
    def get_epic_status(current_stage: str) -> EpicStatus:
        """Convert EpicStage to EpicStatus for policy decisions"""
        return STAGE_TO_STATUS.get(current_stage, EpicStatus.DRAFT)
    
    @staticmethod
    def derive_feature_locked(epic_status: EpicStatus) -> bool:
        """Features are locked when Epic is locked"""
        return epic_status == EpicStatus.LOCKED
    
    @staticmethod
    def derive_story_frozen(epic_status: EpicStatus) -> bool:
        """Stories are frozen when Epic is locked"""
        return epic_status == EpicStatus.LOCKED
    
    # ============================================
    # EPIC POLICY CHECKS
    # ============================================
    
    def can_edit_epic(self, epic_status: EpicStatus) -> PolicyResult:
        """Check if any Epic edits are allowed"""
        if epic_status == EpicStatus.LOCKED:
            return PolicyResult(
                allowed=False,
                reason="Epic is locked. No modifications allowed."
            )
        if epic_status == EpicStatus.ARCHIVED:
            return PolicyResult(
                allowed=False,
                reason="Epic is archived. No modifications allowed."
            )
        return PolicyResult(allowed=True)
    
    def can_edit_epic_field(
        self, 
        epic_status: EpicStatus, 
        field: str,
        current_stage: Optional[str] = None
    ) -> PolicyResult:
        """Check if a specific Epic field can be edited"""
        
        # Locked/Archived epics cannot be edited at all
        if epic_status in (EpicStatus.LOCKED, EpicStatus.ARCHIVED):
            return PolicyResult(
                allowed=False,
                reason=f"Epic is {epic_status.value}. Field '{field}' cannot be modified.",
                field_errors={field: f"Cannot modify '{field}' on {epic_status.value} Epic"}
            )
        
        # Problem fields (problem_statement)
        if field in ("problem_statement", "problem"):
            if epic_status != EpicStatus.DRAFT or (current_stage and current_stage != "problem_capture"):
                return PolicyResult(
                    allowed=False,
                    reason="Problem statement is locked after confirmation.",
                    field_errors={field: "Problem statement cannot be modified after Epic leaves problem_capture stage"}
                )
        
        # Outcome fields (desired_outcome)
        if field in ("desired_outcome", "outcome"):
            if epic_status != EpicStatus.DRAFT:
                # Check if we're past outcome capture
                if current_stage and current_stage not in ("problem_capture", "problem_confirmed", "outcome_capture"):
                    return PolicyResult(
                        allowed=False,
                        reason="Desired outcome is locked after confirmation.",
                        field_errors={field: "Desired outcome cannot be modified after outcome confirmation"}
                    )
            if current_stage == "problem_capture":
                return PolicyResult(
                    allowed=False,
                    reason="Define problem statement first.",
                    field_errors={field: "Cannot set outcome before problem is defined"}
                )
        
        # Title can be edited until locked
        if field == "title":
            if epic_status == EpicStatus.LOCKED:
                return PolicyResult(
                    allowed=False,
                    reason="Epic title is locked.",
                    field_errors={field: "Title cannot be modified on locked Epic"}
                )
        
        return PolicyResult(allowed=True)
    
    def can_transition_epic(
        self, 
        from_status: EpicStatus, 
        to_status: EpicStatus,
        lock_confirmed: bool = False
    ) -> PolicyResult:
        """Check if Epic status transition is allowed"""
        
        # Define allowed transitions
        allowed_transitions = {
            EpicStatus.DRAFT: {EpicStatus.IN_PROGRESS},
            EpicStatus.IN_PROGRESS: {EpicStatus.LOCKED, EpicStatus.ARCHIVED},
            EpicStatus.LOCKED: {EpicStatus.ARCHIVED},  # Can archive locked epics
            EpicStatus.ARCHIVED: set(),  # Cannot transition out of archived
        }
        
        if to_status not in allowed_transitions.get(from_status, set()):
            return PolicyResult(
                allowed=False,
                reason=f"Cannot transition from {from_status.value} to {to_status.value}"
            )
        
        # Lock requires confirmation
        if to_status == EpicStatus.LOCKED and not lock_confirmed:
            return PolicyResult(
                allowed=False,
                reason="Lock must be confirmed before transition. Call confirm-lock first."
            )
        
        return PolicyResult(allowed=True)
    
    def can_confirm_lock(self, epic_status: EpicStatus) -> PolicyResult:
        """Check if lock confirmation is allowed"""
        if epic_status != EpicStatus.IN_PROGRESS:
            return PolicyResult(
                allowed=False,
                reason=f"Lock can only be confirmed from IN_PROGRESS status. Current: {epic_status.value}"
            )
        return PolicyResult(allowed=True)
    
    # ============================================
    # FEATURE POLICY CHECKS
    # ============================================
    
    def can_mutate_features(self, epic_status: EpicStatus) -> PolicyResult:
        """
        Check if Feature mutations are allowed at all.
        
        NOTE: Feature Planning Mode happens WHEN epic is LOCKED (epic_locked stage).
        Features can be created, edited, and deleted during this mode.
        Only ARCHIVED epics prevent feature mutations.
        """
        if epic_status == EpicStatus.ARCHIVED:
            return PolicyResult(
                allowed=False,
                reason="Epic is archived. Features cannot be modified."
            )
        return PolicyResult(allowed=True)
    
    def can_create_feature(self, epic_status: EpicStatus) -> PolicyResult:
        """
        Check if new Features can be created.
        
        Features are created AFTER epic is locked (Feature Planning Mode).
        """
        if epic_status == EpicStatus.ARCHIVED:
            return PolicyResult(
                allowed=False,
                reason="Cannot add Features to an archived Epic."
            )
        # Features can be created when epic is LOCKED (Feature Planning Mode)
        return PolicyResult(allowed=True)
    
    def can_edit_feature(
        self, 
        epic_status: EpicStatus,
        field: str = None
    ) -> PolicyResult:
        """
        Check if Feature can be edited.
        
        Features can be edited while they are in draft/refining stage.
        Individual feature approval is checked at the service layer.
        """
        if epic_status == EpicStatus.ARCHIVED:
            return PolicyResult(
                allowed=False,
                reason="Cannot edit Features on an archived Epic.",
                field_errors={field: "Feature locked"} if field else None
            )
        
        return PolicyResult(allowed=True)
    
    def can_delete_feature(self, epic_status: EpicStatus) -> PolicyResult:
        """
        Check if Feature can be deleted.
        
        Features can be deleted during Feature Planning Mode.
        """
        if epic_status == EpicStatus.ARCHIVED:
            return PolicyResult(
                allowed=False,
                reason="Cannot delete Features from an archived Epic."
            )
        return PolicyResult(allowed=True)
    
    def can_reorder_features(self, epic_status: EpicStatus) -> PolicyResult:
        """Check if Features can be reordered"""
        if epic_status == EpicStatus.ARCHIVED:
            return PolicyResult(
                allowed=False,
                reason="Cannot reorder Features on an archived Epic."
            )
        return PolicyResult(allowed=True)
    
    # ============================================
    # USER STORY POLICY CHECKS
    # ============================================
    
    def can_mutate_stories(self, epic_status: EpicStatus) -> PolicyResult:
        """Check if User Story mutations are allowed at all"""
        if epic_status == EpicStatus.LOCKED:
            return PolicyResult(
                allowed=False,
                reason="Epic is locked. User Stories cannot be added, modified, or deleted."
            )
        if epic_status == EpicStatus.ARCHIVED:
            return PolicyResult(
                allowed=False,
                reason="Epic is archived. User Stories cannot be modified."
            )
        return PolicyResult(allowed=True)
    
    def can_create_story(self, epic_status: EpicStatus) -> PolicyResult:
        """Check if new User Stories can be created"""
        if epic_status == EpicStatus.LOCKED:
            return PolicyResult(
                allowed=False,
                reason="Cannot add User Stories to a locked Epic."
            )
        return PolicyResult(allowed=True)
    
    def can_edit_story(self, epic_status: EpicStatus) -> PolicyResult:
        """Check if User Story can be edited"""
        if epic_status == EpicStatus.LOCKED:
            return PolicyResult(
                allowed=False,
                reason="Cannot edit User Stories on a locked Epic."
            )
        return PolicyResult(allowed=True)
    
    def requires_story_version(self, epic_status: EpicStatus) -> bool:
        """
        Check if editing a story requires creating a new version.
        In IN_PROGRESS, edits must create versions to preserve history.
        """
        return epic_status == EpicStatus.IN_PROGRESS
    
    def can_delete_story(self, epic_status: EpicStatus) -> PolicyResult:
        """Check if User Story can be deleted"""
        if epic_status == EpicStatus.LOCKED:
            return PolicyResult(
                allowed=False,
                reason="Cannot delete User Stories from a locked Epic."
            )
        return PolicyResult(allowed=True)
    
    # ============================================
    # COMPOSITE CHECKS
    # ============================================
    
    def get_edit_permissions(self, epic_status: EpicStatus, current_stage: str = None) -> Dict[str, Any]:
        """Get all edit permissions for an Epic and its children"""
        return {
            "epic": {
                "status": epic_status.value,
                "can_edit": self.can_edit_epic(epic_status).allowed,
                "fields": {
                    "title": self.can_edit_epic_field(epic_status, "title", current_stage).allowed,
                    "problem_statement": self.can_edit_epic_field(epic_status, "problem_statement", current_stage).allowed,
                    "desired_outcome": self.can_edit_epic_field(epic_status, "desired_outcome", current_stage).allowed,
                },
                "can_confirm_lock": self.can_confirm_lock(epic_status).allowed,
            },
            "features": {
                "can_create": self.can_create_feature(epic_status).allowed,
                "can_edit": self.can_edit_feature(epic_status).allowed,
                "can_delete": self.can_delete_feature(epic_status).allowed,
                "can_reorder": self.can_reorder_features(epic_status).allowed,
                "is_locked": self.derive_feature_locked(epic_status),
            },
            "stories": {
                "can_create": self.can_create_story(epic_status).allowed,
                "can_edit": self.can_edit_story(epic_status).allowed,
                "can_delete": self.can_delete_story(epic_status).allowed,
                "is_frozen": self.derive_story_frozen(epic_status),
                "requires_version": self.requires_story_version(epic_status),
            },
        }


# Singleton instance for convenience
lock_policy = LockPolicyService()
