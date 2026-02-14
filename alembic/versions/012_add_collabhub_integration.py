"""Add CollabHub integration fields

Revision ID: 012_add_collabhub_integration
Revises: 011_add_bridged_channels
Create Date: 2026-02-14

This migration adds fields to support CollabHub integration:
- CollabHub user/org UUIDs for identity linking
- Social profile URLs (GitHub, LinkedIn, Twitter, website)
- Community stats (reputation, projects, contributions)
- CollabHub roles (community member, dev team, customer)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = '012_add_collabhub_integration'
down_revision: Union[str, None] = '011_add_bridged_channels'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add CollabHub identity columns to users table
    op.add_column(
        'users',
        sa.Column('collabhub_user_uuid', sa.String(36), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('collabhub_org_uuid', sa.String(36), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('collabhub_synced_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Add social profile URLs
    op.add_column(
        'users',
        sa.Column('github_url', sa.String(255), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('linkedin_url', sa.String(255), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('twitter_url', sa.String(255), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('website_url', sa.String(255), nullable=True)
    )
    
    # Add community stats
    op.add_column(
        'users',
        sa.Column('community_reputation', sa.Integer(), nullable=True, server_default='0')
    )
    op.add_column(
        'users',
        sa.Column('projects_count', sa.Integer(), nullable=True, server_default='0')
    )
    op.add_column(
        'users',
        sa.Column('contributions_count', sa.Integer(), nullable=True, server_default='0')
    )
    
    # Add CollabHub roles (JSON field for flexibility)
    op.add_column(
        'users',
        sa.Column('collabhub_roles', sa.JSON(), nullable=True)
    )
    
    # Create index on collabhub_user_uuid for efficient lookups
    op.create_index(
        'ix_users_collabhub_user_uuid',
        'users',
        ['collabhub_user_uuid'],
        unique=False
    )
    
    # Create index on collabhub_org_uuid for org-based queries
    op.create_index(
        'ix_users_collabhub_org_uuid',
        'users',
        ['collabhub_org_uuid'],
        unique=False
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_users_collabhub_org_uuid', table_name='users')
    op.drop_index('ix_users_collabhub_user_uuid', table_name='users')
    
    # Drop CollabHub roles
    op.drop_column('users', 'collabhub_roles')
    
    # Drop community stats
    op.drop_column('users', 'contributions_count')
    op.drop_column('users', 'projects_count')
    op.drop_column('users', 'community_reputation')
    
    # Drop social profile URLs
    op.drop_column('users', 'website_url')
    op.drop_column('users', 'twitter_url')
    op.drop_column('users', 'linkedin_url')
    op.drop_column('users', 'github_url')
    
    # Drop CollabHub identity columns
    op.drop_column('users', 'collabhub_synced_at')
    op.drop_column('users', 'collabhub_org_uuid')
    op.drop_column('users', 'collabhub_user_uuid')
