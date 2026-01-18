"""
User model for authentication and identity.
"""

import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin
from app.settings import settings


class AuthProvider(str, Enum):
    LOCAL = "local"
    GOOGLE = "google"
    BUILDLY = "buildly"


class User(Base, TimestampMixin):
    """User account model."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Local auth
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # OAuth
    auth_provider: Mapped[AuthProvider] = mapped_column(
        String(20), 
        default=AuthProvider.LOCAL,
        nullable=False,
    )
    provider_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)  # OAuth subject ID
    
    # Avatar
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Session management
    session_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    memberships = relationship("Membership", back_populates="user", lazy="selectin")
    messages = relationship("Message", back_populates="user", lazy="noload")
    
    def generate_session_token(self) -> str:
        """Generate a new session token and set expiry."""
        self.session_token = secrets.token_hex(32)
        self.session_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_expire_hours)
        return self.session_token
    
    def clear_session(self) -> None:
        """Clear session token."""
        self.session_token = None
        self.session_expires_at = None
    
    def is_session_valid(self) -> bool:
        """Check if current session is valid."""
        if not self.session_token or not self.session_expires_at:
            return False
        return datetime.now(timezone.utc) < self.session_expires_at
    
    def update_last_seen(self) -> None:
        """Update last seen timestamp."""
        self.last_seen_at = datetime.now(timezone.utc)
    
    def __repr__(self) -> str:
        return f"<User {self.email}>"
