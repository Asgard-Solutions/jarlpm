"""add_epic_archived_fields

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-05

Adds:
1. is_archived boolean column to epics (default false)
2. archived_at timestamp column to epics
3. Index for archive filtering
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_archived column with default false
    op.add_column(
        'epics',
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Add archived_at timestamp column
    op.add_column(
        'epics',
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Create index for archive filtering
    op.create_index('idx_epics_archived', 'epics', ['is_archived'])


def downgrade() -> None:
    # Drop index
    op.drop_index('idx_epics_archived', 'epics')
    
    # Drop columns
    op.drop_column('epics', 'archived_at')
    op.drop_column('epics', 'is_archived')
