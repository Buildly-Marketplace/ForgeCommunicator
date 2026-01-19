"""Add Labs SSO columns to users table

Revision ID: 002_add_labs_sso
Revises: 001_initial
Create Date: 2026-01-19 14:45:00.000000

Adds columns for Buildly Labs OAuth SSO integration:
- labs_user_id: Numeric user ID from Labs for cross-app identity
- labs_org_uuid: Organization UUID for team membership sync
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_labs_sso'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Labs SSO columns to users table
    op.add_column(
        'users',
        sa.Column('labs_user_id', sa.Integer(), nullable=True),
        
    )
    op.add_column(
        'users',
        sa.Column('labs_org_uuid', sa.String(36), nullable=True),
    )
    
    # Create index on labs_user_id for efficient lookups during sync
    op.create_index('ix_users_labs_user_id', 'users', ['labs_user_id'])


def downgrade() -> None:
    # Remove index first
    op.drop_index('ix_users_labs_user_id', table_name='users')
    
    # Remove columns
    op.drop_column('users', 'labs_org_uuid')
    op.drop_column('users', 'labs_user_id')
