"""
User session model for multi-device session management.

Allows users to be logged in on multiple devices simultaneously.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin
from app.settings import settings


class UserSession(Base, TimestampMixin):
    """
    Individual user session for multi-device support.
    
    Each login creates a new session record, allowing the same user
    to be logged in on multiple devices without invalidating other sessions.
    """
    
    __tablename__ = "user_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Session token - unique per session
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    
    # Expiration
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Device/client information for session management UI
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "iPhone 15", "Chrome on Windows"
    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "mobile", "desktop", "tablet", "pwa"
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)  # Full user agent string
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6
    
    # Activity tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # PWA flag - PWA sessions get longer expiration
    is_pwa: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    @classmethod
    def create_session(
        cls,
        user_id: int,
        request=None,
        is_pwa: bool = False,
    ) -> "UserSession":
        """
        Create a new session for a user.
        
        Args:
            user_id: The user's ID
            request: Optional FastAPI request object for device detection
            is_pwa: Whether this is a PWA session (longer expiration)
        
        Returns:
            New UserSession instance (not yet added to DB)
        """
        # Generate secure token
        token = secrets.token_hex(32)
        
        # Calculate expiration based on PWA vs browser
        expire_hours = settings.session_expire_hours_pwa if is_pwa else settings.session_expire_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
        
        # Extract device info from request
        device_name = None
        device_type = None
        user_agent = None
        ip_address = None
        
        if request:
            user_agent = request.headers.get("User-Agent", "")
            ip_address = cls._get_client_ip(request)
            device_name, device_type = cls._parse_device_info(user_agent, request)
        
        return cls(
            user_id=user_id,
            session_token=token,
            expires_at=expires_at,
            device_name=device_name,
            device_type=device_type,
            user_agent=user_agent,
            ip_address=ip_address,
            is_pwa=is_pwa,
            last_used_at=datetime.now(timezone.utc),
        )
    
    @staticmethod
    def _get_client_ip(request) -> str | None:
        """Extract client IP from request, handling proxies."""
        # Check forwarded headers (in order of preference)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, first is the client
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return None
    
    @staticmethod
    def _parse_device_info(user_agent: str, request) -> tuple[str | None, str | None]:
        """Parse user agent to extract device name and type."""
        if not user_agent:
            return None, None
        
        ua_lower = user_agent.lower()
        
        # Check for PWA mode
        is_pwa = (
            request.headers.get("Sec-Fetch-Dest") == "document" and
            "standalone" in request.headers.get("Sec-Fetch-Site", "")
        ) or request.headers.get("X-PWA-Mode") == "standalone"
        
        # Detect device type
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            device_type = "pwa" if is_pwa else "mobile"
        elif "ipad" in ua_lower or "tablet" in ua_lower:
            device_type = "pwa" if is_pwa else "tablet"
        else:
            device_type = "pwa" if is_pwa else "desktop"
        
        # Build friendly device name
        device_name = None
        
        # iOS devices
        if "iphone" in ua_lower:
            device_name = "iPhone"
        elif "ipad" in ua_lower:
            device_name = "iPad"
        # Android devices
        elif "android" in ua_lower:
            device_name = "Android Device"
        # Desktop browsers
        elif "chrome" in ua_lower and "edg" not in ua_lower:
            if "mac" in ua_lower:
                device_name = "Chrome on Mac"
            elif "windows" in ua_lower:
                device_name = "Chrome on Windows"
            elif "linux" in ua_lower:
                device_name = "Chrome on Linux"
            else:
                device_name = "Chrome"
        elif "firefox" in ua_lower:
            if "mac" in ua_lower:
                device_name = "Firefox on Mac"
            elif "windows" in ua_lower:
                device_name = "Firefox on Windows"
            else:
                device_name = "Firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            device_name = "Safari on Mac"
        elif "edg" in ua_lower:
            device_name = "Edge"
        
        if is_pwa and device_name:
            device_name = f"{device_name} (PWA)"
        
        return device_name, device_type
    
    def is_valid(self) -> bool:
        """Check if session is still valid (not expired)."""
        return datetime.now(timezone.utc) < self.expires_at
    
    def refresh(self) -> None:
        """Refresh session - update last_used_at and optionally extend expiration."""
        self.last_used_at = datetime.now(timezone.utc)
        
        # Sliding window: extend expiration if session is used and has less than half time remaining
        expire_hours = settings.session_expire_hours_pwa if self.is_pwa else settings.session_expire_hours
        half_life = timedelta(hours=expire_hours / 2)
        
        time_remaining = self.expires_at - datetime.now(timezone.utc)
        if time_remaining < half_life:
            self.expires_at = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    
    def __repr__(self) -> str:
        return f"<UserSession {self.id} user={self.user_id} device={self.device_name}>"
