"""
Message model for chat messages.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Message(Base, TimestampMixin):
    """Message model for chat."""
    
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Content
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Threading (optional, phase 2)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    thread_reply_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Edit/delete tracking
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    channel = relationship("Channel", back_populates="messages")
    user = relationship("User", back_populates="messages")
    parent = relationship("Message", remote_side="Message.id", backref="replies")
    
    @property
    def is_edited(self) -> bool:
        return self.edited_at is not None
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
    
    def soft_delete(self) -> None:
        """Soft delete the message."""
        from datetime import timezone
        self.deleted_at = datetime.now(timezone.utc)
    
    def __repr__(self) -> str:
        return f"<Message {self.id} by user {self.user_id}>"
