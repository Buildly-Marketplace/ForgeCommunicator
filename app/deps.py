"""
FastAPI dependencies for authentication, database, and more.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace
from app.settings import settings

# Type alias for database dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_optional(
    request: Request,
    db: DBSession,
    session_token: str | None = Cookie(default=None),
) -> User | None:
    """Get current user from session cookie (returns None if not authenticated).
    
    For OAuth users with valid refresh tokens:
    - Session is automatically extended when less than 25% time remains
    - Session can be restored even if recently expired (within 1 hour grace period)
    """
    if not session_token:
        return None
    
    # Look up user by session token
    result = await db.execute(
        select(User).where(User.session_token == session_token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    # Check if session is valid
    session_valid = user.is_session_valid()
    
    # For OAuth users, try to restore recently expired sessions (1 hour grace period)
    if not session_valid and user.session_expires_at:
        grace_period = timedelta(hours=1)
        time_since_expiry = datetime.now(timezone.utc) - user.session_expires_at
        
        # Check if within grace period and user has OAuth refresh capability
        if time_since_expiry <= grace_period:
            can_auto_refresh = (
                (user.auth_provider.value == "google" and user.google_refresh_token) or
                (user.auth_provider.value == "buildly" and user.labs_refresh_token)
            )
            if can_auto_refresh:
                # Restore session for OAuth users with valid refresh tokens
                user.session_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_expire_hours)
                user.update_last_seen()
                await db.commit()
                request.state.session_refreshed = True
                session_valid = True
    
    if session_valid:
        # Refresh session expiry if less than 25% of the time remains (sliding session)
        # This extends active users' sessions without updating on every request
        refresh_threshold = timedelta(hours=settings.session_expire_hours * 0.25)
        if user.session_expires_at and (user.session_expires_at - datetime.now(timezone.utc)) < refresh_threshold:
            user.session_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_expire_hours)
            user.update_last_seen()
            await db.commit()
            # Mark that session was refreshed so middleware can update the cookie
            request.state.session_refreshed = True
        return user
    
    return None


async def get_current_user(
    request: Request,
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """Get current user from session cookie (raises 401 if not authenticated).
    
    For browser requests, this will trigger a redirect to /auth/login via the
    401 exception handler in main.py.
    """
    if not user:
        # Check if this is an HTMX request
        if request.headers.get("HX-Request"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"HX-Redirect": "/auth/login"},
            )
        # For regular browser requests, just raise 401 - the exception handler will redirect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


# Type alias for authenticated user dependency
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]


async def get_workspace_membership(
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
) -> Membership:
    """Verify user is a member of the workspace and return membership."""
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace",
        )
    return membership


async def require_workspace_admin(
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
) -> Membership:
    """Require user to be admin or owner of the workspace."""
    membership = await get_workspace_membership(workspace_id, user, db)
    
    if membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return membership


async def get_workspace_by_id(
    workspace_id: int,
    db: DBSession,
) -> Workspace:
    """Get workspace by ID."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return workspace


def get_request_id(request: Request) -> str:
    """Get or generate request ID for logging."""
    return request.headers.get("X-Request-ID", request.state.request_id)
