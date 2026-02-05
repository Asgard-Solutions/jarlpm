"""add_delivery_velocity_and_scope_plans

Revision ID: a1b2c3d4e5f6
Revises: b2c3d4e5f6g7
Create Date: 2026-02-05

Adds:
1. points_per_dev_per_sprint column to product_delivery_contexts
2. scope_plans table for reversible deferral planning
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add points_per_dev_per_sprint to product_delivery_contexts
    op.add_column(
        'product_delivery_contexts',
        sa.Column('points_per_dev_per_sprint', sa.Integer(), nullable=True, server_default='8')
    )
    
    # 2. Create scope_plans table
    op.create_table(
        'scope_plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.String(50), nullable=False),
        sa.Column('epic_id', sa.String(50), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False, server_default='Default Plan'),
        sa.Column('deferred_story_ids', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('total_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('deferred_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('remaining_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id'),
        sa.ForeignKeyConstraint(['epic_id'], ['epics.epic_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    )
    
    # 3. Create indexes for scope_plans
    op.create_index('idx_scope_plans_epic_id', 'scope_plans', ['epic_id'])
    op.create_index('idx_scope_plans_user_id', 'scope_plans', ['user_id'])
    op.create_index('idx_scope_plans_active', 'scope_plans', ['epic_id', 'is_active'])


def downgrade() -> None:
    # Drop scope_plans indexes
    op.drop_index('idx_scope_plans_active', 'scope_plans')
    op.drop_index('idx_scope_plans_user_id', 'scope_plans')
    op.drop_index('idx_scope_plans_epic_id', 'scope_plans')
    
    # Drop scope_plans table
    op.drop_table('scope_plans')
    
    # Remove points_per_dev_per_sprint column
    op.drop_column('product_delivery_contexts', 'points_per_dev_per_sprint')
