"""
Channel model for chat channels.
"""

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Channel(Base, TimestampMixin):
    """Channel model for chat."""
    
    __tablename__ = "channels"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(250), nullable=True)
    
    # Channel type
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_dm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Product link (optional)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    
    # Default channel for product
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Archived status
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="channels")
    product = relationship("Product", back_populates="channels")
    messages = relationship("Message", back_populates="channel", lazy="noload", order_by="Message.created_at")
    memberships = relationship("ChannelMembership", back_populates="channel", lazy="selectin")
    artifacts = relationship("Artifact", back_populates="channel", lazy="noload")
    
    @property
    def display_name(self) -> str:
        """Get display name with # prefix for public channels."""
        if self.is_dm:
            return self.name
        return f"#{self.name}"
    
    def __repr__(self) -> str:
        return f"<Channel #{self.name}>"
