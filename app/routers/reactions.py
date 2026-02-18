"""
Reactions router for message reactions.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.reaction import MessageReaction
from app.models.message import Message
from app.models.channel import Channel
from app.models.membership import ChannelMembership
from app.templates_config import templates

router = APIRouter(prefix="/reactions", tags=["reactions"])


# Common emoji reactions
QUICK_REACTIONS = [
    ("👍", "thumbs_up"),
    ("🎉", "celebrate"),
    ("❤️", "heart"),
    ("🚀", "rocket"),
    ("👀", "eyes"),
    ("💯", "hundred"),
]


async def verify_message_access(
    message_id: int,
    user_id: int,
    db: DBSession,
) -> Message:
    """Verify user has access to the message's channel."""
    result = await db.execute(
        select(Message)
        .options(selectinload(Message.channel))
        .where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check user has access to channel
    result = await db.execute(
        select(ChannelMembership).where(
            ChannelMembership.channel_id == message.channel_id,
            ChannelMembership.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this channel")
    
    return message


@router.post("/{message_id}/toggle")
async def toggle_reaction(
    request: Request,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
    emoji: Annotated[str, Form()],
):
    """Toggle a reaction on a message (add if not exists, remove if exists)."""
    message = await verify_message_access(message_id, user.id, db)
    
    # Check if reaction already exists
    result = await db.execute(
        select(MessageReaction).where(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user.id,
            MessageReaction.emoji == emoji,
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Remove reaction
        await db.delete(existing)
        await db.commit()
    else:
        # Add reaction
        reaction = MessageReaction(
            message_id=message_id,
            user_id=user.id,
            emoji=emoji,
        )
        db.add(reaction)
        await db.commit()
    
    # Return updated reactions HTML
    return await get_reactions_html(request, message_id, user, db)


@router.post("/{message_id}/add")
async def add_reaction(
    request: Request,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
    emoji: Annotated[str, Form()],
):
    """Add a reaction to a message."""
    message = await verify_message_access(message_id, user.id, db)
    
    # Check if reaction already exists
    result = await db.execute(
        select(MessageReaction).where(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user.id,
            MessageReaction.emoji == emoji,
        )
    )
    if result.scalar_one_or_none():
        # Already exists, just return current state
        return await get_reactions_html(request, message_id, user, db)
    
    # Add reaction
    reaction = MessageReaction(
        message_id=message_id,
        user_id=user.id,
        emoji=emoji,
    )
    db.add(reaction)
    await db.commit()
    
    return await get_reactions_html(request, message_id, user, db)


@router.post("/{message_id}/remove")
async def remove_reaction(
    request: Request,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
    emoji: Annotated[str, Form()],
):
    """Remove a reaction from a message."""
    await verify_message_access(message_id, user.id, db)
    
    # Delete the reaction
    await db.execute(
        delete(MessageReaction).where(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user.id,
            MessageReaction.emoji == emoji,
        )
    )
    await db.commit()
    
    return await get_reactions_html(request, message_id, user, db)


@router.get("/{message_id}")
async def get_reactions_html(
    request: Request,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Get reactions HTML for a message."""
    # Get all reactions for this message grouped by emoji
    result = await db.execute(
        select(MessageReaction)
        .options(selectinload(MessageReaction.user))
        .where(MessageReaction.message_id == message_id)
    )
    reactions = result.scalars().all()
    
    # Group by emoji with counts and user info
    reaction_groups = {}
    for r in reactions:
        if r.emoji not in reaction_groups:
            reaction_groups[r.emoji] = {
                "emoji": r.emoji,
                "count": 0,
                "users": [],
                "user_reacted": False,
            }
        reaction_groups[r.emoji]["count"] += 1
        reaction_groups[r.emoji]["users"].append(r.user.display_name if r.user else "Unknown")
        if r.user_id == user.id:
            reaction_groups[r.emoji]["user_reacted"] = True
    
    return templates.TemplateResponse(
        "partials/message_reactions.html",
        {
            "request": request,
            "message_id": message_id,
            "reaction_groups": list(reaction_groups.values()),
            "quick_reactions": QUICK_REACTIONS,
        },
    )
