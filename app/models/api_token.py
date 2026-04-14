"""
API token model for external service-to-service authentication.

Allows platform admins to generate long-lived API tokens from the
admin panel. These tokens authenticate against the /api/* endpoints
using DRF-style Token auth: Authorization: Token <token>
"""

import secrets
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


def generate_api_token() -> str:
    """Generate a secure random API token (48 hex chars)."""
    return secrets.token_hex(24)


class APIToken(Base, TimestampMixin):
    """
    Long-lived API token for external integrations.

    Each token is tied to the admin user who created it. When used
    for authentication the request runs as that user, inheriting
    their workspace memberships and permissions.
    """

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Human-readable label, e.g. "CollabHub production"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The admin user who owns this token
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Optional expiry – NULL means no expiry
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Revocation
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Activity tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")

    @classmethod
    def create(
        cls,
        user_id: int,
        name: str,
        description: str | None = None,
        expires_at: datetime | None = None,
    ) -> "APIToken":
        """Create a new API token."""
        return cls(
            token=generate_api_token(),
            name=name.strip(),
            description=description.strip() if description else None,
            user_id=user_id,
            expires_at=expires_at,
        )

    @property
    def is_valid(self) -> bool:
        """Check if token is active and not expired."""
        if not self.is_active:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def revoke(self) -> None:
        """Revoke this token."""
        self.is_active = False
        self.revoked_at = datetime.now(timezone.utc)

    def touch(self) -> None:
        """Update last_used_at timestamp."""
        self.last_used_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<APIToken {self.name!r} user={self.user_id} active={self.is_active}>"
