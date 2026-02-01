"""
Notes router for user notes/notebooks.

Provides endpoints for:
- Creating notes (manually or from messages/threads)
- Viewing and editing notes
- Sharing notes with users or channels
- Paginated notebook view
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.channel import Channel
from app.models.membership import ChannelMembership, Membership
from app.models.message import Message
from app.models.note import Note, NoteShare, NoteSourceType, NoteVisibility
from app.models.user import User
from app.models.workspace import Workspace
from app.templates_config import templates

router = APIRouter(prefix="/notes", tags=["notes"])


# ============================================
# Note List & Notebook View
# ============================================

@router.get("", response_class=HTMLResponse)
async def list_notes(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    workspace_id: int | None = Query(default=None),
    channel_id: int | None = Query(default=None),
    q: str | None = Query(default=None, description="Search query"),
):
    """List user's notes (notebook view)."""
    
    # Build query for user's own notes
    query = select(Note).where(
        Note.owner_id == user.id,
        Note.deleted_at == None,
    )
    
    # Filter by workspace/channel if specified
    if channel_id:
        query = query.where(Note.channel_id == channel_id)
    elif workspace_id:
        query = query.where(Note.workspace_id == workspace_id)
    
    # Search in title and content
    if q:
        search_term = f"%{q}%"
        query = query.where(
            or_(
                Note.title.ilike(search_term),
                Note.content.ilike(search_term),
            )
        )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.options(
        selectinload(Note.workspace),
        selectinload(Note.channel),
    ).order_by(Note.updated_at.desc())
    
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    result = await db.execute(query)
    notes = result.scalars().all()
    
    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page
    
    # Get shared notes (notes shared with this user)
    shared_query = (
        select(Note)
        .join(NoteShare, NoteShare.note_id == Note.id)
        .where(
            NoteShare.shared_with_user_id == user.id,
            Note.deleted_at == None,
        )
        .options(
            selectinload(Note.owner),
            selectinload(Note.workspace),
            selectinload(Note.channel),
        )
        .order_by(Note.updated_at.desc())
        .limit(10)  # Show recent shared notes
    )
    shared_result = await db.execute(shared_query)
    shared_notes = shared_result.scalars().all()
    
    # Get user's workspaces for sidebar filter
    result = await db.execute(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .order_by(Workspace.name)
    )
    workspaces = result.scalars().all()
    
    return templates.TemplateResponse(
        "profile/notes.html",
        {
            "request": request,
            "user": user,
            "notes": notes,
            "shared_notes": shared_notes,
            "workspaces": workspaces,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "search_query": q,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_note_form(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    workspace_id: int | None = Query(default=None),
    channel_id: int | None = Query(default=None),
):
    """Show form to create a new note."""
    workspace = None
    channel = None
    
    if channel_id:
        result = await db.execute(
            select(Channel)
            .where(Channel.id == channel_id)
            .options(selectinload(Channel.workspace))
        )
        channel = result.scalar_one_or_none()
        if channel:
            workspace = channel.workspace
    elif workspace_id:
        result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = result.scalar_one_or_none()
    
    return templates.TemplateResponse(
        "profile/note_edit.html",
        {
            "request": request,
            "user": user,
            "note": None,
            "workspace": workspace,
            "channel": channel,
            "is_new": True,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_note(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    title: Annotated[str, Form()] = "Untitled Note",
    content: Annotated[str, Form()] = "",
    workspace_id: Annotated[int | None, Form()] = None,
    channel_id: Annotated[int | None, Form()] = None,
):
    """Create a new note."""
    note = Note(
        owner_id=user.id,
        title=title.strip() or "Untitled Note",
        content=content,
        workspace_id=workspace_id,
        channel_id=channel_id,
        source_type=NoteSourceType.MANUAL,
        visibility=NoteVisibility.PRIVATE,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    
    if request.headers.get("HX-Request"):
        return RedirectResponse(
            url=f"/notes/{note.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    
    return RedirectResponse(
        url=f"/notes/{note.id}",
        status_code=status.HTTP_302_FOUND,
    )


# ============================================
# Note Detail & Edit
# ============================================

@router.get("/{note_id}", response_class=HTMLResponse)
async def view_note(
    request: Request,
    note_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """View a note."""
    # Get note with relationships
    result = await db.execute(
        select(Note)
        .where(Note.id == note_id, Note.deleted_at == None)
        .options(
            selectinload(Note.owner),
            selectinload(Note.workspace),
            selectinload(Note.channel),
            selectinload(Note.shares).selectinload(NoteShare.shared_with_user),
            selectinload(Note.shares).selectinload(NoteShare.shared_with_channel),
        )
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Check access
    can_view = note.owner_id == user.id
    if not can_view:
        # Check if shared with user
        for share in note.shares:
            if share.shared_with_user_id == user.id:
                can_view = True
                break
    
    if not can_view:
        raise HTTPException(status_code=403, detail="Access denied")
    
    can_edit = note.owner_id == user.id
    
    return templates.TemplateResponse(
        "profile/note_view.html",
        {
            "request": request,
            "user": user,
            "note": note,
            "can_edit": can_edit,
        },
    )


@router.get("/{note_id}/edit", response_class=HTMLResponse)
async def edit_note_form(
    request: Request,
    note_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Edit a note form."""
    result = await db.execute(
        select(Note)
        .where(Note.id == note_id, Note.deleted_at == None)
        .options(
            selectinload(Note.workspace),
            selectinload(Note.channel),
        )
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can edit")
    
    return templates.TemplateResponse(
        "profile/note_edit.html",
        {
            "request": request,
            "user": user,
            "note": note,
            "workspace": note.workspace,
            "channel": note.channel,
            "is_new": False,
        },
    )


@router.put("/{note_id}")
@router.post("/{note_id}")
async def update_note(
    request: Request,
    note_id: int,
    user: CurrentUser,
    db: DBSession,
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
):
    """Update a note."""
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.deleted_at == None)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can edit")
    
    note.title = title.strip() or "Untitled Note"
    note.content = content
    note.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse('<div class="text-green-400 text-sm">✓ Saved</div>')
    
    return RedirectResponse(
        url=f"/notes/{note_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{note_id}")
async def delete_note(
    request: Request,
    note_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Delete a note (soft delete)."""
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.deleted_at == None)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete")
    
    note.soft_delete()
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # Remove from DOM
    
    return RedirectResponse(
        url="/notes",
        status_code=status.HTTP_302_FOUND,
    )


# ============================================
# Export Note as Markdown
# ============================================

@router.get("/{note_id}/export")
async def export_note(
    note_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Export a note as a Markdown file."""
    result = await db.execute(
        select(Note)
        .where(Note.id == note_id, Note.deleted_at == None)
        .options(selectinload(Note.workspace), selectinload(Note.channel))
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Check access
    if note.owner_id != user.id:
        # TODO: Check shares
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Build markdown content
    lines = []
    lines.append(f"# {note.title}\n\n")
    
    if note.workspace or note.channel:
        lines.append("---\n")
        if note.workspace:
            lines.append(f"**Workspace:** {note.workspace.name}  \n")
        if note.channel:
            lines.append(f"**Channel:** #{note.channel.name}  \n")
        lines.append(f"**Created:** {note.created_at.strftime('%Y-%m-%d %H:%M UTC')}  \n")
        lines.append(f"**Updated:** {note.updated_at.strftime('%Y-%m-%d %H:%M UTC')}  \n")
        lines.append("---\n\n")
    
    lines.append(note.content)
    
    markdown_content = "".join(lines)
    
    # Generate filename
    safe_title = note.title.replace(" ", "-").replace("/", "-")[:30]
    filename = f"note-{safe_title}-{note.id}.md"
    
    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ============================================
# Copy from Messages/Threads
# ============================================

@router.post("/from-message/{message_id}")
async def create_note_from_message(
    request: Request,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Create a note from a single message."""
    # Get message with user and channel
    result = await db.execute(
        select(Message)
        .where(Message.id == message_id, Message.deleted_at == None)
        .options(
            selectinload(Message.user),
            selectinload(Message.channel).selectinload(Channel.workspace),
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check channel access
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == message.channel.workspace_id,
            Membership.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Format message as markdown
    author = message.user.display_name if message.user else "Unknown"
    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M") if message.created_at else ""
    
    content = f"## Message from {author}\n\n"
    content += f"*{timestamp}*\n\n"
    content += f"{message.body}\n"
    
    # Create note
    note = Note(
        owner_id=user.id,
        title=f"Note from #{message.channel.name}",
        content=content,
        workspace_id=message.channel.workspace_id,
        channel_id=message.channel_id,
        source_type=NoteSourceType.MESSAGE,
        source_message_id=message_id,
        visibility=NoteVisibility.PRIVATE,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'''
            <div class="text-green-400 text-sm">
                ✓ Saved to <a href="/notes/{note.id}" class="underline">notes</a>
            </div>
        ''')
    
    return RedirectResponse(
        url=f"/notes/{note.id}/edit",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/from-thread/{message_id}")
async def create_note_from_thread(
    request: Request,
    message_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Create a note from a thread (parent message + replies)."""
    # Get parent message
    result = await db.execute(
        select(Message)
        .where(Message.id == message_id, Message.deleted_at == None)
        .options(
            selectinload(Message.user),
            selectinload(Message.channel).selectinload(Channel.workspace),
        )
    )
    parent = result.scalar_one_or_none()
    
    if not parent:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check channel access
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == parent.channel.workspace_id,
            Membership.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get replies
    result = await db.execute(
        select(Message)
        .where(Message.parent_id == message_id, Message.deleted_at == None)
        .options(selectinload(Message.user))
        .order_by(Message.created_at.asc())
    )
    replies = result.scalars().all()
    
    # Format as markdown
    author = parent.user.display_name if parent.user else "Unknown"
    timestamp = parent.created_at.strftime("%Y-%m-%d %H:%M") if parent.created_at else ""
    
    content = f"## Thread from #{parent.channel.name}\n\n"
    content += f"### Original Message\n\n"
    content += f"**{author}** — *{timestamp}*\n\n"
    content += f"{parent.body}\n\n"
    
    if replies:
        content += "---\n\n### Replies\n\n"
        for reply in replies:
            r_author = reply.user.display_name if reply.user else "Unknown"
            r_timestamp = reply.created_at.strftime("%Y-%m-%d %H:%M") if reply.created_at else ""
            content += f"**{r_author}** — *{r_timestamp}*\n\n"
            content += f"{reply.body}\n\n"
    
    # Create note
    note = Note(
        owner_id=user.id,
        title=f"Thread from #{parent.channel.name}",
        content=content,
        workspace_id=parent.channel.workspace_id,
        channel_id=parent.channel_id,
        source_type=NoteSourceType.THREAD,
        source_message_id=message_id,
        visibility=NoteVisibility.PRIVATE,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'''
            <div class="text-green-400 text-sm">
                ✓ Thread saved to <a href="/notes/{note.id}" class="underline">notes</a>
            </div>
        ''')
    
    return RedirectResponse(
        url=f"/notes/{note.id}/edit",
        status_code=status.HTTP_302_FOUND,
    )


# ============================================
# Sharing
# ============================================

@router.post("/{note_id}/share")
async def share_note(
    request: Request,
    note_id: int,
    user: CurrentUser,
    db: DBSession,
    share_with_user_id: Annotated[int | None, Form()] = None,
    share_with_channel_id: Annotated[int | None, Form()] = None,
    message: Annotated[str | None, Form()] = None,
):
    """Share a note with a user or channel."""
    # Get note
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.deleted_at == None)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can share")
    
    if not share_with_user_id and not share_with_channel_id:
        raise HTTPException(status_code=400, detail="Must specify user or channel to share with")
    
    # Check if already shared
    existing_query = select(NoteShare).where(NoteShare.note_id == note_id)
    if share_with_user_id:
        existing_query = existing_query.where(NoteShare.shared_with_user_id == share_with_user_id)
    else:
        existing_query = existing_query.where(NoteShare.shared_with_channel_id == share_with_channel_id)
    
    result = await db.execute(existing_query)
    if result.scalar_one_or_none():
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-yellow-400 text-sm">Already shared</div>')
        raise HTTPException(status_code=400, detail="Already shared")
    
    # Create share
    share = NoteShare(
        note_id=note_id,
        shared_with_user_id=share_with_user_id,
        shared_with_channel_id=share_with_channel_id,
        shared_by_id=user.id,
        message=message.strip() if message else None,
    )
    db.add(share)
    
    # Update note visibility
    note.visibility = NoteVisibility.SHARED
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse('<div class="text-green-400 text-sm">✓ Shared</div>')
    
    return RedirectResponse(
        url=f"/notes/{note_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{note_id}/share/{share_id}")
async def unshare_note(
    request: Request,
    note_id: int,
    share_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Remove a share from a note."""
    result = await db.execute(
        select(NoteShare)
        .where(NoteShare.id == share_id, NoteShare.note_id == note_id)
        .options(selectinload(NoteShare.note))
    )
    share = result.scalar_one_or_none()
    
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    
    if share.note.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can manage shares")
    
    await db.delete(share)
    
    # Check if any shares remain
    result = await db.execute(
        select(func.count()).where(NoteShare.note_id == note_id)
    )
    remaining = result.scalar() or 0
    
    if remaining == 0:
        share.note.visibility = NoteVisibility.PRIVATE
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # Remove from DOM
    
    return RedirectResponse(
        url=f"/notes/{note_id}",
        status_code=status.HTTP_302_FOUND,
    )


# ============================================
# Navigate to Source Message
# ============================================

@router.get("/{note_id}/source")
async def go_to_source(
    request: Request,
    note_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Redirect to the original source message/thread that created this note."""
    # Get note
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.deleted_at == None)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Check access - must be owner or have note shared with them
    if note.owner_id != user.id:
        result = await db.execute(
            select(NoteShare).where(
                NoteShare.note_id == note_id,
                NoteShare.shared_with_user_id == user.id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if note has a source message
    if not note.source_message_id:
        raise HTTPException(status_code=400, detail="Note does not have a source message")
    
    # Get the source message to build redirect URL
    result = await db.execute(
        select(Message)
        .where(Message.id == note.source_message_id)
        .options(selectinload(Message.channel))
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Source message no longer exists")
    
    # Build URL to message
    # For threads, the source_message_id is the thread parent
    # For regular messages, it's the message itself
    workspace_id = message.channel.workspace_id
    channel_id = message.channel_id
    
    if note.source_type == NoteSourceType.THREAD:
        # Redirect to thread view
        redirect_url = f"/workspaces/{workspace_id}/channels/{channel_id}?thread={message.id}"
    else:
        # Redirect to channel with message highlighted
        redirect_url = f"/workspaces/{workspace_id}/channels/{channel_id}?highlight={message.id}"
    
    return RedirectResponse(
        url=redirect_url,
        status_code=status.HTTP_302_FOUND,
    )


# ============================================
# API for HTMX Updates (auto-save)
# ============================================

@router.patch("/{note_id}/content")
async def update_note_content(
    request: Request,
    note_id: int,
    user: CurrentUser,
    db: DBSession,
    content: Annotated[str, Form()],
):
    """Update just the content of a note (for auto-save)."""
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.deleted_at == None)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can edit")
    
    note.content = content
    note.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return HTMLResponse(
        f'<span class="text-gray-500 text-xs">Saved at {note.updated_at.strftime("%H:%M")}</span>'
    )


@router.patch("/{note_id}/title")
async def update_note_title(
    request: Request,
    note_id: int,
    user: CurrentUser,
    db: DBSession,
    title: Annotated[str, Form()],
):
    """Update just the title of a note."""
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.deleted_at == None)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can edit")
    
    note.title = title.strip() or "Untitled Note"
    note.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return HTMLResponse("")
