"""add poker session tables

Revision ID: c1d2e3f4g5h6
Revises: a1b2c3d4e5f6
Create Date: 2026-02-05 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4g5h6'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create poker_estimate_sessions and poker_persona_estimates tables."""
    # Create poker_estimate_sessions table
    op.create_table('poker_estimate_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=50), nullable=False),
        sa.Column('story_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('min_estimate', sa.Integer(), nullable=True),
        sa.Column('max_estimate', sa.Integer(), nullable=True),
        sa.Column('average_estimate', sa.Float(), nullable=True),
        sa.Column('suggested_estimate', sa.Integer(), nullable=True),
        sa.Column('accepted_estimate', sa.Integer(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['story_id'], ['user_stories.story_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )
    op.create_index('idx_poker_sessions_story_id', 'poker_estimate_sessions', ['story_id'], unique=False)
    op.create_index('idx_poker_sessions_user_id', 'poker_estimate_sessions', ['user_id'], unique=False)
    
    # Create poker_persona_estimates table
    op.create_table('poker_persona_estimates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('estimate_id', sa.String(length=50), nullable=False),
        sa.Column('session_id', sa.String(length=50), nullable=False),
        sa.Column('persona_name', sa.String(length=100), nullable=False),
        sa.Column('persona_role', sa.String(length=100), nullable=False),
        sa.Column('estimate_points', sa.Integer(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=False),
        sa.Column('confidence', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['poker_estimate_sessions.session_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('estimate_id')
    )
    op.create_index('idx_poker_estimates_session_id', 'poker_persona_estimates', ['session_id'], unique=False)


def downgrade() -> None:
    """Drop poker_persona_estimates and poker_estimate_sessions tables."""
    op.drop_index('idx_poker_estimates_session_id', table_name='poker_persona_estimates')
    op.drop_table('poker_persona_estimates')
    op.drop_index('idx_poker_sessions_user_id', table_name='poker_estimate_sessions')
    op.drop_index('idx_poker_sessions_story_id', table_name='poker_estimate_sessions')
    op.drop_table('poker_estimate_sessions')
