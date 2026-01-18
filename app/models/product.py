"""
Product model for Buildly Labs integration.
"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Product(Base, TimestampMixin):
    """Product model (Buildly Labs concept)."""
    
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # External integrations
    buildly_product_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    github_repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_org: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Settings
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="products")
    channels = relationship("Channel", back_populates="product", lazy="noload")
    artifacts = relationship("Artifact", back_populates="product", lazy="noload")
    
    def __repr__(self) -> str:
        return f"<Product {self.name}>"
