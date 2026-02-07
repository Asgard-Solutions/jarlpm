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
    GOOGLE = "google"
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


class BugStatus(str, PyEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class BugSeverity(str, PyEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugPriority(str, PyEnum):
    P0 = "p0"  # Urgent
    P1 = "p1"  # High
    P2 = "p2"  # Medium
    P3 = "p3"  # Low


class BugLinkEntityType(str, PyEnum):
    EPIC = "epic"
    FEATURE = "feature"
    STORY = "story"


# Bug status ordering for validation
BUG_STATUS_ORDER = {
    BugStatus.DRAFT: 0,
    BugStatus.CONFIRMED: 1,
    BugStatus.IN_PROGRESS: 2,
    BugStatus.RESOLVED: 3,
    BugStatus.CLOSED: 4,
}

# Valid status transitions
BUG_STATUS_TRANSITIONS = {
    BugStatus.DRAFT: [BugStatus.CONFIRMED],
    BugStatus.CONFIRMED: [BugStatus.IN_PROGRESS],
    BugStatus.IN_PROGRESS: [BugStatus.RESOLVED],
    BugStatus.RESOLVED: [BugStatus.CLOSED],
    BugStatus.CLOSED: [],  # Terminal state
}


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
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Email/password auth
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Email verification status
    picture: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    sessions: Mapped[List["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscription: Mapped[Optional["Subscription"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    llm_configs: Mapped[List["LLMProviderConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    epics: Mapped[List["Epic"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    delivery_context: Mapped[Optional["ProductDeliveryContext"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    bugs: Mapped[List["Bug"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
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


class VerificationToken(Base):
    """Token for email verification and password reset"""
    __tablename__ = "verification_tokens"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, default=lambda: generate_uuid("vtoken_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    token_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'email_verification' or 'password_reset'
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(backref="verification_tokens")
    
    __table_args__ = (
        Index('idx_verification_tokens_user_id', 'user_id'),
        Index('idx_verification_tokens_token', 'token'),
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
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscription")
    
    __table_args__ = (
        Index('idx_subscriptions_user_id', 'user_id'),
        Index('idx_subscriptions_status', 'status'),
    )


class PaymentTransaction(Base):
    """Track all payment transactions through Stripe"""
    __tablename__ = "payment_transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("txn_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    stripe_session_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    stripe_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, paid, failed, expired
    transaction_type: Mapped[str] = mapped_column(String(50), default="subscription", nullable=False)  # subscription, one_time
    payment_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(backref="payment_transactions")
    
    __table_args__ = (
        Index('idx_payment_transactions_user_id', 'user_id'),
        Index('idx_payment_transactions_session_id', 'stripe_session_id'),
        Index('idx_payment_transactions_status', 'payment_status'),
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
    
    # Initiative Library: Archive status (reversible soft-delete)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Pending proposal (JSON for flexibility)
    pending_proposal: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Lock confirmation metadata (required before locking)
    lock_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_confirmed_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lock_confirmation_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Hash of anchors at confirmation
    
    # Lock metadata (set when epic_locked)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # MoSCoW Scoring (must_have, should_have, could_have, wont_have)
    moscow_score: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    moscow_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="epics")
    snapshot: Mapped[Optional["EpicSnapshot"]] = relationship(back_populates="epic", uselist=False, cascade="all, delete-orphan")
    transcript_events: Mapped[List["EpicTranscriptEvent"]] = relationship(back_populates="epic", cascade="all, delete-orphan")
    decisions: Mapped[List["EpicDecision"]] = relationship(back_populates="epic", cascade="all, delete-orphan")
    artifacts: Mapped[List["EpicArtifact"]] = relationship(back_populates="epic", cascade="all, delete-orphan")
    features: Mapped[List["Feature"]] = relationship(back_populates="epic", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_epics_user_id', 'user_id'),
        Index('idx_epics_stage', 'current_stage'),
        Index('idx_epics_archived', 'is_archived'),
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
    
    # Velocity - story points per developer per sprint (default 8)
    points_per_dev_per_sprint: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=8)
    
    # Quality mode: standard (1-pass) or quality (2-pass with critique)
    quality_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="standard")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="delivery_context")
    
    __table_args__ = (
        Index('idx_delivery_context_user_id', 'user_id'),
    )


# ============================================
# SCOPE PLAN (Delivery Reality)
# ============================================

class ScopePlan(Base):
    """
    Saved scope plan for an initiative - reversible planning.
    Stores deferred story IDs without mutating the stories themselves.
    """
    __tablename__ = "scope_plans"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("splan_"))
    epic_id: Mapped[str] = mapped_column(String(50), ForeignKey("epics.epic_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    # Plan name (optional, allows multiple plans per epic)
    name: Mapped[str] = mapped_column(String(200), default="Default Plan", nullable=False)
    
    # Deferred story IDs (JSON array)
    deferred_story_ids: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    
    # Points summary at time of saving (for historical reference)
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deferred_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remaining_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Notes from PM
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Active flag (only one active plan per epic)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_scope_plans_epic_id', 'epic_id'),
        Index('idx_scope_plans_user_id', 'user_id'),
        Index('idx_scope_plans_active', 'epic_id', 'is_active'),
    )


# ============================================
# BUG TRACKING
# ============================================

class Bug(Base):
    """Bug entity - standalone or linked to Epics/Features/Stories"""
    __tablename__ = "bugs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bug_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("bug_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    # Required fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default=BugSeverity.MEDIUM.value, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=BugStatus.DRAFT.value, nullable=False)
    
    # Optional structured fields
    steps_to_reproduce: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_behavior: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_behavior: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    environment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    assignee_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # RICE Scoring (Reach * Impact * Confidence / Effort)
    rice_reach: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-10 scale
    rice_impact: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.25, 0.5, 1, 2, 3
    rice_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.5, 0.8, 1.0
    rice_effort: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.5-10 person-months
    rice_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Calculated score
    rice_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="bugs")
    links: Mapped[List["BugLink"]] = relationship(back_populates="bug", cascade="all, delete-orphan")
    status_history: Mapped[List["BugStatusHistory"]] = relationship(back_populates="bug", cascade="all, delete-orphan")
    conversation_events: Mapped[List["BugConversationEvent"]] = relationship(back_populates="bug", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_bugs_user_id', 'user_id'),
        Index('idx_bugs_status', 'status'),
        Index('idx_bugs_severity', 'severity'),
        Index('idx_bugs_not_deleted', 'is_deleted'),
    )


class BugLink(Base):
    """Polymorphic join table for linking bugs to Epics/Features/Stories"""
    __tablename__ = "bug_links"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    link_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("link_"))
    bug_id: Mapped[str] = mapped_column(String(50), ForeignKey("bugs.bug_id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # epic, feature, story
    entity_id: Mapped[str] = mapped_column(String(50), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    bug: Mapped["Bug"] = relationship(back_populates="links")
    
    __table_args__ = (
        Index('idx_bug_links_bug_id', 'bug_id'),
        Index('idx_bug_links_entity', 'entity_type', 'entity_id'),
        UniqueConstraint('bug_id', 'entity_type', 'entity_id', name='uq_bug_entity_link'),
    )


class BugStatusHistory(Base):
    """Status transition history for bugs"""
    __tablename__ = "bug_status_history"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    history_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("hist_"))
    bug_id: Mapped[str] = mapped_column(String(50), ForeignKey("bugs.bug_id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # null for initial creation
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(50), nullable=False)  # user_id
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    bug: Mapped["Bug"] = relationship(back_populates="status_history")
    
    __table_args__ = (
        Index('idx_bug_status_history_bug_id', 'bug_id'),
    )


class BugConversationEvent(Base):
    """AI conversation events for bug refinement"""
    __tablename__ = "bug_conversation_events"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("evt_"))
    bug_id: Mapped[str] = mapped_column(String(50), ForeignKey("bugs.bug_id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    bug: Mapped["Bug"] = relationship(back_populates="conversation_events")
    
    __table_args__ = (
        Index('idx_bug_conversation_bug_id', 'bug_id'),
    )



class LeanCanvas(Base):
    """Lean Canvas business model tied to an Epic"""
    __tablename__ = "lean_canvases"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canvas_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("canvas_"))
    epic_id: Mapped[str] = mapped_column(String(50), ForeignKey("epics.epic_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    # Lean Canvas 9 sections
    problem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    solution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unique_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unfair_advantage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_segments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_metrics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channels: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_structure: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revenue_streams: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)  # manual | ai_generated
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_lean_canvas_epic_id', 'epic_id'),
        Index('idx_lean_canvas_user_id', 'user_id'),
        UniqueConstraint('epic_id', name='uq_lean_canvas_epic'),  # One canvas per epic
    )



class PRDDocument(Base):
    """Product Requirements Document tied to an Epic"""
    __tablename__ = "prd_documents"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prd_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("prd_"))
    epic_id: Mapped[str] = mapped_column(String(50), ForeignKey("epics.epic_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    # PRD content - using JSON to match existing schema
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sections: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Stores PRD sections as JSON
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    generation_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Metadata
    version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)  # draft | review | approved
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_prd_epic_id', 'epic_id'),
        Index('idx_prd_user_id', 'user_id'),
        UniqueConstraint('epic_id', name='uq_prd_epic'),  # One PRD per epic
    )


class SprintInsightType(str, PyEnum):
    """Types of AI-generated sprint insights"""
    KICKOFF_PLAN = "kickoff_plan"
    STANDUP_SUMMARY = "standup_summary"
    WIP_SUGGESTIONS = "wip_suggestions"


class SprintInsight(Base):
    """
    Persisted AI-generated sprint insights.
    Stores kickoff plans, standup summaries, and WIP suggestions
    so users can view them later without regenerating.
    """
    __tablename__ = "sprint_insights"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    insight_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("si_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    # Sprint identification
    sprint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)  # kickoff_plan, standup_summary, wip_suggestions
    
    # Content - stores the full AI response as JSON
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_sprint_insight_user_sprint', 'user_id', 'sprint_number'),
        Index('idx_sprint_insight_type', 'user_id', 'sprint_number', 'insight_type'),
        # Allow multiple insights of same type per sprint (history)
    )
