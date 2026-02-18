"""
Workspace model for multi-tenant organization.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


def generate_invite_code() -> str:
    """Generate a random invite code."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


class Workspace(Base, TimestampMixin):
    """Workspace (organization/team) model."""
    
    __tablename__ = "workspaces"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Google Workspace integration
    google_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_auto_join: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    # Buildly Labs integration
    buildly_org_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    labs_api_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # API token for Labs
    labs_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # OAuth access token
    labs_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # OAuth refresh token
    labs_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    labs_connected_by_id: Mapped[int | None] = mapped_column(nullable=True)  # User who connected the integration
    labs_default_product_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)  # Default product for syncing artifacts
    
    # GitHub integration
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Format: owner/repo
    github_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # Personal access token or app token
    
    # Invite system
    invite_code: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Settings
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Relationships
    memberships = relationship("Membership", back_populates="workspace", lazy="selectin")
    channels = relationship("Channel", back_populates="workspace", lazy="noload")
    products = relationship("Product", back_populates="workspace", lazy="noload")
    
    def generate_invite_code(self, expires_in_days: int = 7) -> str:
        """Generate a new invite code with expiry."""
        self.invite_code = generate_invite_code()
        self.invite_expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        return self.invite_code
    
    def is_invite_valid(self, code: str) -> bool:
        """Check if an invite code is valid."""
        if not self.invite_code or self.invite_code != code:
            return False
        if self.invite_expires_at and datetime.now(timezone.utc) > self.invite_expires_at:
            return False
        return True
    
    def __repr__(self) -> str:
        return f"<Workspace {self.slug}>"
