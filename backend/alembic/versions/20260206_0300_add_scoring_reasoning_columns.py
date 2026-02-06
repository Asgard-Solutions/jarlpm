"""add_scoring_reasoning_columns

Revision ID: 16517632ed2b
Revises: e3f4g5h6i7j8
Create Date: 2026-02-06 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '16517632ed2b'
down_revision: Union[str, Sequence[str], None] = 'e3f4g5h6i7j8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reasoning columns to scoring-related tables."""
    # Add moscow_reasoning to epics
    op.add_column('epics', sa.Column('moscow_reasoning', sa.Text(), nullable=True))
    
    # Add reasoning columns to features
    op.add_column('features', sa.Column('moscow_reasoning', sa.Text(), nullable=True))
    op.add_column('features', sa.Column('rice_reasoning', sa.Text(), nullable=True))
    
    # Add rice_reasoning to user_stories
    op.add_column('user_stories', sa.Column('rice_reasoning', sa.Text(), nullable=True))
    
    # Add rice_reasoning to bugs
    op.add_column('bugs', sa.Column('rice_reasoning', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove reasoning columns from scoring-related tables."""
    op.drop_column('bugs', 'rice_reasoning')
    op.drop_column('user_stories', 'rice_reasoning')
    op.drop_column('features', 'rice_reasoning')
    op.drop_column('features', 'moscow_reasoning')
    op.drop_column('epics', 'moscow_reasoning')
