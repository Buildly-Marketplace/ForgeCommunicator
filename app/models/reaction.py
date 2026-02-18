"""
Message reaction model for emoji reactions on messages.
"""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class MessageReaction(Base, TimestampMixin):
    """Model for emoji reactions on messages."""
    
    __tablename__ = "message_reactions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    # Emoji - stored as unicode character(s) or shortcode
    emoji: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Relationships
    message = relationship("Message", back_populates="reactions")
    user = relationship("User")
    
    # One user can only react with each emoji once per message
    __table_args__ = (
        UniqueConstraint('message_id', 'user_id', 'emoji', name='uq_message_user_emoji'),
    )
    
    def __repr__(self) -> str:
        return f"<MessageReaction {self.emoji} by user {self.user_id} on message {self.message_id}>"
