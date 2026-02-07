"""Add edge_cases and notes_for_engineering to user_stories

Revision ID: 4ca08f133008
Revises: 0fdb6d96ef3f
Create Date: 2026-02-07 01:09:23.539292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4ca08f133008'
down_revision: Union[str, Sequence[str], None] = '0fdb6d96ef3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add edge_cases and notes_for_engineering columns to user_stories."""
    # Add edge_cases column (array of text)
    op.add_column('user_stories', sa.Column('edge_cases', postgresql.ARRAY(sa.Text()), nullable=True))
    
    # Add notes_for_engineering column (text)
    op.add_column('user_stories', sa.Column('notes_for_engineering', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove edge_cases and notes_for_engineering columns from user_stories."""
    op.drop_column('user_stories', 'notes_for_engineering')
    op.drop_column('user_stories', 'edge_cases')
