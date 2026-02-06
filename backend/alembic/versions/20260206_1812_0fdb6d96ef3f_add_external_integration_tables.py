"""add_external_integration_tables

Revision ID: 0fdb6d96ef3f
Revises: 18517632ed2d
Create Date: 2026-02-06 18:12:53.417188

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fdb6d96ef3f'
down_revision: Union[str, Sequence[str], None] = '18517632ed2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add external integration tables for Jira/Linear/Azure DevOps."""
    # Create external_integrations table
    op.create_table('external_integrations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('integration_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('external_account_id', sa.String(length=255), nullable=True),
        sa.Column('external_account_name', sa.String(length=255), nullable=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pat_encrypted', sa.Text(), nullable=True),
        sa.Column('org_url', sa.String(length=500), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('default_team_id', sa.String(length=255), nullable=True),
        sa.Column('default_team_name', sa.String(length=255), nullable=True),
        sa.Column('default_project_id', sa.String(length=255), nullable=True),
        sa.Column('default_project_name', sa.String(length=255), nullable=True),
        sa.Column('field_mappings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_id'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_user_provider_integration')
    )
    op.create_index('idx_ext_int_provider', 'external_integrations', ['provider'], unique=False)
    op.create_index('idx_ext_int_user_id', 'external_integrations', ['user_id'], unique=False)
    
    # Create external_push_mappings table
    op.create_table('external_push_mappings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('mapping_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('integration_id', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=50), nullable=False),
        sa.Column('external_type', sa.String(length=100), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('external_key', sa.String(length=100), nullable=True),
        sa.Column('external_url', sa.String(length=500), nullable=True),
        sa.Column('project_id', sa.String(length=255), nullable=True),
        sa.Column('team_id', sa.String(length=255), nullable=True),
        sa.Column('last_pushed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_push_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_id'], ['external_integrations.integration_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mapping_id'),
        sa.UniqueConstraint('user_id', 'provider', 'entity_type', 'entity_id', name='uq_user_provider_entity')
    )
    op.create_index('idx_push_map_entity', 'external_push_mappings', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_push_map_external', 'external_push_mappings', ['provider', 'external_id'], unique=False)
    op.create_index('idx_push_map_user_id', 'external_push_mappings', ['user_id'], unique=False)
    
    # Create external_push_runs table
    op.create_table('external_push_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('integration_id', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('epic_id', sa.String(length=50), nullable=True),
        sa.Column('push_scope', sa.String(length=50), nullable=True),
        sa.Column('include_bugs', sa.Boolean(), nullable=False),
        sa.Column('is_dry_run', sa.Boolean(), nullable=False),
        sa.Column('summary_json', sa.JSON(), nullable=True),
        sa.Column('error_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_id'], ['external_integrations.integration_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id')
    )
    op.create_index('idx_push_run_started', 'external_push_runs', ['started_at'], unique=False)
    op.create_index('idx_push_run_status', 'external_push_runs', ['status'], unique=False)
    op.create_index('idx_push_run_user_id', 'external_push_runs', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove external integration tables."""
    op.drop_index('idx_push_run_user_id', table_name='external_push_runs')
    op.drop_index('idx_push_run_status', table_name='external_push_runs')
    op.drop_index('idx_push_run_started', table_name='external_push_runs')
    op.drop_table('external_push_runs')
    
    op.drop_index('idx_push_map_user_id', table_name='external_push_mappings')
    op.drop_index('idx_push_map_external', table_name='external_push_mappings')
    op.drop_index('idx_push_map_entity', table_name='external_push_mappings')
    op.drop_table('external_push_mappings')
    
    op.drop_index('idx_ext_int_user_id', table_name='external_integrations')
    op.drop_index('idx_ext_int_provider', table_name='external_integrations')
    op.drop_table('external_integrations')
