"""Add message reactions and artifact source message

Revision ID: 015
Revises: 014_add_attachments
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '015_add_reactions'
down_revision = '014_add_attachments'
branch_labels = None
depends_on = None


def upgrade():
    # Create message_reactions table
    op.create_table(
        'message_reactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('emoji', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id', 'user_id', 'emoji', name='uq_message_user_emoji')
    )
    op.create_index('ix_message_reactions_message_id', 'message_reactions', ['message_id'])
    
    # Add source_message_id to artifacts table to link artifacts back to source messages
    op.add_column('artifacts', sa.Column('source_message_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_artifact_source_message',
        'artifacts', 'messages',
        ['source_message_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    # Drop source_message_id from artifacts
    op.drop_constraint('fk_artifact_source_message', 'artifacts', type_='foreignkey')
    op.drop_column('artifacts', 'source_message_id')
    
    # Drop message_reactions table
    op.drop_index('ix_message_reactions_message_id', 'message_reactions')
    op.drop_table('message_reactions')
