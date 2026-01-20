"""Add Google Workspace integration columns

Revision ID: 004_google_calendar
Revises: 003_add_team_invites
Create Date: 2026-01-21 10:00:00.000000

Adds columns for Google Workspace OAuth and Calendar integration:
- google_sub: Google subject ID for identity linking
- google_access_token: OAuth access token for API calls
- google_refresh_token: OAuth refresh token for token renewal
- google_token_expires_at: Token expiration timestamp
- google_calendar_status: Calendar-derived status (active/away/dnd)
- google_calendar_message: Calendar status message (e.g., "In a meeting")
- google_calendar_synced_at: Last calendar sync timestamp
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_google_calendar'
down_revision: Union[str, None] = '003_add_team_invites'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Google OAuth columns
    op.add_column(
        'users',
        sa.Column('google_sub', sa.String(255), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('google_access_token', sa.Text(), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('google_refresh_token', sa.Text(), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('google_token_expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Add Calendar status columns
    op.add_column(
        'users',
        sa.Column('google_calendar_status', sa.String(20), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('google_calendar_message', sa.String(100), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('google_calendar_synced_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Create index on google_sub for identity lookups
    op.create_index('ix_users_google_sub', 'users', ['google_sub'])


def downgrade() -> None:
    # Remove index
    op.drop_index('ix_users_google_sub', table_name='users')
    
    # Remove columns
    op.drop_column('users', 'google_calendar_synced_at')
    op.drop_column('users', 'google_calendar_message')
    op.drop_column('users', 'google_calendar_status')
    op.drop_column('users', 'google_token_expires_at')
    op.drop_column('users', 'google_refresh_token')
    op.drop_column('users', 'google_access_token')
    op.drop_column('users', 'google_sub')
