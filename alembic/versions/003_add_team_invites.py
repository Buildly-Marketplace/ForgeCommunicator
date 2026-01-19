"""Add team_invites table

Revision ID: 003_add_team_invites
Revises: 002_add_labs_sso
Create Date: 2026-01-19 16:00:00.000000

Creates team_invites table for workspace invitation management.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_team_invites'
down_revision: Union[str, None] = '002_add_labs_sso'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create team_invites table
    op.create_table(
        'team_invites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('token', sa.String(64), unique=True, nullable=False),
        sa.Column('role', sa.String(20), nullable=False, default='member'),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('invited_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('labs_user_uuid', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('workspace_id', 'email', name='uq_team_invite_workspace_email'),
    )


def downgrade() -> None:
    op.drop_table('team_invites')
