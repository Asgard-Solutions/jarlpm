"""
Feature Models for JarlPM
Features have their own lifecycle stages and conversation threads
"""
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum as PyEnum
import uuid

from sqlalchemy import (
    String, Text, Boolean, Integer, Float, DateTime, JSON,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY

from .database import Base


def generate_uuid(prefix: str = "") -> str:
    """Generate a prefixed UUID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class FeatureStage(str, PyEnum):
    """Feature lifecycle stages - mirrors epic pattern"""
    DRAFT = "draft"           # Initial AI-generated or manual draft
    REFINING = "refining"     # In conversation refinement
    APPROVED = "approved"     # User approved - locked and immutable


# Stage ordering for validation
FEATURE_STAGE_ORDER = {
    FeatureStage.DRAFT: 0,
    FeatureStage.REFINING: 1,
    FeatureStage.APPROVED: 2,
}


class Feature(Base):
    """Feature entity with its own lifecycle"""
    __tablename__ = "features"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    feature_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("feat_"))
    epic_id: Mapped[str] = mapped_column(String(50), ForeignKey("epics.epic_id", ondelete="CASCADE"), nullable=False)
    
    # Core content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    
    # Lifecycle
    current_stage: Mapped[str] = mapped_column(String(50), default=FeatureStage.DRAFT.value, nullable=False)
    
    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="ai_generated", nullable=False)  # ai_generated | manual
    
    # Priority (optional)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # MoSCoW Scoring (must_have, should_have, could_have, wont_have)
    moscow_score: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # RICE Scoring (Reach * Impact * Confidence / Effort)
    rice_reach: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-10 scale
    rice_impact: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.25, 0.5, 1, 2, 3
    rice_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.5, 0.8, 1.0
    rice_effort: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.5-10 person-months
    rice_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Calculated score
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    conversation_events: Mapped[List["FeatureConversationEvent"]] = relationship(back_populates="feature", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_features_epic_id', 'epic_id'),
        Index('idx_features_stage', 'current_stage'),
        CheckConstraint(
            "current_stage IN ('draft', 'refining', 'approved')",
            name='ck_feature_valid_stage'
        ),
    )


class FeatureConversationEvent(Base):
    """Append-only conversation history for feature refinement"""
    __tablename__ = "feature_conversation_events"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("fevt_"))
    feature_id: Mapped[str] = mapped_column(String(50), ForeignKey("features.feature_id", ondelete="CASCADE"), nullable=False)
    
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    feature: Mapped["Feature"] = relationship(back_populates="conversation_events")
    
    __table_args__ = (
        Index('idx_feature_conv_feature_id', 'feature_id'),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name='ck_feature_conv_valid_role'),
    )
