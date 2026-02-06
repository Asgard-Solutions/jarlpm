"""Add sprint_insights table for persisting AI-generated sprint insights

Revision ID: 18517632ed2d
Revises: 17517632ed2c
Create Date: 2026-02-06 05:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '18517632ed2d'
down_revision = '17517632ed2c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sprint_insights table
    op.create_table(
        'sprint_insights',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('insight_id', sa.String(50), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('sprint_number', sa.Integer(), nullable=False),
        sa.Column('insight_type', sa.String(50), nullable=False),
        sa.Column('content', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('insight_id')
    )
    
    # Create indexes
    op.create_index('idx_sprint_insight_user_sprint', 'sprint_insights', ['user_id', 'sprint_number'])
    op.create_index('idx_sprint_insight_type', 'sprint_insights', ['user_id', 'sprint_number', 'insight_type'])


def downgrade() -> None:
    op.drop_index('idx_sprint_insight_type', table_name='sprint_insights')
    op.drop_index('idx_sprint_insight_user_sprint', table_name='sprint_insights')
    op.drop_table('sprint_insights')
