"""
Google Calendar sync service.

Syncs user status from Google Calendar to show:
- "In a meeting" when user has an active calendar event
- "On vacation" when user has vacation/OOO entries
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.auth_providers import GoogleOAuthProvider
from app.settings import settings

logger = logging.getLogger(__name__)


async def refresh_google_token_if_needed(user: User, db: AsyncSession) -> str | None:
    """
    Refresh Google access token if expired.
    
    Args:
        user: User with Google tokens
        db: Database session for saving refreshed tokens
        
    Returns:
        Valid access token, or None if refresh failed
    """
    if not user.google_refresh_token:
        return None
    
    # If token is still valid, return it
    if not user.google_token_expired and user.google_access_token:
        return user.google_access_token
    
    # Need to refresh
    try:
        google_provider = GoogleOAuthProvider(include_calendar=True)
        tokens = await google_provider.refresh_access_token(user.google_refresh_token)
        
        access_token = tokens["access_token"]
        expires_in = tokens.get("expires_in", 3600)
        refresh_token = tokens.get("refresh_token")  # May not be returned
        
        user.set_google_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
        await db.commit()
        
        return access_token
        
    except Exception as e:
        logger.warning(f"Failed to refresh Google token for user {user.id}: {e}")
        return None


async def sync_user_calendar_status(user: User, db: AsyncSession) -> bool:
    """
    Sync calendar status for a single user.
    
    Args:
        user: User with Google linked
        db: Database session
        
    Returns:
        True if sync was successful
    """
    if not user.has_google_linked:
        return False
    
    # Get valid access token
    access_token = await refresh_google_token_if_needed(user, db)
    if not access_token:
        logger.warning(f"No valid Google token for user {user.id}")
        return False
    
    try:
        google_provider = GoogleOAuthProvider(include_calendar=True)
        status_val, status_msg = await google_provider.get_current_status_from_calendar(access_token)
        
        user.update_calendar_status(status_val, status_msg)
        await db.commit()
        
        logger.info(f"Synced calendar status for user {user.id}: {status_val}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to sync calendar for user {user.id}: {e}")
        return False


async def sync_all_calendar_statuses(db: AsyncSession) -> tuple[int, int]:
    """
    Sync calendar status for all users with Google linked.
    
    This should be called periodically (e.g., every 5 minutes) to keep
    statuses up to date.
    
    Args:
        db: Database session
        
    Returns:
        Tuple of (success_count, failure_count)
    """
    if not settings.google_oauth_enabled:
        return (0, 0)
    
    # Get all users with Google linked (have refresh token)
    result = await db.execute(
        select(User).where(
            User.google_refresh_token.isnot(None),
            User.is_active == True,
        )
    )
    users = result.scalars().all()
    
    success = 0
    failed = 0
    
    for user in users:
        if await sync_user_calendar_status(user, db):
            success += 1
        else:
            failed += 1
    
    logger.info(f"Calendar sync complete: {success} success, {failed} failed")
    return (success, failed)


async def get_calendar_status_for_user(user: User, db: AsyncSession) -> tuple[str, str | None]:
    """
    Get the current calendar-based status for a user.
    
    This is a convenience function that syncs if needed and returns the status.
    
    Args:
        user: User to get status for
        db: Database session
        
    Returns:
        Tuple of (status, status_message)
    """
    if not user.has_google_linked:
        return user.get_effective_status()
    
    # Check if we need to sync (older than 5 minutes)
    needs_sync = True
    if user.google_calendar_synced_at:
        sync_age = datetime.now(timezone.utc) - user.google_calendar_synced_at
        needs_sync = sync_age.total_seconds() > 300  # 5 minutes
    
    if needs_sync:
        await sync_user_calendar_status(user, db)
    
    return user.get_effective_status()
