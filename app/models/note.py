"""
Note model for user notes and notebooks.

Notes are personal markdown documents that can be:
- Created by a user
- Associated with a channel or thread (for context)
- Shared with other users or channels
- Collected from messages/threads via copy
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class NoteVisibility(str, Enum):
    """Note visibility levels."""
    PRIVATE = "private"  # Only the owner can see
    SHARED = "shared"    # Shared with specific users/channels


class NoteSourceType(str, Enum):
    """Source type when note was created from content."""
    MANUAL = "manual"        # Created manually by user
    MESSAGE = "message"      # Copied from a single message
    THREAD = "thread"        # Copied from a thread
    CHANNEL = "channel"      # Copied from channel messages


class Note(Base, TimestampMixin):
    """User note/notebook entry."""
    
    __tablename__ = "notes"
    __table_args__ = (
        Index("ix_notes_owner_id", "owner_id"),
        Index("ix_notes_channel_id", "channel_id"),
        Index("ix_notes_workspace_id", "workspace_id"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Owner - required
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Optional workspace/channel context
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True
    )
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=True
    )
    
    # Note content
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled Note")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    
    # Visibility
    visibility: Mapped[NoteVisibility] = mapped_column(
        String(20),
        default=NoteVisibility.PRIVATE,
        nullable=False
    )
    
    # Source tracking (where the note content came from)
    source_type: Mapped[NoteSourceType] = mapped_column(
        String(20),
        default=NoteSourceType.MANUAL,
        nullable=False
    )
    source_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="notes", foreign_keys=[owner_id])
    workspace = relationship("Workspace")
    channel = relationship("Channel")
    source_message = relationship("Message")
    shares = relationship("NoteShare", back_populates="note", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title[:30]}...', owner_id={self.owner_id})>"
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
    
    def soft_delete(self) -> None:
        """Mark note as deleted."""
        self.deleted_at = datetime.now(timezone.utc)
    
    def can_view(self, user_id: int, shared_user_ids: list[int] | None = None) -> bool:
        """Check if a user can view this note."""
        # Owner can always view
        if self.owner_id == user_id:
            return True
        
        # If shared, check shares
        if self.visibility == NoteVisibility.SHARED and shared_user_ids:
            return user_id in shared_user_ids
        
        return False
    
    def can_edit(self, user_id: int) -> bool:
        """Check if a user can edit this note."""
        return self.owner_id == user_id


class NoteShare(Base, TimestampMixin):
    """Share a note with a user or channel."""
    
    __tablename__ = "note_shares"
    __table_args__ = (
        # A note can only be shared once with a specific user or channel
        UniqueConstraint("note_id", "shared_with_user_id", name="uq_note_share_user"),
        UniqueConstraint("note_id", "shared_with_channel_id", name="uq_note_share_channel"),
        Index("ix_note_shares_note_id", "note_id"),
        Index("ix_note_shares_shared_with_user_id", "shared_with_user_id"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Share with a user
    shared_with_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True
    )
    
    # OR share with a channel (visible to all channel members)
    shared_with_channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=True
    )
    
    # Who shared it
    shared_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Optional message for the share
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Relationships
    note = relationship("Note", back_populates="shares")
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    shared_with_channel = relationship("Channel")
    shared_by = relationship("User", foreign_keys=[shared_by_id])
    
    def __repr__(self) -> str:
        if self.shared_with_user_id:
            return f"<NoteShare(note_id={self.note_id}, user_id={self.shared_with_user_id})>"
        return f"<NoteShare(note_id={self.note_id}, channel_id={self.shared_with_channel_id})>"
