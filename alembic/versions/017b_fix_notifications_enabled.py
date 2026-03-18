"""Fix missing notifications_enabled column

Revision ID: 017b
Revises: 017
Create Date: 2026-03-18

Adds the missing notifications_enabled column to memberships table.
This column was defined in the model but never had a migration.

Safe for all deployment scenarios:
- New deployments: Column won't exist, will be added
- Existing deployments missing column: Will be added
- Deployments that somehow have the column: Safely skipped
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "017b_fix_notifications_enabled"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column already exists - handles all edge cases safely
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('memberships')]
    
    if 'notifications_enabled' not in columns:
        op.add_column(
            "memberships",
            sa.Column(
                "notifications_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    # Only drop if it exists
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('memberships')]
    
    if 'notifications_enabled' in columns:
        op.drop_column("memberships", "notifications_enabled")
