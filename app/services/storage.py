"""Storage service for file uploads using S3-compatible storage (DigitalOcean Spaces)."""
import uuid
from datetime import datetime
from typing import BinaryIO
import mimetypes

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.settings import settings
from app.models.attachment import is_allowed_extension, get_attachment_type


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class StorageService:
    """Service for managing file uploads to S3-compatible storage."""
    
    def __init__(self):
        """Initialize the S3 client."""
        if not settings.file_storage_enabled:
            raise StorageError("File storage is not configured")
        
        self.client = boto3.client(
            's3',
            endpoint_url=settings.storage_endpoint,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            region_name=settings.storage_region,
        )
        self.bucket = settings.storage_bucket
        self.public_url = settings.storage_public_url
    
    def _generate_storage_key(self, channel_id: int, filename: str) -> str:
        """Generate a unique storage key for a file.
        
        Format: channels/{channel_id}/{date}/{uuid}_{filename}
        """
        date_path = datetime.utcnow().strftime('%Y/%m')
        unique_id = uuid.uuid4().hex[:8]
        safe_filename = "".join(c for c in filename if c.isalnum() or c in '._-')
        return f"channels/{channel_id}/{date_path}/{unique_id}_{safe_filename}"
    
    def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str | None,
        channel_id: int,
    ) -> tuple[str, str, int]:
        """Upload a file to storage.
        
        Args:
            file: File-like object to upload
            filename: Original filename
            content_type: MIME type (will be guessed if not provided)
            channel_id: Channel ID for organizing files
            
        Returns:
            Tuple of (storage_key, content_type, file_size)
            
        Raises:
            StorageError: If upload fails
            ValueError: If file type is not allowed
        """
        # Validate file extension
        if not is_allowed_extension(filename):
            raise ValueError(f"File type not allowed: {filename}")
        
        # Guess content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or 'application/octet-stream'
        
        # Generate storage key
        storage_key = self._generate_storage_key(channel_id, filename)
        
        # Get file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        # Check file size
        if file_size > settings.upload_max_size_bytes:
            max_mb = settings.upload_max_size_mb
            raise ValueError(f"File size exceeds maximum allowed ({max_mb}MB)")
        
        try:
            self.client.upload_fileobj(
                file,
                self.bucket,
                storage_key,
                ExtraArgs={
                    'ContentType': content_type,
                    'ACL': 'public-read',  # Make files publicly accessible
                }
            )
        except NoCredentialsError:
            raise StorageError("Storage credentials not configured")
        except ClientError as e:
            raise StorageError(f"Failed to upload file: {e}")
        
        return storage_key, content_type, file_size
    
    def delete_file(self, storage_key: str) -> bool:
        """Delete a file from storage.
        
        Args:
            storage_key: The storage key of the file to delete
            
        Returns:
            True if deleted, False if file didn't exist
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_key)
            return True
        except ClientError:
            return False
    
    def get_public_url(self, storage_key: str) -> str:
        """Get the public URL for a file.
        
        Args:
            storage_key: The storage key of the file
            
        Returns:
            Public URL to access the file
        """
        if self.public_url:
            return f"{self.public_url.rstrip('/')}/{storage_key}"
        # Fallback to DigitalOcean Spaces URL format
        return f"https://{self.bucket}.{settings.storage_region}.digitaloceanspaces.com/{storage_key}"
    
    def file_exists(self, storage_key: str) -> bool:
        """Check if a file exists in storage.
        
        Args:
            storage_key: The storage key to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except ClientError:
            return False


# Singleton instance - lazy initialization
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get the storage service singleton.
    
    Returns:
        StorageService instance
        
    Raises:
        StorageError: If storage is not configured
    """
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
