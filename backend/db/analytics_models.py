"""
Analytics Models for JarlPM
Private observability for AI generation quality tracking

Tracks:
- Prompt versions and effectiveness
- Model/provider usage and costs
- Parse/validation success rates
- User edit patterns after generation
"""
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from sqlalchemy import (
    String, Text, Boolean, Integer, Float, DateTime, JSON,
    ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY

from .database import Base


def generate_uuid(prefix: str = "") -> str:
    """Generate a prefixed UUID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class InitiativeGenerationLog(Base):
    """
    Logs each initiative generation attempt for quality analysis.
    This is append-only analytics data - never update, only insert.
    """
    __tablename__ = "initiative_generation_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    log_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("ilog_"))
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Input context
    idea_length: Mapped[int] = mapped_column(Integer, nullable=False)  # Character count of input
    idea_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 for dedup analysis
    product_name_provided: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Delivery context used
    has_delivery_context: Mapped[bool] = mapped_column(Boolean, default=False)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    methodology: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    team_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Model/Provider info
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai, anthropic, local
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Prompt versioning
    prompt_version: Mapped[str] = mapped_column(String(20), default="v1.0", nullable=False)
    
    # Token usage and cost (per pass)
    pass_1_tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_1_tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_2_tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_2_tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_3_tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_3_tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_4_tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_4_tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Parse/validation metrics
    pass_1_retries: Mapped[int] = mapped_column(Integer, default=0)
    pass_2_retries: Mapped[int] = mapped_column(Integer, default=0)
    pass_3_retries: Mapped[int] = mapped_column(Integer, default=0)
    pass_4_retries: Mapped[int] = mapped_column(Integer, default=0)
    total_retries: Mapped[int] = mapped_column(Integer, default=0)
    validation_errors: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    
    # Output metrics
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    features_generated: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stories_generated: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Quality check results
    critic_issues_found: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    critic_auto_fixed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scope_assessment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # on_track, at_risk, overloaded
    
    # Timing
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_1_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_2_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_3_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_4_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_gen_logs_user_id', 'user_id'),
        Index('idx_gen_logs_created', 'created_at'),
        Index('idx_gen_logs_provider', 'llm_provider'),
        Index('idx_gen_logs_success', 'success'),
        Index('idx_gen_logs_prompt_version', 'prompt_version'),
    )


class InitiativeEditLog(Base):
    """
    Tracks what users edit after AI generation.
    Helps identify which parts of generation need improvement.
    """
    __tablename__ = "initiative_edit_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    edit_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("iedit_"))
    generation_log_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Links to generation
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    epic_id: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # What was edited
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # prd, epic, feature, story
    entity_id: Mapped[str] = mapped_column(String(50), nullable=False)
    field_edited: Mapped[str] = mapped_column(String(100), nullable=False)  # title, description, acceptance_criteria, etc.
    
    # Edit metrics
    original_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    edited_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    change_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # edited_length / original_length
    
    # Edit type classification
    edit_type: Mapped[str] = mapped_column(String(50), nullable=False)  # add, remove, modify, rewrite
    
    # Timing (how long after generation)
    time_to_edit_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_edit_logs_user_id', 'user_id'),
        Index('idx_edit_logs_epic_id', 'epic_id'),
        Index('idx_edit_logs_entity_type', 'entity_type'),
        Index('idx_edit_logs_field', 'field_edited'),
        Index('idx_edit_logs_created', 'created_at'),
    )


class PromptVersionRegistry(Base):
    """
    Tracks prompt versions and their performance over time.
    Enables A/B testing of prompts.
    """
    __tablename__ = "prompt_version_registry"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("pver_"))
    
    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # v1.0, v1.1, v2.0
    pass_name: Mapped[str] = mapped_column(String(50), nullable=False)  # prd, decomp, planning, critic
    
    # Prompt content (for audit)
    system_prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Aggregated metrics (updated periodically)
    total_uses: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_retries: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_edit_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # How much users edit
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_prompt_registry_version', 'version'),
        Index('idx_prompt_registry_active', 'is_active'),
    )


class ModelHealthMetrics(Base):
    """
    Persisted model health metrics per user+provider+model.
    Tracks validation success/failure rates for weak model detection.
    """
    __tablename__ = "model_health_metrics"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai, anthropic, local
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Counters (updated atomically)
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    validation_failures: Mapped[int] = mapped_column(Integer, default=0)
    repair_successes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Derived metrics (computed on read)
    # failure_rate = validation_failures / total_calls
    
    # Warning state
    warning_shown: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_model_health_user_provider_model', 'user_id', 'provider', 'model_name'),
        Index('idx_model_health_user', 'user_id'),
    )
