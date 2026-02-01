"""
Bridged channel model for linking Forge channels with external Slack/Discord channels.
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class BridgePlatform(str, Enum):
    """External platforms that can be bridged."""
    SLACK = "slack"
    DISCORD = "discord"


class BridgedChannel(Base, TimestampMixin):
    """
    Links a Forge Communicator channel to an external Slack or Discord channel.
    Enables two-way message sync between platforms.
    """
    __tablename__ = "bridged_channels"
    
    __table_args__ = (
        # Unique constraint: one bridge per external channel per integration
        UniqueConstraint('integration_id', 'external_channel_id', name='uix_integration_external_channel'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Link to Forge channel
    channel_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("channels.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Link to user's integration (contains OAuth tokens)
    integration_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("external_integrations.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    # External channel info
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # 'slack' or 'discord'
    external_channel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_team_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Slack workspace ID
    external_guild_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Discord server ID
    
    # Sync settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sync_incoming: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Sync messages FROM external
    sync_outgoing: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Sync messages TO external
    import_history: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Import full history
    
    # Tracking
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Last synced message ID
    messages_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Reply prefix setting (customizable per bridge)
    reply_prefix: Mapped[str] = mapped_column(
        String(100), 
        default="From Buildly Communicator", 
        nullable=False
    )
    
    # Relationships
    channel = relationship("Channel", backref="bridges", lazy="joined")
    integration = relationship("ExternalIntegration", lazy="joined")
    
    def __repr__(self) -> str:
        return f"<BridgedChannel {self.platform}:{self.external_channel_name} <-> Channel {self.channel_id}>"
    
    @property
    def is_slack(self) -> bool:
        return self.platform == BridgePlatform.SLACK.value
    
    @property
    def is_discord(self) -> bool:
        return self.platform == BridgePlatform.DISCORD.value
    
    def update_last_sync(self, message_id: str | None = None) -> None:
        """Update last sync timestamp and optionally the last message ID."""
        self.last_sync_at = datetime.now(timezone.utc)
        if message_id:
            self.last_message_id = message_id
    
    def format_outgoing_message(self, message_body: str, author_name: str) -> str:
        """Format a message for sending to external platform with prefix."""
        prefix = self.reply_prefix or "From Buildly Communicator"
        return f"*{prefix}* ({author_name}):\n{message_body}"
