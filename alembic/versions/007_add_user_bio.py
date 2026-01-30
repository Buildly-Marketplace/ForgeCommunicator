"""Add bio column to users table

Revision ID: 007_add_user_bio
Revises: 006_add_push_subscriptions
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007_add_user_bio'
down_revision: Union[str, None] = '006_add_push_subscriptions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'bio')
