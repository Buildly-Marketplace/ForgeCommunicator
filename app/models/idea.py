"""
Idea model for quick captures from the mobile Capture app.

An Idea is a raw, low-friction note (text + optional photos/screenshots) that a
user jots down on their phone. It is later "refined" by AI into a structured
breakdown of features and issues with estimates, reviewed by the user, and then
"submitted" — which creates Artifacts in Forge and backlog items in Buildly Labs
that a developer, an AI coding agent, or both can pick up.

Lifecycle:  draft -> refining -> refined -> submitted
            refining -> failed (AI error; refine can be retried)
"""

from enum import Enum

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class IdeaKind(str, Enum):
    IDEA = "idea"  # New feature / product idea
    BUG = "bug"  # Problem with an app (on the phone or in Labs)
    FEEDBACK = "feedback"  # General feedback / UX note


class IdeaStatus(str, Enum):
    DRAFT = "draft"
    REFINING = "refining"
    REFINED = "refined"
    SUBMITTED = "submitted"
    FAILED = "failed"


class Idea(Base, TimestampMixin):
    """A quick capture from the mobile app, before it becomes real work."""

    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Client-generated id so offline captures can be retried without duplicates
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    kind: Mapped[str] = mapped_column(String(20), nullable=False, default=IdeaKind.IDEA.value)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=IdeaStatus.DRAFT.value)

    # [{"url": ..., "storage_key": ..., "filename": ..., "content_type": ..., "size": ...}]
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # For bug reports: {"app_name", "app_version", "os", "os_version", "device_model", "url", ...}
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # AI output — see app/services/idea_refiner.py for the shape
    breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Filled on submit: [{"artifact_id", "labs_uuid", "title", "type"}]
    submitted_items: Mapped[list | None] = mapped_column(JSON, nullable=True)

    workspace = relationship("Workspace")
    product = relationship("Product")
    author = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Idea {self.id} {self.kind}: {(self.title or self.body)[:30]}>"
