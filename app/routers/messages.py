"""
Message router for sending and managing messages.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.artifact import Artifact
from app.models.channel import Channel
from app.models.membership import ChannelMembership, Membership
from app.models.message import Message
from app.services.slash_commands import SlashCommandParser
from app.templates_config import templates

router = APIRouter(prefix="/workspaces/{workspace_id}/channels/{channel_id}/messages", tags=["messages"])


async def verify_channel_access(
    workspace_id: int,
    channel_id: int,
    user_id: int,
    db,
) -> Channel:
    """Verify user has access to channel."""
    # Check workspace membership
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a workspace member")
    
    # Get channel
    result = await db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.workspace_id == workspace_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    # Check private channel access
    if channel.is_private:
        result = await db.execute(
            select(ChannelMembership).where(
                ChannelMembership.channel_id == channel_id,
                ChannelMembership.user_id == user_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a channel member")
    
    return channel


@router.get("", response_class=HTMLResponse)
async def get_messages(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
    after: int | None = Query(default=None),
    limit: int = Query(default=50, le=100),
):
    """Get messages for channel (supports polling). Excludes thread replies."""
    channel = await verify_channel_access(workspace_id, channel_id, user.id, db)
    
    # Build query - exclude thread replies (parent_id is null for top-level messages)
    query = (
        select(Message)
        .where(
            Message.channel_id == channel_id,
            Message.deleted_at == None,
            Message.parent_id == None,  # Only top-level messages
        )
        .options(selectinload(Message.user))
    )
    
    if after:
        query = query.where(Message.id > after)
    
    query = query.order_by(Message.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    messages = list(reversed(result.scalars().all()))
    
    # Return partial for HTMX polling
    if request.headers.get("HX-Request"):
        if not messages:
            return HTMLResponse("")
        
        return templates.TemplateResponse(
            "partials/message_list.html",
            {
                "request": request,
                "messages": messages,
                "user": user,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "append": after is not None,
            },
        )
    
    return templates.TemplateResponse(
        "partials/message_list.html",
        {
            "request": request,
            "messages": messages,
            "user": user,
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "append": False,
        },
    )


@router.post("", response_class=HTMLResponse)
async def send_message(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
    body: Annotated[str, Form()],
    parent_id: int | None = Query(default=None),
):
    """Send a message to channel. If parent_id is provided, this is a thread reply."""
    channel = await verify_channel_access(workspace_id, channel_id, user.id, db)
    
    body = body.strip()
    if not body:
        if request.headers.get("HX-Request"):
            return HTMLResponse("")
        raise HTTPException(status_code=400, detail="Message body required")
    
    # Check for slash commands
    parsed = SlashCommandParser.parse(body)
    
    if parsed:
        if not parsed.is_valid:
            # Return error for invalid command
            if request.headers.get("HX-Request"):
                return HTMLResponse(
                    f'<div class="text-red-500 text-sm p-2">{parsed.error}</div>',
                    status_code=400,
                )
            raise HTTPException(status_code=400, detail=parsed.error)
        
        # Handle artifact creation commands
        artifact_type = SlashCommandParser.get_artifact_type(parsed.command)
        if artifact_type:
            from app.models.artifact import Artifact
            
            artifact = Artifact(
                workspace_id=workspace_id,
                channel_id=channel_id,
                product_id=channel.product_id,
                type=artifact_type,
                title=parsed.title,
                body=parsed.body,
                status=Artifact.get_default_status(artifact_type),
                created_by=user.id,
            )
            
            # Task-specific fields
            if parsed.command == 'task':
                if parsed.due_date:
                    artifact.due_date = parsed.due_date
                if parsed.assignee:
                    # Look up assignee by username/display_name
                    from app.models.user import User
                    result = await db.execute(
                        select(User).where(User.display_name.ilike(f"%{parsed.assignee}%"))
                    )
                    assignee = result.scalar_one_or_none()
                    if assignee:
                        artifact.assignee_user_id = assignee.id
            
            db.add(artifact)
            await db.commit()
            
            # Create a system message about the artifact
            system_message = f"Created {artifact_type.value}: **{parsed.title}**"
            message = Message(
                channel_id=channel_id,
                user_id=user.id,
                body=system_message,
            )
            db.add(message)
            await db.commit()
            await db.refresh(message)
            
            if request.headers.get("HX-Request"):
                return templates.TemplateResponse(
                    "partials/message_item.html",
                    {
                        "request": request,
                        "message": message,
                        "user": user,
                        "workspace_id": workspace_id,
                        "channel_id": channel_id,
                    },
                )
        
        # Handle channel commands
        elif parsed.command == 'join':
            # Redirect to join channel
            if request.headers.get("HX-Request"):
                response = HTMLResponse("")
                response.headers["HX-Redirect"] = f"/workspaces/{workspace_id}/channels?join={parsed.channel_name}"
                return response
        
        elif parsed.command == 'leave':
            if request.headers.get("HX-Request"):
                response = HTMLResponse("")
                response.headers["HX-Redirect"] = f"/workspaces/{workspace_id}/channels/{channel_id}/leave"
                return response
        
        elif parsed.command == 'topic':
            channel.topic = parsed.topic
            await db.commit()
            if request.headers.get("HX-Request"):
                return HTMLResponse(
                    '<div class="text-green-500 text-sm p-2">Topic updated</div>'
                )
    
    # Regular message (or thread reply)
    message = Message(
        channel_id=channel_id,
        user_id=user.id,
        body=body,
        parent_id=parent_id,
    )
    db.add(message)
    
    # Update parent's reply count if this is a thread reply
    if parent_id:
        result = await db.execute(
            select(Message).where(Message.id == parent_id)
        )
        parent_message = result.scalar_one_or_none()
        if parent_message:
            parent_message.thread_reply_count = (parent_message.thread_reply_count or 0) + 1
    
    await db.commit()
    await db.refresh(message)
    
    # Load user for template
    result = await db.execute(
        select(Message)
        .where(Message.id == message.id)
        .options(selectinload(Message.user))
    )
    message = result.scalar_one()
    
    # Send push notifications for DMs and @mentions
    try:
        from app.services.push import push_service
        from app.models.user import User
        import re
        
        # Check if this is a DM channel
        if channel.is_dm:
            # Get all members of the DM except the sender
            result = await db.execute(
                select(ChannelMembership.user_id)
                .where(
                    ChannelMembership.channel_id == channel_id,
                    ChannelMembership.user_id != user.id,
                )
            )
            recipient_ids = [row[0] for row in result.fetchall()]
            
            for recipient_id in recipient_ids:
                await push_service.notify_dm(
                    db=db,
                    recipient_user_id=recipient_id,
                    sender_name=user.display_name,
                    workspace_id=workspace_id,
                    channel_id=channel_id,
                    message_preview=body[:100],
                )
        
        # Check for @mentions in regular channels
        mention_pattern = re.compile(r'@(\w+(?:\s+\w+)?)', re.IGNORECASE)
        mentions = mention_pattern.findall(body)
        
        if mentions:
            for mention_name in mentions:
                # Find user by display name
                result = await db.execute(
                    select(User)
                    .join(Membership, Membership.user_id == User.id)
                    .where(
                        Membership.workspace_id == workspace_id,
                        User.display_name.ilike(f"%{mention_name}%"),
                        User.id != user.id,  # Don't notify yourself
                    )
                )
                mentioned_user = result.scalar_one_or_none()
                
                if mentioned_user:
                    await push_service.notify_mention(
                        db=db,
                        mentioned_user_id=mentioned_user.id,
                        sender_name=user.display_name,
                        channel_name=channel.display_name,
                        workspace_id=workspace_id,
                        channel_id=channel_id,
                        message_preview=body[:100],
                    )
    except Exception as e:
        # Don't fail the message send if push notification fails
        import logging
        logging.getLogger(__name__).error(f"Push notification error: {e}")
    
    if request.headers.get("HX-Request"):
        # Different template for thread replies vs main messages
        if parent_id:
            return templates.TemplateResponse(
                "partials/thread_reply_item.html",
                {
                    "request": request,
                    "reply": message,
                    "user": user,
                    "workspace_id": workspace_id,
                    "channel_id": channel_id,
                },
            )
        return templates.TemplateResponse(
            "partials/message_item.html",
            {
                "request": request,
                "message": message,
                "user": user,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
            },
        )
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{message_id}/edit")
async def edit_message(
    request: Request,
    workspace_id: int,
    channel_id: int,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
    body: Annotated[str, Form()],
):
    """Edit a message."""
    await verify_channel_access(workspace_id, channel_id, user.id, db)
    
    # Get message
    result = await db.execute(
        select(Message)
        .where(Message.id == message_id, Message.channel_id == channel_id)
        .options(selectinload(Message.user))
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    # Check ownership
    if message.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit other user's message")
    
    # Update message
    message.body = body.strip()
    message.edited_at = datetime.now(timezone.utc)
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/message_item.html",
            {
                "request": request,
                "message": message,
                "user": user,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
            },
        )
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{message_id}")
async def delete_message(
    request: Request,
    workspace_id: int,
    channel_id: int,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Soft delete a message."""
    await verify_channel_access(workspace_id, channel_id, user.id, db)
    
    # Get message
    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.channel_id == channel_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    # Check ownership or admin
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    
    from app.models.membership import MembershipRole
    
    if message.user_id != user.id and membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete this message")
    
    # Decrement parent's reply count if this is a thread reply
    if message.parent_id:
        result = await db.execute(
            select(Message).where(Message.id == message.parent_id)
        )
        parent = result.scalar_one_or_none()
        if parent and parent.thread_reply_count > 0:
            parent.thread_reply_count -= 1
    
    # Soft delete
    message.soft_delete()
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/{message_id}/thread", response_class=HTMLResponse)
async def get_thread(
    request: Request,
    workspace_id: int,
    channel_id: int,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Get thread content for a message."""
    await verify_channel_access(workspace_id, channel_id, user.id, db)
    
    # Get parent message
    result = await db.execute(
        select(Message)
        .where(
            Message.id == message_id,
            Message.channel_id == channel_id,
            Message.deleted_at == None,
        )
        .options(selectinload(Message.user))
    )
    parent_message = result.scalar_one_or_none()
    
    if not parent_message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    # Get replies
    result = await db.execute(
        select(Message)
        .where(
            Message.parent_id == message_id,
            Message.deleted_at == None,
        )
        .options(selectinload(Message.user))
        .order_by(Message.created_at.asc())
    )
    replies = result.scalars().all()
    
    return templates.TemplateResponse(
        "partials/thread_content.html",
        {
            "request": request,
            "parent_message": parent_message,
            "replies": replies,
            "user": user,
            "workspace_id": workspace_id,
            "channel_id": channel_id,
        },
    )


@router.get("/{message_id}", response_class=HTMLResponse)
async def get_single_message(
    request: Request,
    workspace_id: int,
    channel_id: int,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
    partial: bool = Query(default=False),
):
    """Get a single message (for refreshing after thread update)."""
    await verify_channel_access(workspace_id, channel_id, user.id, db)
    
    result = await db.execute(
        select(Message)
        .where(
            Message.id == message_id,
            Message.channel_id == channel_id,
            Message.deleted_at == None,
        )
        .options(selectinload(Message.user))
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    if partial or request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/message_item.html",
            {
                "request": request,
                "message": message,
                "user": user,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
            },
        )
    
    # Full page redirect to channel
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}",
        status_code=status.HTTP_302_FOUND,
    )
