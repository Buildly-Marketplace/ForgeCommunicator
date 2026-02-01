"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('buildly_user_id', sa.String(100), nullable=True, unique=True),
        sa.Column('google_user_id', sa.String(100), nullable=True, unique=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('invite_code', sa.String(20), unique=True, nullable=True),
        sa.Column('owner_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Memberships table
    op.create_table(
        'memberships',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', sa.Integer, sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), default='member', nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'workspace_id', name='uq_membership'),
    )
    op.create_index('ix_memberships_user_workspace', 'memberships', ['user_id', 'workspace_id'])

    # Products table
    op.create_table(
        'products',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('workspace_id', sa.Integer, sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('buildly_product_id', sa.String(100), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_products_workspace', 'products', ['workspace_id'])

    # Channels table
    op.create_table(
        'channels',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('workspace_id', sa.Integer, sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', sa.Integer, sa.ForeignKey('products.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('topic', sa.String(250), nullable=True),
        sa.Column('is_private', sa.Boolean, default=False, nullable=False),
        sa.Column('is_dm', sa.Boolean, default=False, nullable=False),
        sa.Column('created_by_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_channel_name'),
    )
    op.create_index('ix_channels_workspace', 'channels', ['workspace_id'])

    # Channel memberships table
    op.create_table(
        'channel_memberships',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel_id', sa.Integer, sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'channel_id', name='uq_channel_membership'),
    )
    op.create_index('ix_channel_memberships_user_channel', 'channel_memberships', ['user_id', 'channel_id'])

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('channel_id', sa.Integer, sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean, default=False, nullable=False),
        sa.Column('thread_parent_id', sa.Integer, sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_messages_channel_created', 'messages', ['channel_id', 'created_at'])

    # Artifacts table
    op.create_table(
        'artifacts',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('channel_id', sa.Integer, sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('message_id', sa.Integer, sa.ForeignKey('messages.id', ondelete='SET NULL'), nullable=True),
        sa.Column('type', sa.String(20), nullable=False),  # decision, feature, issue, task
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text, nullable=True),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), default=[], nullable=True),
        sa.Column('assignee_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('github_issue_url', sa.String(512), nullable=True),
        sa.Column('buildly_artifact_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_artifacts_channel_type', 'artifacts', ['channel_id', 'type'])


def downgrade() -> None:
    op.drop_table('artifacts')
    op.drop_table('messages')
    op.drop_table('channel_memberships')
    op.drop_table('channels')
    op.drop_table('products')
    op.drop_table('memberships')
    op.drop_table('workspaces')
    op.drop_table('users')
