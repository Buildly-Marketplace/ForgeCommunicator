"""
Attachment model for file uploads in messages.
"""

from enum import Enum

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class AttachmentType(str, Enum):
    """File type categories for attachments."""
    IMAGE = "image"  # jpg, png, gif, webp, svg
    DOCUMENT = "document"  # pdf, doc, docx, xls, xlsx, ppt, pptx
    TEXT = "text"  # txt, md, csv, json, xml
    ARCHIVE = "archive"  # zip, tar, gz
    OTHER = "other"


# MIME type to AttachmentType mapping
MIME_TYPE_MAP = {
    # Images
    "image/jpeg": AttachmentType.IMAGE,
    "image/png": AttachmentType.IMAGE,
    "image/gif": AttachmentType.IMAGE,
    "image/webp": AttachmentType.IMAGE,
    "image/svg+xml": AttachmentType.IMAGE,
    # Documents
    "application/pdf": AttachmentType.DOCUMENT,
    "application/msword": AttachmentType.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": AttachmentType.DOCUMENT,
    "application/vnd.ms-excel": AttachmentType.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": AttachmentType.DOCUMENT,
    "application/vnd.ms-powerpoint": AttachmentType.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": AttachmentType.DOCUMENT,
    # Text
    "text/plain": AttachmentType.TEXT,
    "text/markdown": AttachmentType.TEXT,
    "text/csv": AttachmentType.TEXT,
    "application/json": AttachmentType.TEXT,
    "application/xml": AttachmentType.TEXT,
    "text/xml": AttachmentType.TEXT,
    # Archives
    "application/zip": AttachmentType.ARCHIVE,
    "application/x-tar": AttachmentType.ARCHIVE,
    "application/gzip": AttachmentType.ARCHIVE,
    "application/x-gzip": AttachmentType.ARCHIVE,
}


def get_attachment_type(mime_type: str) -> AttachmentType:
    """Determine attachment type from MIME type."""
    # Check exact match first
    if mime_type in MIME_TYPE_MAP:
        return MIME_TYPE_MAP[mime_type]
    
    # Check category prefix
    if mime_type.startswith("image/"):
        return AttachmentType.IMAGE
    if mime_type.startswith("text/"):
        return AttachmentType.TEXT
    
    return AttachmentType.OTHER


# File extensions for validation
ALLOWED_EXTENSIONS = {
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Text
    ".txt", ".md", ".csv", ".json", ".xml",
    # Archives
    ".zip", ".tar", ".gz", ".tgz",
}


def is_allowed_extension(filename: str) -> bool:
    """Check if file extension is allowed."""
    import os
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


class Attachment(Base, TimestampMixin):
    """
    File attachment model.
    
    Attachments are uploaded to S3-compatible storage (DigitalOcean Spaces)
    and linked to messages. Each attachment stores metadata about the file
    while the actual file is stored externally.
    """
    
    __tablename__ = "attachments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Ownership
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), 
        nullable=True, 
        index=True
    )
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), 
        nullable=True, 
        index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # Display/stored filename
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # Original upload name
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)  # S3 key
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)  # MIME type
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Size in bytes
    attachment_type: Mapped[str] = mapped_column(String(20), nullable=False)  # Category
    
    # Relationships
    message = relationship("Message", back_populates="attachments")
    channel = relationship("Channel", back_populates="attachments")
    user = relationship("User", back_populates="attachments")
    
    @property
    def is_image(self) -> bool:
        """Check if attachment is an image."""
        return self.attachment_type == AttachmentType.IMAGE
    
    @property
    def file_size_display(self) -> str:
        """Human-readable file size."""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
    
    @property
    def extension(self) -> str:
        """Get file extension."""
        import os
        return os.path.splitext(self.filename)[1].lower()
    
    def __repr__(self) -> str:
        return f"<Attachment {self.id} {self.filename}>"
