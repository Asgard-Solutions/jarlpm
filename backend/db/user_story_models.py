"""
User Story Models for JarlPM
User Stories have their own lifecycle stages and conversation threads
Stories are created from Features and follow the standard user story format
Includes versioning support for edit history tracking
"""
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum as PyEnum
import uuid

from sqlalchemy import (
    String, Text, Boolean, Integer, DateTime, JSON,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY

from .database import Base


def generate_uuid(prefix: str = "") -> str:
    """Generate a prefixed UUID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class UserStoryStage(str, PyEnum):
    """User Story lifecycle stages - mirrors feature pattern"""
    DRAFT = "draft"           # Initial AI-generated or manual draft
    REFINING = "refining"     # In conversation refinement
    APPROVED = "approved"     # User approved - locked and immutable


# Stage ordering for validation
USER_STORY_STAGE_ORDER = {
    UserStoryStage.DRAFT: 0,
    UserStoryStage.REFINING: 1,
    UserStoryStage.APPROVED: 2,
}


class UserStory(Base):
    """User Story entity with its own lifecycle and versioning
    
    Stories can be:
    1. Feature-bound: Created from a Feature (traditional flow)
    2. Standalone: Independent stories not tied to any feature
    """
    __tablename__ = "user_stories"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    story_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("story_"))
    
    # For feature-bound stories
    feature_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("features.feature_id", ondelete="CASCADE"), nullable=True)
    
    # For standalone stories (required when feature_id is null)
    user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Standard User Story format: As a [persona], I want to [action] so that [benefit]
    persona: Mapped[str] = mapped_column(String(200), nullable=False)  # The user role/persona
    action: Mapped[str] = mapped_column(Text, nullable=False)          # What they want to do
    benefit: Mapped[str] = mapped_column(Text, nullable=False)         # Why they want to do it
    
    # Full story text (computed from above, but stored for display)
    story_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Optional title for standalone stories
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Acceptance Criteria in Given/When/Then format
    acceptance_criteria: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    
    # Lifecycle
    current_stage: Mapped[str] = mapped_column(String(50), default=UserStoryStage.DRAFT.value, nullable=False)
    
    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="ai_generated", nullable=False)  # ai_generated | manual
    
    # Story points (optional - for sprint planning)
    story_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Priority order within feature or standalone list
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Versioning support
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_story_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Lineage for versions
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Derived from Epic lock but stored for performance
    
    # Standalone stories can be linked to epics/features/bugs optionally
    is_standalone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    conversation_events: Mapped[List["UserStoryConversationEvent"]] = relationship(back_populates="user_story", cascade="all, delete-orphan")
    versions: Mapped[List["UserStoryVersion"]] = relationship(back_populates="story", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_user_stories_feature_id', 'feature_id'),
        Index('idx_user_stories_user_id', 'user_id'),
        Index('idx_user_stories_stage', 'current_stage'),
        Index('idx_user_stories_parent', 'parent_story_id'),
        Index('idx_user_stories_standalone', 'is_standalone'),
        CheckConstraint(
            "current_stage IN ('draft', 'refining', 'approved')",
            name='ck_user_story_valid_stage'
        ),
    )


class UserStoryVersion(Base):
    """
    Append-only version history for user stories.
    Created whenever a story is edited in IN_PROGRESS epic status.
    """
    __tablename__ = "user_story_versions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("sver_"))
    story_id: Mapped[str] = mapped_column(String(50), ForeignKey("user_stories.story_id", ondelete="CASCADE"), nullable=False)
    
    # Version number (1, 2, 3, ...)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Full snapshot of the story at this version
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Who created this version
    created_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    story: Mapped["UserStory"] = relationship(back_populates="versions")
    
    __table_args__ = (
        Index('idx_story_versions_story_id', 'story_id'),
        Index('idx_story_versions_version', 'story_id', 'version'),
    )


class UserStoryConversationEvent(Base):
    """Append-only conversation history for user story refinement"""
    __tablename__ = "user_story_conversation_events"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("sevt_"))
    story_id: Mapped[str] = mapped_column(String(50), ForeignKey("user_stories.story_id", ondelete="CASCADE"), nullable=False)
    
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user_story: Mapped["UserStory"] = relationship(back_populates="conversation_events")
    
    __table_args__ = (
        Index('idx_user_story_conv_story_id', 'story_id'),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name='ck_user_story_conv_valid_role'),
    )

