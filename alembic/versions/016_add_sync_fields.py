"""Add artifact sync fields to workspace

Revision ID: 016
Revises: 015_add_reactions_and_artifact_source
Create Date: 2026-02-18

Adds GitHub and Labs integration fields to workspace for artifact syncing.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '016_add_sync_fields'
down_revision = '015_add_reactions'
branch_labels = None
depends_on = None


def upgrade():
    # Add Labs default product UUID
    op.add_column('workspaces', sa.Column('labs_default_product_uuid', sa.String(36), nullable=True))
    
    # Add GitHub integration fields
    op.add_column('workspaces', sa.Column('github_repo', sa.String(255), nullable=True))
    op.add_column('workspaces', sa.Column('github_token', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('workspaces', 'github_token')
    op.drop_column('workspaces', 'github_repo')
    op.drop_column('workspaces', 'labs_default_product_uuid')
