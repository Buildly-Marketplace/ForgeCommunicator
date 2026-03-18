"""Add notify_all_messages to memberships

Revision ID: 017
Revises: 016
Create Date: 2026-02-25

Adds per-workspace opt-in for push notifications on all channel messages.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "017"
down_revision = "016_add_sync_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column already exists (safety for partial migrations or manual additions)
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('memberships')]
    
    if 'notify_all_messages' not in columns:
        op.add_column(
            "memberships",
            sa.Column(
                "notify_all_messages",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    op.drop_column("memberships", "notify_all_messages")
