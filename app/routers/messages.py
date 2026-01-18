"""
Message router for sending and managing messages.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.artifact import Artifact
from app.models.channel import Channel
from app.models.membership import ChannelMembership, Membership
from app.models.message import Message
from app.services.slash_commands import SlashCommandParser

router = APIRouter(prefix="/workspaces/{workspace_id}/channels/{channel_id}/messages", tags=["messages"])
templates = Jinja2Templates(directory="app/templates")


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
    """Get messages for channel (supports polling)."""
    channel = await verify_channel_access(workspace_id, channel_id, user.id, db)
    
    # Build query
    query = (
        select(Message)
        .where(Message.channel_id == channel_id, Message.deleted_at == None)
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
):
    """Send a message to channel."""
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
    
    # Regular message
    message = Message(
        channel_id=channel_id,
        user_id=user.id,
        body=body,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    # Load user for template
    result = await db.execute(
        select(Message)
        .where(Message.id == message.id)
        .options(selectinload(Message.user))
    )
    message = result.scalar_one()
    
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
    
    # Soft delete
    message.soft_delete()
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}",
        status_code=status.HTTP_302_FOUND,
    )
