"""
External Integration Models for JarlPM
Supports Jira, Linear, and Azure DevOps integrations
"""
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum as PyEnum
import uuid

from sqlalchemy import (
    String, Text, Boolean, Integer, Float, DateTime, JSON,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def generate_uuid(prefix: str = "") -> str:
    """Generate a prefixed UUID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class IntegrationProvider(str, PyEnum):
    """Supported external integration providers"""
    JIRA = "jira"
    LINEAR = "linear"
    AZURE_DEVOPS = "azure_devops"


class IntegrationStatus(str, PyEnum):
    """Status of an external integration"""
    CONNECTED = "connected"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class PushStatus(str, PyEnum):
    """Status of a push run"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class EntityType(str, PyEnum):
    """Types of JarlPM entities that can be pushed"""
    EPIC = "epic"
    FEATURE = "feature"
    STORY = "story"
    BUG = "bug"


class ExternalIntegration(Base):
    """
    Stores user's external integration connections.
    One record per user per provider.
    """
    __tablename__ = "external_integrations"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    integration_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("int_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=IntegrationStatus.DISCONNECTED.value, nullable=False)
    
    # External account identification
    external_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # cloudId, workspaceId, orgId
    external_account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Workspace/org display name
    
    # OAuth tokens (encrypted)
    access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # PAT for Azure DevOps (encrypted)
    pat_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    org_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # For Azure DevOps
    
    # Scopes granted
    scopes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Default target configuration
    default_team_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_team_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_project_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Field mappings (provider-specific configuration)
    field_mappings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Mapped["User"] = relationship(backref="external_integrations")
    push_mappings: Mapped[List["ExternalPushMapping"]] = relationship(back_populates="integration", cascade="all, delete-orphan")
    push_runs: Mapped[List["ExternalPushRun"]] = relationship(back_populates="integration", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_ext_int_user_id', 'user_id'),
        Index('idx_ext_int_provider', 'provider'),
        UniqueConstraint('user_id', 'provider', name='uq_user_provider_integration'),
    )


class ExternalPushMapping(Base):
    """
    Maps JarlPM entities to provider entities.
    Ensures idempotent pushes (no duplicates).
    """
    __tablename__ = "external_push_mappings"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mapping_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("map_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    integration_id: Mapped[str] = mapped_column(String(50), ForeignKey("external_integrations.integration_id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # JarlPM entity
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # epic, feature, story, bug
    entity_id: Mapped[str] = mapped_column(String(50), nullable=False)   # JarlPM ID (epic_id, feature_id, etc.)
    
    # External provider entity
    external_type: Mapped[str] = mapped_column(String(100), nullable=False)  # Jira Issue, Linear Issue, ADO WorkItem
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)    # Provider's internal ID
    external_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Jira: PROJ-123, Linear: ENG-42
    external_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Direct link to the issue
    
    # Target project/team info
    project_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    team_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Sync metadata
    last_pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_push_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA256 hash of payload for idempotency
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    integration: Mapped["ExternalIntegration"] = relationship(back_populates="push_mappings")
    
    __table_args__ = (
        Index('idx_push_map_user_id', 'user_id'),
        Index('idx_push_map_entity', 'entity_type', 'entity_id'),
        Index('idx_push_map_external', 'provider', 'external_id'),
        UniqueConstraint('user_id', 'provider', 'entity_type', 'entity_id', name='uq_user_provider_entity'),
    )


class ExternalPushRun(Base):
    """
    Audit trail of push operations.
    One record per push attempt (batch or single).
    """
    __tablename__ = "external_push_runs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, default=lambda: generate_uuid("run_"))
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    integration_id: Mapped[str] = mapped_column(String(50), ForeignKey("external_integrations.integration_id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default=PushStatus.SUCCESS.value, nullable=False)
    
    # Scope of this push
    epic_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    push_scope: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # epic_only, epic_features, epic_features_stories
    include_bugs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Summary (counts and links)
    summary_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"created": 5, "updated": 2, "skipped": 1, "links": ["url1", "url2"]}
    
    # Errors (provider error bodies)
    error_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    integration: Mapped["ExternalIntegration"] = relationship(back_populates="push_runs")
    
    __table_args__ = (
        Index('idx_push_run_user_id', 'user_id'),
        Index('idx_push_run_status', 'status'),
        Index('idx_push_run_started', 'started_at'),
    )
