"""
Django REST Framework-compatible API router for CollabHub integration.

This router exposes user profiles, workspaces, and activity data in a format
compatible with Django REST Framework, allowing CollabHub to sync data from
ForgeCommunicator.

Authentication is via Token auth (DRF style) or Bearer auth (OAuth).
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.deps import DBSession
from app.models.channel import Channel
from app.models.membership import Membership
from app.models.message import Message
from app.models.user import User
from app.models.user_session import UserSession
from app.models.workspace import Workspace
from app.services.collabhub_sync import CollabHubSyncService, CollabHubSyncError
from app.settings import settings


def require_collabhub_enabled():
    """Dependency that ensures CollabHub integration is enabled."""
    if not settings.collabhub_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CollabHub integration is not enabled on this server",
        )
    return True


router = APIRouter(
    prefix="/api",
    tags=["api"],
    dependencies=[Depends(require_collabhub_enabled)],
)

# Security schemes (DRF-compatible)
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


# Apply CollabHub guard to all routes in this router
CollabHubEnabled = Annotated[bool, Depends(require_collabhub_enabled)]


# -------------------------------------------------------------------------
# Pydantic Models (DRF-style serializers)
# -------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    """DRF-style paginated response."""
    count: int
    next: str | None = None
    previous: str | None = None
    results: list


class UserPublicProfile(BaseModel):
    """Public user profile (DRF-style serializer)."""
    id: int
    uuid: str | None = Field(None, description="CollabHub user UUID")
    email: str
    first_name: str | None = None
    last_name: str | None = None
    display_name: str
    bio: str | None = None
    title: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    status: str
    status_message: str | None = None
    
    # Social profiles
    github_url: str | None = None
    linkedin_url: str | None = None
    twitter_url: str | None = None
    website_url: str | None = None
    
    # Community stats
    community_reputation: int | None = 0
    projects_count: int | None = 0
    contributions_count: int | None = 0
    
    # Roles
    roles: dict | None = None
    
    # Timestamps
    created_at: datetime | None = None
    last_seen_at: datetime | None = None


class UserUpdateRequest(BaseModel):
    """User profile update request."""
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    bio: str | None = None
    title: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    twitter_url: str | None = None
    website_url: str | None = None


class WorkspacePublic(BaseModel):
    """Public workspace info."""
    id: int
    name: str
    slug: str
    description: str | None = None
    icon_url: str | None = None
    member_count: int = 0
    created_at: datetime | None = None


class ActivityItem(BaseModel):
    """Activity feed item."""
    id: int
    type: str  # "message", "join_workspace", "create_channel", etc.
    timestamp: datetime
    workspace_id: int | None = None
    workspace_name: str | None = None
    channel_id: int | None = None
    channel_name: str | None = None
    content: str | None = None
    actor_id: int | None = None
    actor_name: str | None = None


class SyncProfileRequest(BaseModel):
    """Request to sync profile from CollabHub."""
    direction: str = Field("pull", description="'pull' from CollabHub or 'push' to CollabHub")


class SyncProfileResponse(BaseModel):
    """Response from profile sync."""
    success: bool
    direction: str
    fields_synced: list[str] = []
    error: str | None = None


# -------------------------------------------------------------------------
# Authentication
# -------------------------------------------------------------------------

async def get_api_user(
    authorization: Annotated[str | None, Security(api_key_header)],
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(http_bearer)],
) -> User:
    """
    Authenticate API request using Token or Bearer auth.
    
    Supports:
    - Token auth: "Authorization: Token <api_key>" (DRF style)
    - Bearer auth: "Authorization: Bearer <access_token>" (OAuth style)
    """
    token = None
    
    # Extract token from authorization header
    if authorization:
        if authorization.startswith("Token "):
            token = authorization[6:]
        elif authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            # Assume it's a bare token
            token = authorization
    elif bearer:
        token = bearer.credentials
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Token"},
        )
    
    # Try to find user by session token or Labs access token
    async with async_session_maker() as db:
        from sqlalchemy.orm import selectinload
        
        user = None
        
        # First try UserSession table (multi-device support)
        result = await db.execute(
            select(UserSession)
            .where(UserSession.session_token == token)
            .options(selectinload(UserSession.user))
        )
        session = result.scalar_one_or_none()
        
        if session and session.is_valid() and session.user and session.user.is_active:
            user = session.user
        
        if not user:
            # Fallback: Try old session token on User table
            result = await db.execute(
                select(User).where(
                    User.session_token == token,
                    User.is_active == True,
                )
            )
            user = result.scalar_one_or_none()
        
        if not user:
            # Try Labs access token
            result = await db.execute(
                select(User).where(
                    User.labs_access_token == token,
                    User.is_active == True,
                )
            )
            user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token.",
                headers={"WWW-Authenticate": "Token"},
            )
        
        return user


# Dependency alias
APIUser = Annotated[User, Depends(get_api_user)]


# -------------------------------------------------------------------------
# User Endpoints (DRF-compatible)
# -------------------------------------------------------------------------

@router.get("/users/me/", response_model=UserPublicProfile)
async def get_current_user_profile(
    user: APIUser,
    db: DBSession,
):
    """
    Get current user's profile.
    
    DRF-compatible endpoint for CollabHub integration.
    """
    # Refresh user from DB
    result = await db.execute(select(User).where(User.id == user.id))
    user = result.scalar_one()
    
    # Parse display name into first/last
    parts = user.display_name.split(" ", 1) if user.display_name else [""]
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else None
    
    return UserPublicProfile(
        id=user.id,
        uuid=user.collabhub_user_uuid,
        email=user.email,
        first_name=first_name,
        last_name=last_name,
        display_name=user.display_name,
        bio=user.bio,
        title=user.title,
        phone=user.phone,
        avatar_url=user.avatar_url,
        status=user.effective_status_value,
        status_message=user.effective_status_message,
        github_url=user.github_url,
        linkedin_url=user.linkedin_url,
        twitter_url=user.twitter_url,
        website_url=user.website_url,
        community_reputation=user.community_reputation or 0,
        projects_count=user.projects_count or 0,
        contributions_count=user.contributions_count or 0,
        roles=user.collabhub_roles,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
    )


@router.patch("/users/me/", response_model=UserPublicProfile)
async def update_current_user_profile(
    user: APIUser,
    db: DBSession,
    data: UserUpdateRequest,
):
    """
    Update current user's profile.
    
    DRF-compatible PATCH endpoint.
    """
    # Refresh user from DB
    result = await db.execute(select(User).where(User.id == user.id))
    user = result.scalar_one()
    
    # Apply updates
    if data.first_name is not None or data.last_name is not None:
        first = data.first_name or (user.display_name.split(" ")[0] if user.display_name else "")
        last = data.last_name or ""
        user.display_name = f"{first} {last}".strip()
    elif data.display_name is not None:
        user.display_name = data.display_name
    
    if data.bio is not None:
        user.bio = data.bio
    if data.title is not None:
        user.title = data.title
    if data.phone is not None:
        user.phone = data.phone
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url
    if data.github_url is not None:
        user.github_url = data.github_url
    if data.linkedin_url is not None:
        user.linkedin_url = data.linkedin_url
    if data.twitter_url is not None:
        user.twitter_url = data.twitter_url
    if data.website_url is not None:
        user.website_url = data.website_url
    
    await db.commit()
    await db.refresh(user)
    
    # Return updated profile
    return await get_current_user_profile(user, db)


@router.get("/users/{user_id}/", response_model=UserPublicProfile)
async def get_user_profile(
    user_id: int,
    user: APIUser,
    db: DBSession,
):
    """
    Get a user's public profile by ID.
    
    Returns only public profile information.
    """
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    
    # Parse display name
    parts = target_user.display_name.split(" ", 1) if target_user.display_name else [""]
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else None
    
    return UserPublicProfile(
        id=target_user.id,
        uuid=target_user.collabhub_user_uuid,
        email=target_user.email,
        first_name=first_name,
        last_name=last_name,
        display_name=target_user.display_name,
        bio=target_user.bio,
        title=target_user.title,
        phone=target_user.phone,  # Include for authenticated users
        avatar_url=target_user.avatar_url,
        status=target_user.effective_status_value,
        status_message=target_user.effective_status_message,
        github_url=target_user.github_url,
        linkedin_url=target_user.linkedin_url,
        twitter_url=target_user.twitter_url,
        website_url=target_user.website_url,
        community_reputation=target_user.community_reputation or 0,
        projects_count=target_user.projects_count or 0,
        contributions_count=target_user.contributions_count or 0,
        roles=target_user.collabhub_roles,
        created_at=target_user.created_at,
        last_seen_at=target_user.last_seen_at,
    )


@router.get("/users/", response_model=PaginatedResponse)
async def list_users(
    user: APIUser,
    db: DBSession,
    search: str | None = Query(None, description="Search by name or email"),
    organization: str | None = Query(None, description="Filter by CollabHub org UUID"),
    is_dev_team: bool | None = Query(None, description="Filter dev team members"),
    is_customer: bool | None = Query(None, description="Filter customers"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List users with optional filters.
    
    DRF-compatible paginated response.
    """
    # Build query
    query = select(User).where(User.is_active == True)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_term)) | (User.display_name.ilike(search_term))
        )
    
    if organization:
        query = query.where(User.collabhub_org_uuid == organization)
    
    # Filter by roles (stored in JSON field)
    # Note: This requires JSON query support
    # For simplicity, we'll do a basic filter here
    
    # Get count first
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar()
    
    # Get paginated results
    query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Build response
    results = []
    for u in users:
        parts = u.display_name.split(" ", 1) if u.display_name else [""]
        results.append({
            "id": u.id,
            "uuid": u.collabhub_user_uuid,
            "email": u.email,
            "first_name": parts[0],
            "last_name": parts[1] if len(parts) > 1 else None,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "status": u.effective_status_value,
            "github_url": u.github_url,
            "linkedin_url": u.linkedin_url,
            "roles": u.collabhub_roles,
        })
    
    # Build pagination URLs
    next_url = None
    prev_url = None
    base_url = f"{settings.base_url}/api/users/"
    
    if offset + limit < total_count:
        next_url = f"{base_url}?offset={offset + limit}&limit={limit}"
    if offset > 0:
        prev_url = f"{base_url}?offset={max(0, offset - limit)}&limit={limit}"
    
    return PaginatedResponse(
        count=total_count,
        next=next_url,
        previous=prev_url,
        results=results,
    )


# -------------------------------------------------------------------------
# Workspace Endpoints
# -------------------------------------------------------------------------

@router.get("/workspaces/", response_model=PaginatedResponse)
async def list_workspaces(
    user: APIUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List workspaces the current user is a member of.
    """
    # Get user's workspaces through memberships
    query = (
        select(Workspace, func.count(Membership.id).label("member_count"))
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .group_by(Workspace.id)
    )
    
    # Get count
    count_query = select(func.count()).select_from(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .subquery()
    )
    count_result = await db.execute(count_query)
    total_count = count_result.scalar()
    
    # Get paginated results
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    workspaces = result.all()
    
    results = []
    for ws, member_count in workspaces:
        results.append({
            "id": ws.id,
            "name": ws.name,
            "slug": ws.slug,
            "description": ws.description,
            "icon_url": ws.icon_url,
            "member_count": member_count,
            "created_at": ws.created_at,
        })
    
    # Build pagination URLs
    next_url = None
    prev_url = None
    base_url = f"{settings.base_url}/api/workspaces/"
    
    if offset + limit < total_count:
        next_url = f"{base_url}?offset={offset + limit}&limit={limit}"
    if offset > 0:
        prev_url = f"{base_url}?offset={max(0, offset - limit)}&limit={limit}"
    
    return PaginatedResponse(
        count=total_count,
        next=next_url,
        previous=prev_url,
        results=results,
    )


@router.get("/workspaces/{workspace_id}/members/", response_model=PaginatedResponse)
async def list_workspace_members(
    workspace_id: int,
    user: APIUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List members of a workspace.
    
    User must be a member of the workspace.
    """
    # Check user is a member
    membership = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this workspace.",
        )
    
    # Get members
    query = (
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == workspace_id, User.is_active == True)
    )
    
    # Get count
    count_query = select(func.count()).select_from(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == workspace_id, User.is_active == True)
        .subquery()
    )
    count_result = await db.execute(count_query)
    total_count = count_result.scalar()
    
    # Get paginated results
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    members = result.all()
    
    results = []
    for u, role in members:
        parts = u.display_name.split(" ", 1) if u.display_name else [""]
        results.append({
            "id": u.id,
            "uuid": u.collabhub_user_uuid,
            "email": u.email,
            "first_name": parts[0],
            "last_name": parts[1] if len(parts) > 1 else None,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "status": u.effective_status_value,
            "role": role,
            "github_url": u.github_url,
            "linkedin_url": u.linkedin_url,
        })
    
    return PaginatedResponse(
        count=total_count,
        next=None,
        previous=None,
        results=results,
    )


# -------------------------------------------------------------------------
# Activity Endpoints
# -------------------------------------------------------------------------

@router.get("/activity/", response_model=PaginatedResponse)
async def get_activity_feed(
    user: APIUser,
    db: DBSession,
    workspace_id: int | None = Query(None, description="Filter by workspace"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get activity feed for the current user.
    
    Returns recent messages and events from workspaces the user is a member of.
    """
    # Get user's workspace IDs
    membership_result = await db.execute(
        select(Membership.workspace_id).where(Membership.user_id == user.id)
    )
    workspace_ids = [row[0] for row in membership_result.all()]
    
    if workspace_id:
        if workspace_id not in workspace_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this workspace.",
            )
        workspace_ids = [workspace_id]
    
    if not workspace_ids:
        return PaginatedResponse(count=0, results=[])
    
    # Get recent messages from these workspaces
    query = (
        select(Message, Channel, Workspace, User)
        .join(Channel, Message.channel_id == Channel.id)
        .join(Workspace, Channel.workspace_id == Workspace.id)
        .join(User, Message.user_id == User.id)
        .where(Workspace.id.in_(workspace_ids))
        .order_by(Message.created_at.desc())
    )
    
    # Get count
    count_query = select(func.count()).select_from(
        select(Message)
        .join(Channel, Message.channel_id == Channel.id)
        .where(Channel.workspace_id.in_(workspace_ids))
        .subquery()
    )
    count_result = await db.execute(count_query)
    total_count = count_result.scalar()
    
    # Get paginated results
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()
    
    results = []
    for msg, channel, workspace, actor in rows:
        results.append({
            "id": msg.id,
            "type": "message",
            "timestamp": msg.created_at,
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "channel_id": channel.id,
            "channel_name": channel.name,
            "content": msg.body[:200] if msg.body else None,  # Truncate for feed
            "actor_id": actor.id,
            "actor_name": actor.display_name,
        })
    
    return PaginatedResponse(
        count=total_count,
        next=None,
        previous=None,
        results=results,
    )


# -------------------------------------------------------------------------
# Sync Endpoints
# -------------------------------------------------------------------------

@router.post("/sync/profile/", response_model=SyncProfileResponse)
async def sync_profile_with_collabhub(
    user: APIUser,
    db: DBSession,
    request: SyncProfileRequest,
):
    """
    Sync user profile with CollabHub.
    
    - pull: Fetch profile data from CollabHub
    - push: Send profile data to CollabHub
    
    Requires user to have a Labs access token.
    """
    # Get fresh user from DB
    result = await db.execute(select(User).where(User.id == user.id))
    user = result.scalar_one()
    
    if not user.labs_access_token and not settings.collabhub_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No CollabHub credentials available. Please link your Labs account.",
        )
    
    try:
        sync_service = CollabHubSyncService(
            access_token=user.labs_access_token,
            api_key=settings.collabhub_api_key,
        )
        
        if request.direction == "pull":
            result = await sync_service.sync_user_profile(db, user)
            return SyncProfileResponse(
                success=result["synced"],
                direction="pull",
                fields_synced=result["fields_updated"],
                error=result.get("error"),
            )
        elif request.direction == "push":
            result = await sync_service.push_user_profile(user)
            return SyncProfileResponse(
                success=result["pushed"],
                direction="push",
                fields_synced=result["fields_pushed"],
                error=result.get("error"),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid direction. Use 'pull' or 'push'.",
            )
            
    except CollabHubSyncError as e:
        return SyncProfileResponse(
            success=False,
            direction=request.direction,
            fields_synced=[],
            error=str(e),
        )


@router.get("/stats/", response_model=dict)
async def get_user_stats(
    user: APIUser,
    db: DBSession,
):
    """
    Get statistics for the current user.
    
    Returns message counts, workspace memberships, etc.
    """
    # Get fresh user from DB
    result = await db.execute(select(User).where(User.id == user.id))
    user = result.scalar_one()
    
    # Count workspaces
    ws_count = await db.execute(
        select(func.count()).select_from(
            select(Membership).where(Membership.user_id == user.id).subquery()
        )
    )
    workspace_count = ws_count.scalar()
    
    # Count messages
    msg_count = await db.execute(
        select(func.count()).select_from(
            select(Message).where(Message.user_id == user.id).subquery()
        )
    )
    message_count = msg_count.scalar()
    
    return {
        "user_id": user.id,
        "workspaces_count": workspace_count,
        "messages_count": message_count,
        "community_reputation": user.community_reputation or 0,
        "projects_count": user.projects_count or 0,
        "contributions_count": user.contributions_count or 0,
        "is_community_member": user.is_community_member,
        "is_dev_team_member": user.is_dev_team_member,
        "is_customer": user.is_customer,
        "labs_linked": bool(user.labs_user_id),
        "collabhub_linked": user.has_collabhub_linked,
        "collabhub_synced_at": user.collabhub_synced_at,
    }
