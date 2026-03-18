"""Add thread_read_states table for tracking thread read status

Revision ID: 023_add_thread_read_states
Revises: 022_drop_messages_is_deleted
Create Date: 2026-03-18

Tracks which thread replies users have read to show "X new replies" instead of "X replies"
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '023_add_thread_read_states'
down_revision: Union[str, None] = '022_drop_messages_is_deleted'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'thread_read_states' not in existing_tables:
        op.create_table(
            'thread_read_states',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('parent_message_id', sa.Integer(), nullable=False),
            sa.Column('last_read_reply_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['parent_message_id'], ['messages.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'parent_message_id', name='uq_thread_read_user_message'),
        )
        # Add index for fast lookups
        op.create_index('ix_thread_read_states_user_message', 'thread_read_states', ['user_id', 'parent_message_id'])


def downgrade() -> None:
    op.drop_index('ix_thread_read_states_user_message', table_name='thread_read_states')
    op.drop_table('thread_read_states')
