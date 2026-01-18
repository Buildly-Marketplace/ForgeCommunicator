"""
FastAPI dependencies for authentication, database, and more.
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace

# Type alias for database dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_optional(
    request: Request,
    db: DBSession,
    session_token: str | None = Cookie(default=None),
) -> User | None:
    """Get current user from session cookie (returns None if not authenticated)."""
    if not session_token:
        return None
    
    # Look up user by session token
    result = await db.execute(
        select(User).where(User.session_token == session_token)
    )
    user = result.scalar_one_or_none()
    
    if user and user.is_session_valid():
        return user
    return None


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """Get current user from session cookie (raises 401 if not authenticated)."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"HX-Redirect": "/auth/login"},
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
