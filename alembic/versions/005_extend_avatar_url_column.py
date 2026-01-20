"""Extend avatar_url column to TEXT for long Google URLs

Revision ID: 005_extend_avatar_url
Revises: 004_google_calendar
Create Date: 2026-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_extend_avatar_url'
down_revision: Union[str, None] = '004_google_calendar'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Google avatar URLs can be very long (1000+ characters)
    # Change from VARCHAR(500) to TEXT
    op.alter_column(
        'users',
        'avatar_url',
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=True
    )


def downgrade() -> None:
    # Revert to VARCHAR(500) - may truncate long URLs
    op.alter_column(
        'users',
        'avatar_url',
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True
    )
