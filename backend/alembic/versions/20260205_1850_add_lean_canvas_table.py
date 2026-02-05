"""add lean canvas table

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4g5h6
Create Date: 2026-02-05 18:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4g5h6i7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4g5h6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create lean_canvases table."""
    op.create_table('lean_canvases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('canvas_id', sa.String(length=50), nullable=False),
        sa.Column('epic_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('problem', sa.Text(), nullable=True),
        sa.Column('solution', sa.Text(), nullable=True),
        sa.Column('unique_value', sa.Text(), nullable=True),
        sa.Column('unfair_advantage', sa.Text(), nullable=True),
        sa.Column('customer_segments', sa.Text(), nullable=True),
        sa.Column('key_metrics', sa.Text(), nullable=True),
        sa.Column('channels', sa.Text(), nullable=True),
        sa.Column('cost_structure', sa.Text(), nullable=True),
        sa.Column('revenue_streams', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='manual'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['epic_id'], ['epics.epic_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('canvas_id'),
        sa.UniqueConstraint('epic_id', name='uq_lean_canvas_epic')
    )
    op.create_index('idx_lean_canvas_epic_id', 'lean_canvases', ['epic_id'], unique=False)
    op.create_index('idx_lean_canvas_user_id', 'lean_canvases', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop lean_canvases table."""
    op.drop_index('idx_lean_canvas_user_id', table_name='lean_canvases')
    op.drop_index('idx_lean_canvas_epic_id', table_name='lean_canvases')
    op.drop_table('lean_canvases')
