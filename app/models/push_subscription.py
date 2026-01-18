"""
Push subscription model for web push notifications.
"""

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class PushSubscription(Base, TimestampMixin):
    """Web push subscription for notifications."""
    
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", name="uq_push_sub_user_endpoint"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Push subscription data
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh_key: Mapped[str] = mapped_column(String(255), nullable=False)  # Public key
    auth_key: Mapped[str] = mapped_column(String(255), nullable=False)  # Auth secret
    
    # User agent for device identification
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="push_subscriptions")
    
    def __repr__(self) -> str:
        return f"<PushSubscription user={self.user_id}>"
