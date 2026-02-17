"""Add attachments table for file uploads

Revision ID: 014_add_attachments
Revises: 013_add_user_sessions
Create Date: 2026-02-17

This migration adds the attachments table to support file uploads in channels and DMs.
Files are stored in DigitalOcean Spaces (S3-compatible) with metadata in the database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# Revision identifiers, used by Alembic.
revision: str = '014_add_attachments'
down_revision: Union[str, None] = '013_add_user_sessions'
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


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Create attachments table
    if not table_exists('attachments'):
        op.create_table(
            'attachments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('original_filename', sa.String(length=255), nullable=False),
            sa.Column('storage_key', sa.String(length=512), nullable=False),
            sa.Column('content_type', sa.String(length=100), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('attachment_type', sa.String(length=20), nullable=False),
            sa.Column('message_id', sa.Integer(), nullable=True),
            sa.Column('channel_id', sa.Integer(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        
        # Create indexes
        op.create_index('ix_attachments_message_id', 'attachments', ['message_id'], unique=False)
        op.create_index('ix_attachments_channel_id', 'attachments', ['channel_id'], unique=False)
        op.create_index('ix_attachments_user_id', 'attachments', ['user_id'], unique=False)
        op.create_index('ix_attachments_storage_key', 'attachments', ['storage_key'], unique=True)
        op.create_index('ix_attachments_created_at', 'attachments', ['created_at'], unique=False)
    else:
        # Table exists - add any missing columns for existing databases
        if not column_exists('attachments', 'updated_at'):
            op.add_column('attachments', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    # Drop indexes first
    if table_exists('attachments'):
        if index_exists('ix_attachments_created_at', 'attachments'):
            op.drop_index('ix_attachments_created_at', table_name='attachments')
        if index_exists('ix_attachments_storage_key', 'attachments'):
            op.drop_index('ix_attachments_storage_key', table_name='attachments')
        if index_exists('ix_attachments_user_id', 'attachments'):
            op.drop_index('ix_attachments_user_id', table_name='attachments')
        if index_exists('ix_attachments_channel_id', 'attachments'):
            op.drop_index('ix_attachments_channel_id', table_name='attachments')
        if index_exists('ix_attachments_message_id', 'attachments'):
            op.drop_index('ix_attachments_message_id', table_name='attachments')
        op.drop_table('attachments')
