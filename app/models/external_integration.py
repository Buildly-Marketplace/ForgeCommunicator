"""
External integration models for Slack/Discord notifications.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class IntegrationType(str, Enum):
    """Types of external integrations."""
    SLACK = "slack"
    DISCORD = "discord"


class NotificationSource(str, Enum):
    """Source of a notification."""
    SLACK_DM = "slack_dm"
    SLACK_MENTION = "slack_mention"
    SLACK_CHANNEL = "slack_channel"
    DISCORD_DM = "discord_dm"
    DISCORD_MENTION = "discord_mention"
    DISCORD_CHANNEL = "discord_channel"


class ExternalIntegration(Base):
    """
    Stores OAuth tokens and settings for external integrations (Slack, Discord).
    Each user can have one integration per type.
    """
    __tablename__ = "external_integrations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    integration_type: Mapped[IntegrationType] = mapped_column(SQLEnum(IntegrationType), nullable=False)
    
    # OAuth tokens
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Integration-specific data (team ID, user ID on external platform, etc.)
    external_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_team_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Webhook URL for receiving notifications (Discord bot token, Slack webhook)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Notification preferences (stored as JSON for flexibility)
    # e.g., {"dm": true, "mentions": true, "channels": ["general", "dev"]}
    notification_preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="external_integrations", lazy="joined")
    
    def __repr__(self) -> str:
        return f"<ExternalIntegration {self.integration_type.value} for user {self.user_id}>"
    
    @property
    def is_connected(self) -> bool:
        """Check if integration is connected and has valid tokens."""
        return bool(self.access_token) and self.is_active
    
    @property
    def token_expired(self) -> bool:
        """Check if access token has expired."""
        if not self.token_expires_at:
            return False
        return datetime.now(timezone.utc) >= self.token_expires_at
    
    def update_tokens(self, access_token: str, refresh_token: str | None = None, expires_in: int | None = None):
        """Update OAuth tokens."""
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if expires_in:
            from datetime import timedelta
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        self.updated_at = datetime.now(timezone.utc)


class NotificationLog(Base):
    """
    Stores notifications received from external platforms.
    These are displayed in the user's personal notifications feed.
    """
    __tablename__ = "notification_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    integration_id: Mapped[int] = mapped_column(Integer, ForeignKey("external_integrations.id", ondelete="CASCADE"), nullable=False)
    
    # Notification details
    source: Mapped[NotificationSource] = mapped_column(SQLEnum(NotificationSource), nullable=False)
    
    # Sender info
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Channel/conversation info
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Message content
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    message_preview: Mapped[str] = mapped_column(String(500), nullable=False)  # Truncated for display
    
    # External link to original message
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notification_logs", lazy="joined")
    integration: Mapped["ExternalIntegration"] = relationship("ExternalIntegration", lazy="joined")
    
    def __repr__(self) -> str:
        return f"<NotificationLog {self.source.value} from {self.sender_name}>"
    
    @property
    def platform(self) -> str:
        """Get the platform name (slack or discord)."""
        return self.source.value.split("_")[0]
    
    @property
    def notification_type(self) -> str:
        """Get the notification type (dm, mention, channel)."""
        parts = self.source.value.split("_")
        return parts[1] if len(parts) > 1 else "message"
    
    @classmethod
    def create_from_slack(
        cls,
        user_id: int,
        integration_id: int,
        source: NotificationSource,
        sender_name: str,
        message_body: str,
        channel_name: str | None = None,
        external_url: str | None = None,
        **kwargs,
    ) -> "NotificationLog":
        """Create a notification log from a Slack event."""
        return cls(
            user_id=user_id,
            integration_id=integration_id,
            source=source,
            sender_name=sender_name,
            message_body=message_body,
            message_preview=message_body[:500] if len(message_body) > 500 else message_body,
            channel_name=channel_name,
            external_url=external_url,
            **kwargs,
        )
    
    @classmethod
    def create_from_discord(
        cls,
        user_id: int,
        integration_id: int,
        source: NotificationSource,
        sender_name: str,
        message_body: str,
        channel_name: str | None = None,
        external_url: str | None = None,
        **kwargs,
    ) -> "NotificationLog":
        """Create a notification log from a Discord event."""
        return cls(
            user_id=user_id,
            integration_id=integration_id,
            source=source,
            sender_name=sender_name,
            message_body=message_body,
            message_preview=message_body[:500] if len(message_body) > 500 else message_body,
            channel_name=channel_name,
            external_url=external_url,
            **kwargs,
        )
