from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


class EpicStage(str, Enum):
    PROBLEM_CAPTURE = "problem_capture"
    PROBLEM_CONFIRMED = "problem_confirmed"
    OUTCOME_CAPTURE = "outcome_capture"
    OUTCOME_CONFIRMED = "outcome_confirmed"
    EPIC_DRAFTED = "epic_drafted"
    EPIC_LOCKED = "epic_locked"


# Stage ordering for monotonic progression
STAGE_ORDER = {
    EpicStage.PROBLEM_CAPTURE: 0,
    EpicStage.PROBLEM_CONFIRMED: 1,
    EpicStage.OUTCOME_CAPTURE: 2,
    EpicStage.OUTCOME_CONFIRMED: 3,
    EpicStage.EPIC_DRAFTED: 4,
    EpicStage.EPIC_LOCKED: 5,
}

# Stages that are locked (immutable once reached)
LOCKED_STAGES = {
    EpicStage.PROBLEM_CONFIRMED,
    EpicStage.OUTCOME_CONFIRMED,
    EpicStage.EPIC_LOCKED,
}


class ArtifactType(str, Enum):
    FEATURE = "feature"
    USER_STORY = "user_story"
    BUG = "bug"


class EpicSnapshot(BaseModel):
    """Canonical snapshot of epic content at a point in time"""
    model_config = ConfigDict(extra="ignore")
    
    problem_statement: Optional[str] = None
    problem_confirmed_at: Optional[datetime] = None
    
    desired_outcome: Optional[str] = None
    outcome_confirmed_at: Optional[datetime] = None
    
    epic_summary: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    epic_locked_at: Optional[datetime] = None


class PendingProposal(BaseModel):
    """Pending proposal that requires user confirmation"""
    model_config = ConfigDict(extra="ignore")
    
    proposal_id: str = Field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:12]}")
    field: str  # Which field this proposal is for (e.g., 'problem_statement', 'epic_summary')
    proposed_content: str
    proposed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target_stage: EpicStage  # Stage to advance to if confirmed


class Epic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    epic_id: str = Field(default_factory=lambda: f"epic_{uuid.uuid4().hex[:12]}")
    user_id: str
    title: str
    current_stage: EpicStage = EpicStage.PROBLEM_CAPTURE
    snapshot: EpicSnapshot = Field(default_factory=EpicSnapshot)
    pending_proposal: Optional[PendingProposal] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EpicTranscriptEvent(BaseModel):
    """Append-only conversation history"""
    model_config = ConfigDict(extra="ignore")
    
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    epic_id: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    stage: EpicStage
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EpicDecision(BaseModel):
    """Append-only decision log"""
    model_config = ConfigDict(extra="ignore")
    
    decision_id: str = Field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}")
    epic_id: str
    decision_type: str  # 'confirm_proposal', 'reject_proposal', 'stage_advance'
    from_stage: EpicStage
    to_stage: Optional[EpicStage] = None
    proposal_id: Optional[str] = None
    content_snapshot: Optional[str] = None  # What was confirmed
    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EpicArtifact(BaseModel):
    """Features, User Stories, Bugs linked to an Epic"""
    model_config = ConfigDict(extra="ignore")
    
    artifact_id: str = Field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    epic_id: str
    artifact_type: ArtifactType
    title: str
    description: str
    acceptance_criteria: Optional[List[str]] = None
    priority: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request/Response models
class EpicCreate(BaseModel):
    title: str


class EpicChatMessage(BaseModel):
    content: str


class EpicConfirmProposal(BaseModel):
    proposal_id: str
    confirmed: bool  # True to confirm, False to reject


class ArtifactCreate(BaseModel):
    artifact_type: ArtifactType
    title: str
    description: str
    acceptance_criteria: Optional[List[str]] = None
    priority: Optional[int] = None
