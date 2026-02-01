"""Add external integrations tables

Revision ID: 010_add_external_integrations
Revises: 009_add_notes
Create Date: 2026-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_add_external_integrations'
down_revision: Union[str, None] = '009_add_notes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create external_integrations table (using String instead of Enum for simplicity)
    op.create_table(
        'external_integrations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('integration_type', sa.String(20), nullable=False),  # 'slack' or 'discord'
        
        # OAuth tokens
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        
        # External platform info
        sa.Column('external_user_id', sa.String(255), nullable=True),
        sa.Column('external_team_id', sa.String(255), nullable=True),
        sa.Column('external_username', sa.String(255), nullable=True),
        sa.Column('external_team_name', sa.String(255), nullable=True),
        
        # Webhook/bot config
        sa.Column('webhook_url', sa.Text(), nullable=True),
        sa.Column('bot_token', sa.Text(), nullable=True),
        
        # Notification preferences (JSON)
        sa.Column('notification_preferences', sa.JSON(), nullable=False, server_default='{}'),
        
        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Create unique index for user_id + integration_type
    op.create_index(
        'ix_external_integrations_user_type',
        'external_integrations',
        ['user_id', 'integration_type'],
        unique=True,
    )
    
    # Create notification_logs table
    op.create_table(
        'notification_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('integration_id', sa.Integer(), sa.ForeignKey('external_integrations.id', ondelete='CASCADE'), nullable=False),
        
        # Notification details
        sa.Column('source', sa.String(30), nullable=False),  # slack_dm, slack_mention, etc.
        
        # Sender info
        sa.Column('sender_name', sa.String(255), nullable=False),
        sa.Column('sender_avatar_url', sa.Text(), nullable=True),
        sa.Column('sender_external_id', sa.String(255), nullable=True),
        
        # Channel/conversation info
        sa.Column('channel_name', sa.String(255), nullable=True),
        sa.Column('channel_external_id', sa.String(255), nullable=True),
        
        # Message content
        sa.Column('message_body', sa.Text(), nullable=False),
        sa.Column('message_preview', sa.String(500), nullable=False),
        
        # External references
        sa.Column('external_url', sa.Text(), nullable=True),
        sa.Column('external_message_id', sa.String(255), nullable=True),
        sa.Column('external_timestamp', sa.DateTime(timezone=True), nullable=True),
        
        # Status
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Create indexes for notification_logs
    op.create_index('ix_notification_logs_user_id', 'notification_logs', ['user_id'])
    op.create_index('ix_notification_logs_created_at', 'notification_logs', ['created_at'])
    op.create_index('ix_notification_logs_is_read', 'notification_logs', ['user_id', 'is_read'])


def downgrade() -> None:
    # Drop notification_logs table and indexes
    op.drop_index('ix_notification_logs_is_read')
    op.drop_index('ix_notification_logs_created_at')
    op.drop_index('ix_notification_logs_user_id')
    op.drop_table('notification_logs')
    
    # Drop external_integrations table and indexes
    op.drop_index('ix_external_integrations_user_type')
    op.drop_table('external_integrations')
