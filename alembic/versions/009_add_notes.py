"""Add notes and note_shares tables

Revision ID: 009_add_notes
Revises: 008_add_user_title
Create Date: 2026-01-30

Adds notes table for user personal notebooks and note_shares
table for sharing notes with users or channels.
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '009_add_notes'
down_revision = '008_add_user_title'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notes table
    op.create_table(
        'notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('channel_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(255), nullable=False, server_default='Untitled Note'),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('visibility', sa.String(20), nullable=False, server_default='private'),
        sa.Column('source_type', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('source_message_id', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for notes
    op.create_index('ix_notes_owner_id', 'notes', ['owner_id'], unique=False)
    op.create_index('ix_notes_workspace_id', 'notes', ['workspace_id'], unique=False)
    op.create_index('ix_notes_channel_id', 'notes', ['channel_id'], unique=False)
    
    # Create note_shares table
    op.create_table(
        'note_shares',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('note_id', sa.Integer(), nullable=False),
        sa.Column('shared_with_user_id', sa.Integer(), nullable=True),
        sa.Column('shared_with_channel_id', sa.Integer(), nullable=True),
        sa.Column('shared_by_id', sa.Integer(), nullable=False),
        sa.Column('message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_with_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_with_channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('note_id', 'shared_with_user_id', name='uq_note_share_user'),
        sa.UniqueConstraint('note_id', 'shared_with_channel_id', name='uq_note_share_channel'),
    )
    
    # Create indexes for note_shares
    op.create_index('ix_note_shares_note_id', 'note_shares', ['note_id'], unique=False)
    op.create_index('ix_note_shares_shared_with_user_id', 'note_shares', ['shared_with_user_id'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_note_shares_shared_with_user_id', table_name='note_shares')
    op.drop_index('ix_note_shares_note_id', table_name='note_shares')
    op.drop_index('ix_notes_channel_id', table_name='notes')
    op.drop_index('ix_notes_workspace_id', table_name='notes')
    op.drop_index('ix_notes_owner_id', table_name='notes')
    
    # Drop tables
    op.drop_table('note_shares')
    op.drop_table('notes')
