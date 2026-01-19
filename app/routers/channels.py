"""
Channel management router.
"""

import json
import re
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.artifact import Artifact, ArtifactType
from app.models.channel import Channel
from app.models.membership import ChannelMembership, Membership, MembershipRole
from app.models.message import Message
from app.models.product import Product
from app.models.user import User
from app.models.workspace import Workspace
from app.templates_config import templates

router = APIRouter(prefix="/workspaces/{workspace_id}/channels", tags=["channels"])


async def get_workspace_and_membership(
    workspace_id: int,
    user_id: int,
    db,
) -> tuple[Workspace, Membership]:
    """Helper to get workspace and verify membership."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    
    return workspace, membership


@router.get("", response_class=HTMLResponse)
async def list_channels(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """List channels in workspace."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    # Get public channels and private channels user is a member of
    result = await db.execute(
        select(Channel)
        .where(
            Channel.workspace_id == workspace_id,
            Channel.is_archived == False,
            or_(
                Channel.is_private == False,
                and_(
                    Channel.is_private == True,
                    Channel.id.in_(
                        select(ChannelMembership.channel_id)
                        .where(ChannelMembership.user_id == user.id)
                    )
                )
            )
        )
        .order_by(Channel.name)
    )
    channels = result.scalars().all()
    
    # Get products for grouping
    result = await db.execute(
        select(Product).where(Product.workspace_id == workspace_id, Product.is_active == True)
    )
    products = result.scalars().all()
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/channel_sidebar.html",
            {
                "request": request,
                "user": user,
                "workspace": workspace,
                "channels": channels,
                "products": products,
                "current_channel_id": None,
            },
        )
    
    return templates.TemplateResponse(
        "channels/list.html",
        {
            "request": request,
            "user": user,
            "workspace": workspace,
            "channels": channels,
            "products": products,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_channel_form(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Render new channel form."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    # Get products for linking
    result = await db.execute(
        select(Product).where(Product.workspace_id == workspace_id, Product.is_active == True)
    )
    products = result.scalars().all()
    
    return templates.TemplateResponse(
        "channels/new.html",
        {
            "request": request,
            "user": user,
            "workspace": workspace,
            "products": products,
        },
    )


@router.post("/new")
async def create_channel(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    is_private: Annotated[bool, Form()] = False,
    product_id: Annotated[int | None, Form()] = None,
):
    """Create a new channel."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    # Validate name (lowercase, alphanumeric and hyphens only)
    channel_name = name.lower().strip()
    channel_name = re.sub(r'[^a-z0-9-]', '-', channel_name)
    channel_name = re.sub(r'-+', '-', channel_name).strip('-')[:80]
    
    if not channel_name:
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-red-500">Invalid channel name</div>', status_code=400)
        raise HTTPException(status_code=400, detail="Invalid channel name")
    
    # Check if channel name exists in workspace
    result = await db.execute(
        select(Channel).where(
            Channel.workspace_id == workspace_id,
            Channel.name == channel_name,
        )
    )
    if result.scalar_one_or_none():
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-red-500">Channel name already exists</div>', status_code=400)
        raise HTTPException(status_code=400, detail="Channel name already exists")
    
    # Create channel
    channel = Channel(
        workspace_id=workspace_id,
        name=channel_name,
        description=description.strip() if description else None,
        is_private=is_private,
        product_id=product_id if product_id else None,
    )
    db.add(channel)
    await db.flush()
    
    # Add creator to private channel
    if is_private:
        channel_membership = ChannelMembership(
            channel_id=channel.id,
            user_id=user.id,
        )
        db.add(channel_membership)
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/workspaces/{workspace_id}/channels/{channel.id}"
        return response
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel.id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/{channel_id}", response_class=HTMLResponse)
async def channel_view(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """View a channel with messages."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    # Get channel
    result = await db.execute(
        select(Channel)
        .where(Channel.id == channel_id, Channel.workspace_id == workspace_id)
        .options(selectinload(Channel.product))
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    # Check access to private channel
    if channel.is_private:
        result = await db.execute(
            select(ChannelMembership).where(
                ChannelMembership.channel_id == channel_id,
                ChannelMembership.user_id == user.id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this channel")
    
    # Get channels for sidebar
    result = await db.execute(
        select(Channel)
        .where(
            Channel.workspace_id == workspace_id,
            Channel.is_archived == False,
            or_(
                Channel.is_private == False,
                and_(
                    Channel.is_private == True,
                    Channel.id.in_(
                        select(ChannelMembership.channel_id)
                        .where(ChannelMembership.user_id == user.id)
                    )
                )
            )
        )
        .order_by(Channel.name)
    )
    channels = result.scalars().all()
    
    # Get products
    result = await db.execute(
        select(Product).where(Product.workspace_id == workspace_id, Product.is_active == True)
    )
    products = result.scalars().all()
    
    # Get recent messages
    result = await db.execute(
        select(Message)
        .where(Message.channel_id == channel_id, Message.deleted_at == None)
        .options(selectinload(Message.user))
        .order_by(Message.created_at.desc())
        .limit(50)
    )
    messages = list(reversed(result.scalars().all()))
    
    # Update last read message for this channel
    if messages:
        last_message_id = messages[-1].id
        # Get or create channel membership for tracking reads
        result = await db.execute(
            select(ChannelMembership).where(
                ChannelMembership.channel_id == channel_id,
                ChannelMembership.user_id == user.id,
            )
        )
        channel_membership = result.scalar_one_or_none()
        if channel_membership:
            channel_membership.last_read_message_id = last_message_id
        elif not channel.is_private:
            # For public channels, create membership record for read tracking
            channel_membership = ChannelMembership(
                channel_id=channel_id,
                user_id=user.id,
                last_read_message_id=last_message_id,
            )
            db.add(channel_membership)
        await db.commit()
    
    # Get unread counts for all channels
    # First get user's channel memberships with last_read_message_id
    result = await db.execute(
        select(ChannelMembership)
        .where(ChannelMembership.user_id == user.id)
    )
    user_channel_memberships = {cm.channel_id: cm.last_read_message_id for cm in result.scalars().all()}
    
    # Get latest message ID for each channel
    from sqlalchemy import func as sqlfunc
    result = await db.execute(
        select(Message.channel_id, sqlfunc.max(Message.id).label("max_id"))
        .where(
            Message.channel_id.in_([ch.id for ch in channels]),
            Message.deleted_at == None,
        )
        .group_by(Message.channel_id)
    )
    latest_messages = {row[0]: row[1] for row in result.fetchall()}
    
    # Calculate unread status for each channel
    unread_channels = {}
    for ch in channels:
        latest_msg_id = latest_messages.get(ch.id)
        last_read_id = user_channel_memberships.get(ch.id)
        
        if latest_msg_id:
            if last_read_id is None or latest_msg_id > last_read_id:
                unread_channels[ch.id] = True
            else:
                unread_channels[ch.id] = False
        else:
            unread_channels[ch.id] = False
    
    # Get recent artifacts for channel
    result = await db.execute(
        select(Artifact)
        .where(Artifact.channel_id == channel_id)
        .order_by(Artifact.created_at.desc())
        .limit(10)
    )
    artifacts = result.scalars().all()
    
    # Get workspace members for @mentions
    from app.models.user import User
    result = await db.execute(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(User.display_name)
    )
    members = result.scalars().all()
    
    import json
    members_json = json.dumps([
        {"id": m.id, "display_name": m.display_name, "email": m.email}
        for m in members
    ])
    
    from app.settings import settings
    
    return templates.TemplateResponse(
        "channels/view.html",
        {
            "request": request,
            "user": user,
            "workspace": workspace,
            "channel": channel,
            "channels": channels,
            "products": products,
            "messages": messages,
            "artifacts": artifacts,
            "membership": membership,
            "members_json": members_json,
            "unread_channels": unread_channels,
            "realtime_mode": settings.realtime_mode,
            "poll_interval": settings.poll_interval_seconds,
        },
    )


@router.post("/{channel_id}/topic")
async def set_topic(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
    topic: Annotated[str, Form()],
):
    """Set channel topic."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.workspace_id == workspace_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    channel.topic = topic.strip()[:250] if topic.strip() else None
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            f'<span id="channel-topic" class="text-gray-500 text-sm">{channel.topic or "No topic set"}</span>'
        )
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{channel_id}/join")
async def join_channel(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Join a channel."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.workspace_id == workspace_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    # Check if already a member
    result = await db.execute(
        select(ChannelMembership).where(
            ChannelMembership.channel_id == channel_id,
            ChannelMembership.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        channel_membership = ChannelMembership(
            channel_id=channel_id,
            user_id=user.id,
        )
        db.add(channel_membership)
        await db.commit()
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/workspaces/{workspace_id}/channels/{channel_id}"
        return response
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{channel_id}/leave")
async def leave_channel(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Leave a channel."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    result = await db.execute(
        select(ChannelMembership).where(
            ChannelMembership.channel_id == channel_id,
            ChannelMembership.user_id == user.id,
        )
    )
    channel_membership = result.scalar_one_or_none()
    if channel_membership:
        await db.delete(channel_membership)
        await db.commit()
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/workspaces/{workspace_id}"
        return response
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/dm/new")
async def create_dm_channel(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
    user_ids: Annotated[str, Form()],  # JSON array of user IDs
):
    """Create a DM channel with selected users.
    
    If a DM already exists with the exact same participants, return that channel.
    """
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    try:
        selected_user_ids = json.loads(user_ids)
        if not isinstance(selected_user_ids, list):
            raise ValueError("Invalid format")
        selected_user_ids = [int(uid) for uid in selected_user_ids]
    except (json.JSONDecodeError, ValueError, TypeError):
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-red-500">Invalid user selection</div>', status_code=400)
        raise HTTPException(status_code=400, detail="Invalid user selection")
    
    # Always include current user
    if user.id not in selected_user_ids:
        selected_user_ids.append(user.id)
    
    # Must have at least 2 participants
    if len(selected_user_ids) < 2:
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-red-500">Please select at least one user</div>', status_code=400)
        raise HTTPException(status_code=400, detail="Please select at least one user")
    
    # Verify all users are members of the workspace
    result = await db.execute(
        select(Membership.user_id)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.user_id.in_(selected_user_ids)
        )
    )
    valid_user_ids = set(row[0] for row in result.fetchall())
    
    if len(valid_user_ids) != len(selected_user_ids):
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-red-500">One or more users not in workspace</div>', status_code=400)
        raise HTTPException(status_code=400, detail="One or more users not in workspace")
    
    # Check for existing DM with same participants
    # Find DM channels where user is a member
    result = await db.execute(
        select(Channel)
        .where(
            Channel.workspace_id == workspace_id,
            Channel.is_dm == True,
            Channel.id.in_(
                select(ChannelMembership.channel_id)
                .where(ChannelMembership.user_id == user.id)
            )
        )
        .options(selectinload(Channel.memberships))
    )
    dm_channels = result.scalars().all()
    
    # Check if any existing DM has exact same participants
    for dm in dm_channels:
        dm_member_ids = set(m.user_id for m in dm.memberships)
        if dm_member_ids == set(selected_user_ids):
            # Found existing DM channel
            if request.headers.get("HX-Request"):
                response = HTMLResponse("")
                response.headers["HX-Redirect"] = f"/workspaces/{workspace_id}/channels/{dm.id}"
                return response
            return RedirectResponse(
                url=f"/workspaces/{workspace_id}/channels/{dm.id}",
                status_code=status.HTTP_302_FOUND,
            )
    
    # Get user display names for the channel name
    result = await db.execute(
        select(User)
        .where(User.id.in_(selected_user_ids), User.id != user.id)
    )
    other_users = result.scalars().all()
    
    if len(other_users) == 1:
        channel_name = other_users[0].display_name
    else:
        names = sorted([u.display_name for u in other_users])
        if len(names) > 3:
            channel_name = f"{', '.join(names[:2])}, +{len(names) - 2} more"
        else:
            channel_name = ", ".join(names)
    
    # Create new DM channel
    channel = Channel(
        workspace_id=workspace_id,
        name=channel_name,
        is_private=True,
        is_dm=True,
    )
    db.add(channel)
    await db.flush()
    
    # Add all participants as members
    for uid in selected_user_ids:
        channel_membership = ChannelMembership(
            channel_id=channel.id,
            user_id=uid,
        )
        db.add(channel_membership)
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/workspaces/{workspace_id}/channels/{channel.id}"
        return response
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel.id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{channel_id}")
async def delete_channel(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Delete a channel (admin only). Cannot delete the last channel."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    # Only admins/owners can delete channels
    if membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    # Get the channel
    result = await db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.workspace_id == workspace_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    # Don't delete if it's the only non-archived channel
    result = await db.execute(
        select(Channel).where(
            Channel.workspace_id == workspace_id,
            Channel.is_archived == False,
            Channel.id != channel_id,
        )
    )
    other_channels = result.scalars().all()
    if not other_channels:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                '<div class="text-red-500 text-sm">Cannot delete the last channel</div>',
                status_code=400,
            )
        raise HTTPException(status_code=400, detail="Cannot delete the last channel")
    
    # Delete the channel (messages cascade delete)
    await db.delete(channel)
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # Remove the row
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{channel_id}/archive")
async def archive_channel(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Archive a channel (admin only)."""
    workspace, membership = await get_workspace_and_membership(workspace_id, user.id, db)
    
    if membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    result = await db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.workspace_id == workspace_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    channel.is_archived = True
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )