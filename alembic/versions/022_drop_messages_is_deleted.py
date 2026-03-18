"""Drop legacy is_deleted column from messages

Revision ID: 022_drop_messages_is_deleted
Revises: 021_drop_channels_display_name
Create Date: 2026-03-18

The messages model uses is_deleted as a computed @property (based on deleted_at),
but the database has it as a NOT NULL column, causing insert errors.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '022_drop_messages_is_deleted'
down_revision: Union[str, None] = '021_drop_channels_display_name'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Drop is_deleted column if it exists
    if column_exists('messages', 'is_deleted'):
        op.drop_column('messages', 'is_deleted')


def downgrade() -> None:
    # Re-add column if needed (shouldn't be necessary)
    if not column_exists('messages', 'is_deleted'):
        op.add_column('messages', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
