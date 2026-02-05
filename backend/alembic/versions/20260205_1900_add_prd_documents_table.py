"""add prd documents table

Revision ID: e3f4g5h6i7j8
Revises: d2e3f4g5h6i7
Create Date: 2026-02-05 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f4g5h6i7j8'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4g5h6i7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create prd_documents table."""
    op.create_table('prd_documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('prd_id', sa.String(length=50), nullable=False),
        sa.Column('epic_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['epic_id'], ['epics.epic_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prd_id'),
        sa.UniqueConstraint('epic_id', name='uq_prd_epic')
    )
    op.create_index('idx_prd_epic_id', 'prd_documents', ['epic_id'], unique=False)
    op.create_index('idx_prd_user_id', 'prd_documents', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop prd_documents table."""
    op.drop_index('idx_prd_user_id', table_name='prd_documents')
    op.drop_index('idx_prd_epic_id', table_name='prd_documents')
    op.drop_table('prd_documents')
