"""add_sprint_fields_to_stories

Revision ID: 17517632ed2c
Revises: 16517632ed2b
Create Date: 2026-02-06 03:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '17517632ed2c'
down_revision: Union[str, Sequence[str], None] = '16517632ed2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sprint planning fields to user_stories."""
    op.add_column('user_stories', sa.Column('sprint_number', sa.Integer(), nullable=True))
    op.add_column('user_stories', sa.Column('status', sa.String(50), nullable=True))
    op.add_column('user_stories', sa.Column('blocked_reason', sa.Text(), nullable=True))
    
    # Create index for sprint queries
    op.create_index('idx_user_stories_sprint', 'user_stories', ['sprint_number'])
    op.create_index('idx_user_stories_status', 'user_stories', ['status'])


def downgrade() -> None:
    """Remove sprint planning fields from user_stories."""
    op.drop_index('idx_user_stories_status', table_name='user_stories')
    op.drop_index('idx_user_stories_sprint', table_name='user_stories')
    op.drop_column('user_stories', 'blocked_reason')
    op.drop_column('user_stories', 'status')
    op.drop_column('user_stories', 'sprint_number')
