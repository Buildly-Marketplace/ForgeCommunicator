"""
Channel management router.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.artifact import Artifact, ArtifactType
from app.models.channel import Channel
from app.models.membership import ChannelMembership, Membership, MembershipRole
from app.models.message import Message
from app.models.product import Product
from app.models.workspace import Workspace

router = APIRouter(prefix="/workspaces/{workspace_id}/channels", tags=["channels"])
templates = Jinja2Templates(directory="app/templates")


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
    
    # Get recent artifacts for channel
    result = await db.execute(
        select(Artifact)
        .where(Artifact.channel_id == channel_id)
        .order_by(Artifact.created_at.desc())
        .limit(10)
    )
    artifacts = result.scalars().all()
    
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
