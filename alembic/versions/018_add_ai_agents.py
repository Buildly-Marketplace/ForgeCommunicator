"""Add AI agents and conversations

Revision ID: 018
Revises: 017b
Create Date: 2026-03-18

Adds tables for AI agent configuration, conversations, and channel memberships.
Supports workspace-level and user-level AI assistants with multiple providers
(OpenAI/ChatGPT, Anthropic/Claude, Perplexity).
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017b_fix_notifications_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AI Agents table
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False, server_default="user"),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="4096"),
        sa.Column("context_messages", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("can_read_channels", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_read_dms", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_read_notes", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_read_artifacts", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("total_tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_agents_workspace_id", "ai_agents", ["workspace_id"])
    op.create_index("ix_ai_agents_owner_id", "ai_agents", ["owner_id"])
    
    # AI Conversations table
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_conversations_agent_id", "ai_conversations", ["agent_id"])
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.create_index("ix_ai_conversations_channel_id", "ai_conversations", ["channel_id"])
    
    # AI Messages table
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("referenced_message_ids", sa.JSON(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])
    
    # AI Channel Memberships table
    op.create_table(
        "ai_channel_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        sa.Column("respond_to_mentions", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("respond_to_all", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_summarize", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("agent_id", "channel_id", name="uq_ai_channel_membership"),
    )
    op.create_index("ix_ai_channel_memberships_agent_id", "ai_channel_memberships", ["agent_id"])
    op.create_index("ix_ai_channel_memberships_channel_id", "ai_channel_memberships", ["channel_id"])


def downgrade() -> None:
    op.drop_table("ai_channel_memberships")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_table("ai_agents")
