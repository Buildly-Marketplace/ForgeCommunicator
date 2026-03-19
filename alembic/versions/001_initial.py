"""Comprehensive initial schema - all tables matching current models.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        # Profile
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("title", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=True, default="UTC"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("status_message", sa.String(100), nullable=True),
        # Local auth
        sa.Column("hashed_password", sa.String(255), nullable=True),
        # OAuth
        sa.Column("auth_provider", sa.String(20), nullable=False, server_default="local"),
        sa.Column("provider_sub", sa.String(255), nullable=True),
        # Buildly Labs SSO
        sa.Column("labs_user_id", sa.Integer, nullable=True),
        sa.Column("labs_org_uuid", sa.String(36), nullable=True),
        sa.Column("labs_access_token", sa.Text, nullable=True),
        sa.Column("labs_refresh_token", sa.Text, nullable=True),
        sa.Column("labs_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        # CollabHub
        sa.Column("collabhub_user_uuid", sa.String(36), nullable=True),
        sa.Column("collabhub_org_uuid", sa.String(36), nullable=True),
        sa.Column("collabhub_synced_at", sa.DateTime(timezone=True), nullable=True),
        # Social profiles
        sa.Column("github_url", sa.String(255), nullable=True),
        sa.Column("linkedin_url", sa.String(255), nullable=True),
        sa.Column("twitter_url", sa.String(255), nullable=True),
        sa.Column("website_url", sa.String(255), nullable=True),
        # Public stats
        sa.Column("community_reputation", sa.Integer, nullable=True, server_default="0"),
        sa.Column("projects_count", sa.Integer, nullable=True, server_default="0"),
        sa.Column("contributions_count", sa.Integer, nullable=True, server_default="0"),
        # CollabHub roles
        sa.Column("collabhub_roles", sa.JSON, nullable=True),
        # Google Workspace
        sa.Column("google_sub", sa.String(255), nullable=True),
        sa.Column("google_access_token", sa.Text, nullable=True),
        sa.Column("google_refresh_token", sa.Text, nullable=True),
        sa.Column("google_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("google_calendar_status", sa.String(20), nullable=True),
        sa.Column("google_calendar_message", sa.String(100), nullable=True),
        sa.Column("google_calendar_synced_at", sa.DateTime(timezone=True), nullable=True),
        # Avatar
        sa.Column("avatar_url", sa.Text, nullable=True),
        # Session management
        sa.Column("session_token", sa.String(64), unique=True, nullable=True),
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True),
        # Status flags
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_platform_admin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        # Account approval
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("can_create_workspaces", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_session_token", "users", ["session_token"])

    # ── workspaces ───────────────────────────────────────────────────────
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        # Google
        sa.Column("google_domain", sa.String(255), nullable=True),
        sa.Column("google_auto_join", sa.Boolean, nullable=False, server_default=sa.text("false")),
        # Buildly Labs
        sa.Column("buildly_org_uuid", sa.String(36), nullable=True),
        sa.Column("labs_api_token", sa.Text, nullable=True),
        sa.Column("labs_access_token", sa.Text, nullable=True),
        sa.Column("labs_refresh_token", sa.Text, nullable=True),
        sa.Column("labs_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("labs_connected_by_id", sa.Integer, nullable=True),
        sa.Column("labs_default_product_uuid", sa.String(36), nullable=True),
        # GitHub
        sa.Column("github_repo", sa.String(255), nullable=True),
        sa.Column("github_token", sa.Text, nullable=True),
        # Invite
        sa.Column("invite_code", sa.String(20), unique=True, nullable=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        # Settings
        sa.Column("icon_url", sa.String(500), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])

    # ── products ─────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("buildly_product_uuid", sa.String(36), nullable=True),
        sa.Column("github_repo_url", sa.String(500), nullable=True),
        sa.Column("github_org", sa.String(100), nullable=True),
        sa.Column("icon_url", sa.String(500), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_products_buildly_product_uuid", "products", ["buildly_product_uuid"])

    # ── channels ─────────────────────────────────────────────────────────
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("topic", sa.String(250), nullable=True),
        sa.Column("is_private", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_dm", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── memberships ──────────────────────────────────────────────────────
    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("notifications_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notify_all_messages", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_membership_workspace_user"),
    )

    # ── channel_memberships ──────────────────────────────────────────────
    op.create_table(
        "channel_memberships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_read_message_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("channel_id", "user_id", name="uq_channel_membership_channel_user"),
    )

    # ── messages ─────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("thread_reply_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # External source tracking
        sa.Column("external_source", sa.String(20), nullable=True),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column("external_channel_id", sa.String(255), nullable=True),
        sa.Column("external_thread_ts", sa.String(255), nullable=True),
        sa.Column("external_author_name", sa.String(255), nullable=True),
        sa.Column("external_author_avatar", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_channel_id", "messages", ["channel_id"])
    op.create_index("ix_messages_external_source", "messages", ["external_source"])

    # ── thread_read_states ───────────────────────────────────────────────
    op.create_table(
        "thread_read_states",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_read_reply_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "parent_message_id", name="uq_thread_read_user_message"),
    )

    # ── team_invites ─────────────────────────────────────────────────────
    op.create_table(
        "team_invites",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("labs_user_uuid", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "email", name="uq_team_invite_workspace_email"),
    )
    op.create_index("ix_team_invites_email", "team_invites", ["email"])

    # ── push_subscriptions ───────────────────────────────────────────────
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("p256dh_key", sa.String(255), nullable=False),
        sa.Column("auth_key", sa.String(255), nullable=False),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "endpoint", name="uq_push_sub_user_endpoint"),
    )

    # ── notes ────────────────────────────────────────────────────────────
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False, server_default="Untitled Note"),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="private"),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("source_message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notes_owner_id", "notes", ["owner_id"])
    op.create_index("ix_notes_channel_id", "notes", ["channel_id"])
    op.create_index("ix_notes_workspace_id", "notes", ["workspace_id"])

    # ── note_shares ──────────────────────────────────────────────────────
    op.create_table(
        "note_shares",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("note_id", sa.Integer, sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shared_with_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("shared_with_channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=True),
        sa.Column("shared_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("note_id", "shared_with_user_id", name="uq_note_share_user"),
        sa.UniqueConstraint("note_id", "shared_with_channel_id", name="uq_note_share_channel"),
    )
    op.create_index("ix_note_shares_note_id", "note_shares", ["note_id"])
    op.create_index("ix_note_shares_shared_with_user_id", "note_shares", ["shared_with_user_id"])

    # ── external_integrations ────────────────────────────────────────────
    op.create_table(
        "external_integrations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_type", sa.Enum("slack", "discord", name="integrationtype"), nullable=False),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_user_id", sa.String(255), nullable=True),
        sa.Column("external_team_id", sa.String(255), nullable=True),
        sa.Column("external_username", sa.String(255), nullable=True),
        sa.Column("external_team_name", sa.String(255), nullable=True),
        sa.Column("webhook_url", sa.Text, nullable=True),
        sa.Column("bot_token", sa.Text, nullable=True),
        sa.Column("notification_preferences", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── notification_logs ────────────────────────────────────────────────
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", sa.Integer, sa.ForeignKey("external_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "slack_dm", "slack_mention", "slack_channel",
                "discord_dm", "discord_mention", "discord_channel",
                name="notificationsource",
            ),
            nullable=False,
        ),
        sa.Column("sender_name", sa.String(255), nullable=False),
        sa.Column("sender_avatar_url", sa.Text, nullable=True),
        sa.Column("sender_external_id", sa.String(255), nullable=True),
        sa.Column("channel_name", sa.String(255), nullable=True),
        sa.Column("channel_external_id", sa.String(255), nullable=True),
        sa.Column("message_body", sa.Text, nullable=False),
        sa.Column("message_preview", sa.String(500), nullable=False),
        sa.Column("external_url", sa.Text, nullable=True),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column("external_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── bridged_channels ─────────────────────────────────────────────────
    op.create_table(
        "bridged_channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", sa.Integer, sa.ForeignKey("external_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("external_channel_id", sa.String(255), nullable=False),
        sa.Column("external_channel_name", sa.String(255), nullable=False),
        sa.Column("external_team_id", sa.String(255), nullable=True),
        sa.Column("external_guild_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sync_incoming", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sync_outgoing", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("import_history", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_id", sa.String(255), nullable=True),
        sa.Column("messages_imported", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reply_prefix", sa.String(100), nullable=False, server_default="From Buildly Communicator"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("integration_id", "external_channel_id", name="uix_integration_external_channel"),
    )
    op.create_index("ix_bridged_channels_channel_id", "bridged_channels", ["channel_id"])
    op.create_index("ix_bridged_channels_external_channel_id", "bridged_channels", ["external_channel_id"])

    # ── site_configs ─────────────────────────────────────────────────────
    op.create_table(
        "site_configs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("json_value", sa.JSON, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("updated_by", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_site_configs_key", "site_configs", ["key"])

    # ── user_sessions ────────────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_name", sa.String(100), nullable=True),
        sa.Column("device_type", sa.String(20), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_pwa", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_session_token", "user_sessions", ["session_token"])

    # ── attachments ──────────────────────────────────────────────────────
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), unique=True, nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("attachment_type", sa.String(20), nullable=False),
    )
    op.create_index("ix_attachments_created_at", "attachments", ["created_at"])
    op.create_index("ix_attachments_message_id", "attachments", ["message_id"])
    op.create_index("ix_attachments_channel_id", "attachments", ["channel_id"])

    # ── message_reactions ────────────────────────────────────────────────
    op.create_table(
        "message_reactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emoji", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("message_id", "user_id", "emoji", name="uq_message_user_emoji"),
    )
    op.create_index("ix_message_reactions_message_id", "message_reactions", ["message_id"])

    # ── artifacts ────────────────────────────────────────────────────────
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_issue_url", sa.String(500), nullable=True),
        sa.Column("buildly_item_uuid", sa.String(36), nullable=True),
        sa.Column("source_message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("assignee_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_artifacts_type", "artifacts", ["type"])

    # ── ai_agents ────────────────────────────────────────────────────────
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="user"),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("api_key", sa.Text, nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("capabilities", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer, nullable=False, server_default="4096"),
        sa.Column("context_messages", sa.Integer, nullable=False, server_default="20"),
        sa.Column("can_read_channels", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("can_read_dms", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("can_read_notes", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("can_read_artifacts", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("total_tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_messages", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_agents_workspace_id", "ai_agents", ["workspace_id"])
    op.create_index("ix_ai_agents_owner_id", "ai_agents", ["owner_id"])

    # ── ai_conversations ─────────────────────────────────────────────────
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agent_id", sa.Integer, sa.ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("context_summary", sa.Text, nullable=True),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_conversations_agent_id", "ai_conversations", ["agent_id"])
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.create_index("ix_ai_conversations_channel_id", "ai_conversations", ["channel_id"])

    # ── ai_messages ──────────────────────────────────────────────────────
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("referenced_message_ids", sa.JSON, nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])

    # ── ai_channel_memberships ───────────────────────────────────────────
    op.create_table(
        "ai_channel_memberships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agent_id", sa.Integer, sa.ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("respond_to_mentions", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("respond_to_all", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("auto_summarize", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_channel_memberships_agent_id", "ai_channel_memberships", ["agent_id"])
    op.create_index("ix_ai_channel_memberships_channel_id", "ai_channel_memberships", ["channel_id"])


def downgrade() -> None:
    op.drop_table("ai_channel_memberships")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_table("ai_agents")
    op.drop_table("artifacts")
    op.drop_table("message_reactions")
    op.drop_table("attachments")
    op.drop_table("user_sessions")
    op.drop_table("site_configs")
    op.drop_table("bridged_channels")
    op.drop_table("notification_logs")
    op.drop_table("external_integrations")
    sa.Enum("slack", "discord", name="integrationtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "slack_dm", "slack_mention", "slack_channel",
        "discord_dm", "discord_mention", "discord_channel",
        name="notificationsource",
    ).drop(op.get_bind(), checkfirst=True)
    op.drop_table("note_shares")
    op.drop_table("notes")
    op.drop_table("push_subscriptions")
    op.drop_table("team_invites")
    op.drop_table("thread_read_states")
    op.drop_table("messages")
    op.drop_table("channel_memberships")
    op.drop_table("memberships")
    op.drop_table("channels")
    op.drop_table("products")
    op.drop_table("workspaces")
    op.drop_table("users")
