"""
Team invite model for workspace invitations.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


def generate_invite_token() -> str:
    """Generate a random invite token."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))


class InviteStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TeamInvite(Base, TimestampMixin):
    """Team invitation for workspace."""
    
    __tablename__ = "team_invites"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_team_invite_workspace_email"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    
    # Invitation details
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=generate_invite_token)
    
    # Role to assign when accepted
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    
    # Status tracking
    status: Mapped[InviteStatus] = mapped_column(String(20), default=InviteStatus.PENDING, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Tracking
    invited_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Labs sync tracking
    labs_user_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    
    # Relationships
    workspace = relationship("Workspace")
    invited_by = relationship("User", foreign_keys=[invited_by_id])
    accepted_by = relationship("User", foreign_keys=[accepted_by_id])
    
    @classmethod
    def create(
        cls,
        workspace_id: int,
        email: str,
        name: str | None = None,
        role: str = "member",
        invited_by_id: int | None = None,
        labs_user_uuid: str | None = None,
        expires_in_days: int = 7,
    ) -> "TeamInvite":
        """Create a new team invite."""
        return cls(
            workspace_id=workspace_id,
            email=email.lower().strip(),
            name=name,
            role=role,
            invited_by_id=invited_by_id,
            labs_user_uuid=labs_user_uuid,
            token=generate_invite_token(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
        )
    
    @property
    def is_valid(self) -> bool:
        """Check if invite is still valid."""
        if self.status != InviteStatus.PENDING:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        return True
    
    def get_invite_url(self, base_url: str) -> str:
        """Get the full invite URL."""
        return f"{base_url}/invites/{self.token}"
    
    def __repr__(self) -> str:
        return f"<TeamInvite {self.email} -> workspace={self.workspace_id} status={self.status}>"
