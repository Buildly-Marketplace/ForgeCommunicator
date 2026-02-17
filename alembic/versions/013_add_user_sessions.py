"""Add user_sessions table for multi-device support

Revision ID: 013_add_user_sessions
Revises: 012_add_collabhub_integration
Create Date: 2026-02-17

This migration adds the user_sessions table to support multiple concurrent sessions
per user. Previously, each user had only one session_token on the users table,
so logging in on a new device would invalidate the previous session.

With this change:
- Each login creates a new UserSession record
- Users can be logged in on multiple devices simultaneously
- Sessions include device info for the session management UI
- Old session columns on users table are deprecated but kept for migration safety
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# Revision identifiers, used by Alembic.
revision: str = '013_add_user_sessions'
down_revision: Union[str, None] = '012_add_collabhub_integration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(index_name: str, table_name: str) -> bool:
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)


def upgrade() -> None:
    # Create user_sessions table
    if not table_exists('user_sessions'):
        op.create_table(
            'user_sessions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('session_token', sa.String(64), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('device_name', sa.String(100), nullable=True),
            sa.Column('device_type', sa.String(20), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_pwa', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Create indexes for session lookup
    if not index_exists('ix_user_sessions_session_token', 'user_sessions'):
        op.create_index('ix_user_sessions_session_token', 'user_sessions', ['session_token'], unique=True)
    
    if not index_exists('ix_user_sessions_user_id', 'user_sessions'):
        op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
    
    # Note: We keep the old session_token and session_expires_at columns on users table
    # for backwards compatibility during rollout. They can be removed in a future migration
    # after the new session system is stable.


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_user_sessions_user_id', table_name='user_sessions')
    op.drop_index('ix_user_sessions_session_token', table_name='user_sessions')
    
    # Drop the table
    op.drop_table('user_sessions')
