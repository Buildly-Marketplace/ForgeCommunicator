"""Add title column to users table

Revision ID: 008_add_user_title
Revises: 007_add_user_bio
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '008_add_user_title'
down_revision: Union[str, None] = '007_add_user_bio'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('users', sa.Column('title', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'title')
