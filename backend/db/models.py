"""
JarlPM Database Models
SQLAlchemy 2.0 with PostgreSQL

Enforces:
- Relational integrity via foreign keys
- Append-only constraints (via triggers)
- Monotonic stage progression (via triggers)
- Locked content immutability (via triggers)
"""
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum as PyEnum
import uuid

from sqlalchemy import (
    String, Text, Boolean, Integer, Float, DateTime, JSON,
    ForeignKey, Index, CheckConstraint, UniqueConstraint,
    event, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY

from .database import Base


def generate_uuid(prefix: str = "") -> str:
    """Generate a prefixed UUID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# ============================================
# ENUMS (Python-side for type safety)
# ============================================

class SubscriptionStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIAL = "trial"


class LLMProvider(str, PyEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class EpicStage(str, PyEnum):
    PROBLEM_CAPTURE = "problem_capture"
    PROBLEM_CONFIRMED = "problem_confirmed"
    OUTCOME_CAPTURE = "outcome_capture"
    OUTCOME_CONFIRMED = "outcome_confirmed"
    EPIC_DRAFTED = "epic_drafted"
    EPIC_LOCKED = "epic_locked"


class ArtifactType(str, PyEnum):
    FEATURE = "feature"
    USER_STORY = "user_story"
    BUG = "bug"


class PaymentStatus(str, PyEnum):
    INITIATED = "initiated"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class DeliveryMethodology(str, PyEnum):
    WATERFALL = "waterfall"
    AGILE = "agile"
    SCRUM = "scrum"
    KANBAN = "kanban"
    HYBRID = "hybrid"


class DeliveryPlatform(str, PyEnum):
    JIRA = "jira"
    AZURE_DEVOPS = "azure_devops"
    NONE = "none"
    OTHER = "other"


# Stage ordering for validation
STAGE_ORDER = {
    EpicStage.PROBLEM_CAPTURE: 0,
    EpicStage.PROBLEM_CONFIRMED: 1,
    EpicStage.OUTCOME_CAPTURE: 2,
    EpicStage.OUTCOME_CONFIRMED: 3,
    EpicStage.EPIC_DRAFTED: 4,
    EpicStage.EPIC_LOCKED: 5,
}

LOCKED_STAGES = {
    EpicStage.PROBLEM_CONFIRMED,
    EpicStage.OUTCOME_CONFIRMED,
    EpicStage.EPIC_LOCKED,
}


# ============================================
# USER MODELS
# ============================================

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("user_"))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    sessions: Mapped[List["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscription: Mapped[Optional["Subscription"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    llm_configs: Mapped[List["LLMProviderConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    epics: Mapped[List["Epic"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_users_user_id', 'user_id'),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, default=lambda: generate_uuid("sess_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    session_token: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    
    __table_args__ = (
        Index('idx_sessions_user_id', 'user_id'),
        Index('idx_sessions_token', 'session_token'),
    )


# ============================================
# SUBSCRIPTION MODELS
# ============================================

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscription_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("sub_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=SubscriptionStatus.INACTIVE.value, nullable=False)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscription")
    
    __table_args__ = (
        Index('idx_subscriptions_user_id', 'user_id'),
        Index('idx_subscriptions_status', 'status'),
    )


# ============================================
# LLM PROVIDER MODELS
# ============================================

class LLMProviderConfig(Base):
    __tablename__ = "llm_provider_configs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("llm_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="llm_configs")
    
    __table_args__ = (
        Index('idx_llm_configs_user_provider', 'user_id', 'provider'),
        UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
    )


# ============================================
# EPIC MODELS
# ============================================

class Epic(Base):
    __tablename__ = "epics"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    epic_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("epic_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(50), default=EpicStage.PROBLEM_CAPTURE.value, nullable=False)
    
    # Pending proposal (JSON for flexibility)
    pending_proposal: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="epics")
    snapshot: Mapped[Optional["EpicSnapshot"]] = relationship(back_populates="epic", uselist=False, cascade="all, delete-orphan")
    transcript_events: Mapped[List["EpicTranscriptEvent"]] = relationship(back_populates="epic", cascade="all, delete-orphan")
    decisions: Mapped[List["EpicDecision"]] = relationship(back_populates="epic", cascade="all, delete-orphan")
    artifacts: Mapped[List["EpicArtifact"]] = relationship(back_populates="epic", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_epics_user_id', 'user_id'),
        Index('idx_epics_stage', 'current_stage'),
        # Stage can only be valid enum values
        CheckConstraint(
            "current_stage IN ('problem_capture', 'problem_confirmed', 'outcome_capture', 'outcome_confirmed', 'epic_drafted', 'epic_locked')",
            name='ck_valid_stage'
        ),
    )


class EpicSnapshot(Base):
    """Canonical snapshot of epic content - locked sections are immutable"""
    __tablename__ = "epic_snapshots"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    epic_id: Mapped[str] = mapped_column(String(50), ForeignKey("epics.epic_id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Problem (locked when problem_confirmed_at is set)
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    problem_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Outcome (locked when outcome_confirmed_at is set)
    desired_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Epic content (locked when epic_locked_at is set)
    epic_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    epic_locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    epic: Mapped["Epic"] = relationship(back_populates="snapshot")
    
    __table_args__ = (
        Index('idx_snapshots_epic_id', 'epic_id'),
    )


class EpicTranscriptEvent(Base):
    """Append-only conversation history - NO UPDATES, NO DELETES (except cascade)"""
    __tablename__ = "epic_transcript_events"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("evt_"))
    epic_id: Mapped[str] = mapped_column(String(50), ForeignKey("epics.epic_id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    epic: Mapped["Epic"] = relationship(back_populates="transcript_events")
    
    __table_args__ = (
        Index('idx_transcript_epic_created', 'epic_id', 'created_at'),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name='ck_valid_role'),
    )


class EpicDecision(Base):
    """Append-only decision log - NO UPDATES, NO DELETES (except cascade)"""
    __tablename__ = "epic_decisions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("dec_"))
    epic_id: Mapped[str] = mapped_column(String(50), ForeignKey("epics.epic_id", ondelete="CASCADE"), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'confirm_proposal', 'reject_proposal', 'stage_advance'
    from_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    to_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    proposal_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    content_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    epic: Mapped["Epic"] = relationship(back_populates="decisions")
    
    __table_args__ = (
        Index('idx_decisions_epic_created', 'epic_id', 'created_at'),
    )


class EpicArtifact(Base):
    """Features, User Stories, Bugs linked to an Epic"""
    __tablename__ = "epic_artifacts"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    artifact_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("art_"))
    epic_id: Mapped[str] = mapped_column(String(50), ForeignKey("epics.epic_id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    epic: Mapped["Epic"] = relationship(back_populates="artifacts")
    
    __table_args__ = (
        Index('idx_artifacts_epic_id', 'epic_id'),
    )


# ============================================
# PROMPT TEMPLATE
# ============================================

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("tmpl_"))
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    invariants: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    expected_outputs: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_prompts_stage_active', 'stage', 'is_active'),
    )


# ============================================
# PAYMENT
# ============================================

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("txn_"))
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(50), default=PaymentStatus.INITIATED.value, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payment_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_payments_session', 'session_id'),
    )



# ============================================
# PRODUCT DELIVERY CONTEXT
# ============================================

class ProductDeliveryContext(Base):
    """Per-user Product Delivery Context - automatically injected into all prompts"""
    __tablename__ = "product_delivery_contexts"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    context_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("ctx_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Required fields
    industry: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Comma-separated
    delivery_methodology: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # waterfall, agile, scrum, kanban, hybrid
    sprint_cycle_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Days
    sprint_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    num_developers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_qa: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivery_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # jira, azure_devops, none, other
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="delivery_context")
    
    __table_args__ = (
        Index('idx_delivery_context_user_id', 'user_id'),
    )
