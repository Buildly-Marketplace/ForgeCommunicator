"""Add bridged channels and external message fields

Revision ID: 011_add_bridged_channels
Revises: 010_add_external_integrations
Create Date: 2026-01-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_add_bridged_channels'
down_revision: Union[str, None] = '010_add_external_integrations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection for raw SQL (needed for IF NOT EXISTS checks)
    conn = op.get_bind()
    
    # Make user_id nullable for external messages (messages from Slack/Discord don't have a local user)
    # Check if already nullable first
    result = conn.execute(sa.text("""
        SELECT is_nullable FROM information_schema.columns 
        WHERE table_name = 'messages' AND column_name = 'user_id'
    """))
    row = result.fetchone()
    if row and row[0] == 'NO':
        op.alter_column('messages', 'user_id', existing_type=sa.Integer(), nullable=True)
    
    # Add external source fields to messages table (IF NOT EXISTS)
    existing_columns = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns WHERE table_name = 'messages'
    """))
    existing_cols = {row[0] for row in existing_columns}
    
    if 'external_source' not in existing_cols:
        op.add_column('messages', sa.Column('external_source', sa.String(20), nullable=True))
    if 'external_message_id' not in existing_cols:
        op.add_column('messages', sa.Column('external_message_id', sa.String(255), nullable=True))
    if 'external_channel_id' not in existing_cols:
        op.add_column('messages', sa.Column('external_channel_id', sa.String(255), nullable=True))
    if 'external_thread_ts' not in existing_cols:
        op.add_column('messages', sa.Column('external_thread_ts', sa.String(255), nullable=True))
    if 'external_author_name' not in existing_cols:
        op.add_column('messages', sa.Column('external_author_name', sa.String(255), nullable=True))
    if 'external_author_avatar' not in existing_cols:
        op.add_column('messages', sa.Column('external_author_avatar', sa.Text(), nullable=True))
    
    # Create index on external_source for filtering (IF NOT EXISTS)
    existing_indexes = conn.execute(sa.text("""
        SELECT indexname FROM pg_indexes WHERE tablename = 'messages'
    """))
    existing_idx = {row[0] for row in existing_indexes}
    
    if 'ix_messages_external_source' not in existing_idx:
        op.create_index('ix_messages_external_source', 'messages', ['external_source'], unique=False)
    
    # Create bridged_channels table (IF NOT EXISTS)
    existing_tables = conn.execute(sa.text("""
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    """))
    existing_tbl = {row[0] for row in existing_tables}
    
    if 'bridged_channels' not in existing_tbl:
        op.create_table(
            'bridged_channels',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('channel_id', sa.Integer(), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
            sa.Column('integration_id', sa.Integer(), sa.ForeignKey('external_integrations.id', ondelete='CASCADE'), nullable=False),
            
            # External channel info
            sa.Column('platform', sa.String(20), nullable=False),
            sa.Column('external_channel_id', sa.String(255), nullable=False),
            sa.Column('external_channel_name', sa.String(255), nullable=False),
            sa.Column('external_team_id', sa.String(255), nullable=True),
            sa.Column('external_guild_id', sa.String(255), nullable=True),
            
            # Sync settings
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('sync_incoming', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('sync_outgoing', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('import_history', sa.Boolean(), nullable=False, server_default='false'),
            
            # Tracking
            sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_message_id', sa.String(255), nullable=True),
            sa.Column('messages_imported', sa.Integer(), nullable=False, server_default='0'),
            
            # Reply prefix
            sa.Column('reply_prefix', sa.String(100), nullable=False, server_default='From Buildly Communicator'),
            
            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        
        # Create indexes
        op.create_index('ix_bridged_channels_channel_id', 'bridged_channels', ['channel_id'], unique=False)
        op.create_index('ix_bridged_channels_external_channel_id', 'bridged_channels', ['external_channel_id'], unique=False)
        
        # Create unique constraint
        op.create_unique_constraint(
            'uix_integration_external_channel', 
            'bridged_channels', 
            ['integration_id', 'external_channel_id']
        )


def downgrade() -> None:
    # Drop bridged_channels table
    op.drop_table('bridged_channels')
    
    # Remove external source fields from messages
    op.drop_index('ix_messages_external_source', table_name='messages')
    op.drop_column('messages', 'external_author_avatar')
    op.drop_column('messages', 'external_author_name')
    op.drop_column('messages', 'external_thread_ts')
    op.drop_column('messages', 'external_channel_id')
    op.drop_column('messages', 'external_message_id')
    op.drop_column('messages', 'external_source')
    
    # Revert user_id to NOT NULL (will fail if there are external messages - handle manually)
    op.alter_column('messages', 'user_id', existing_type=sa.Integer(), nullable=False)
