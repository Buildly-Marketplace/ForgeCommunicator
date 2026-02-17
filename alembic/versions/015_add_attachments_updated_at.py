"""Add updated_at column to attachments table

Revision ID: 015
Revises: 014
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '015'
down_revision: Union[str, None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add updated_at column if it doesn't exist
    if not column_exists('attachments', 'updated_at'):
        op.add_column('attachments', sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False
        ))


def downgrade() -> None:
    # Remove updated_at column if it exists
    if column_exists('attachments', 'updated_at'):
        op.drop_column('attachments', 'updated_at')
