"""
Workspace management router.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.channel import Channel
from app.models.membership import Membership, MembershipRole
from app.models.team_invite import TeamInvite, InviteStatus
from app.models.workspace import Workspace
from app.templates_config import templates

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def slugify(name: str) -> str:
    """Convert name to URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug[:50]


@router.get("", response_class=HTMLResponse)
async def list_workspaces(
    request: Request,
    user: CurrentUser,
    db: DBSession,
):
    """List user's workspaces."""
    # Get workspaces user is a member of
    result = await db.execute(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .options(selectinload(Workspace.memberships))
    )
    workspaces = result.scalars().all()
    
    return templates.TemplateResponse(
        "workspaces/list.html",
        {
            "request": request,
            "user": user,
            "workspaces": workspaces,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_workspace_form(
    request: Request,
    user: CurrentUser,
):
    """Render new workspace form."""
    return templates.TemplateResponse(
        "workspaces/new.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.post("/new")
async def create_workspace(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
):
    """Create a new workspace."""
    # Generate slug
    slug = slugify(name)
    
    # Check if slug exists
    result = await db.execute(
        select(Workspace).where(Workspace.slug == slug)
    )
    if result.scalar_one_or_none():
        # Add suffix to make unique
        import time
        slug = f"{slug}-{int(time.time()) % 10000}"
    
    # Create workspace
    workspace = Workspace(
        name=name.strip(),
        slug=slug,
        description=description.strip() if description else None,
    )
    workspace.generate_invite_code()
    db.add(workspace)
    await db.flush()
    
    # Add creator as owner
    membership = Membership(
        workspace_id=workspace.id,
        user_id=user.id,
        role=MembershipRole.OWNER,
    )
    db.add(membership)
    
    # Create default #general channel
    general = Channel(
        workspace_id=workspace.id,
        name="general",
        description="General discussion",
        is_default=True,
    )
    db.add(general)
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/workspaces/{workspace.id}"
        return response
    
    return RedirectResponse(
        url=f"/workspaces/{workspace.id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/join", response_class=HTMLResponse)
async def join_workspace_form(
    request: Request,
    user: CurrentUser,
    code: str | None = None,
):
    """Render join workspace form."""
    return templates.TemplateResponse(
        "workspaces/join.html",
        {
            "request": request,
            "user": user,
            "code": code,
        },
    )


@router.post("/join")
async def join_workspace(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    invite_code: Annotated[str, Form()],
):
    """Join a workspace via invite code."""
    # Find workspace by invite code
    result = await db.execute(
        select(Workspace).where(Workspace.invite_code == invite_code.upper().strip())
    )
    workspace = result.scalar_one_or_none()
    
    if not workspace or not workspace.is_invite_valid(invite_code.upper().strip()):
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                '<div class="text-red-500">Invalid or expired invite code</div>',
                status_code=400,
            )
        return RedirectResponse(
            url="/workspaces/join?error=Invalid+invite+code",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Check if already a member
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace.id,
            Membership.user_id == user.id,
        )
    )
    if result.scalar_one_or_none():
        # Already a member, just redirect
        if request.headers.get("HX-Request"):
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = f"/workspaces/{workspace.id}"
            return response
        return RedirectResponse(
            url=f"/workspaces/{workspace.id}",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Add membership
    membership = Membership(
        workspace_id=workspace.id,
        user_id=user.id,
        role=MembershipRole.MEMBER,
    )
    db.add(membership)
    await db.commit()
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/workspaces/{workspace.id}"
        return response
    
    return RedirectResponse(
        url=f"/workspaces/{workspace.id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/{workspace_id}", response_class=HTMLResponse)
async def workspace_home(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Workspace home page - redirects to first channel."""
    # Check membership
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    
    # Get workspace
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    # Get default channel
    result = await db.execute(
        select(Channel)
        .where(Channel.workspace_id == workspace_id, Channel.is_default == True)
        .limit(1)
    )
    default_channel = result.scalar_one_or_none()
    
    if not default_channel:
        # Get any channel
        result = await db.execute(
            select(Channel)
            .where(Channel.workspace_id == workspace_id, Channel.is_archived == False)
            .limit(1)
        )
        default_channel = result.scalar_one_or_none()
    
    if default_channel:
        return RedirectResponse(
            url=f"/workspaces/{workspace_id}/channels/{default_channel.id}",
            status_code=status.HTTP_302_FOUND,
        )
    
    # No channels, render workspace settings
    return templates.TemplateResponse(
        "workspaces/settings.html",
        {
            "request": request,
            "user": user,
            "workspace": workspace,
            "membership": membership,
        },
    )


@router.get("/{workspace_id}/settings", response_class=HTMLResponse)
async def workspace_settings(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Workspace settings page."""
    # Check membership
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    
    # Get workspace
    result = await db.execute(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .options(selectinload(Workspace.memberships))
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    # Get pending invites
    result = await db.execute(
        select(TeamInvite)
        .where(
            TeamInvite.workspace_id == workspace_id,
            TeamInvite.status == InviteStatus.PENDING,
        )
        .order_by(TeamInvite.created_at.desc())
    )
    pending_invites = result.scalars().all()
    
    return templates.TemplateResponse(
        "workspaces/settings.html",
        {
            "request": request,
            "user": user,
            "workspace": workspace,
            "membership": membership,
            "pending_invites": pending_invites,
        },
    )


@router.post("/{workspace_id}/invite/regenerate")
async def regenerate_invite(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Regenerate invite code (admin only)."""
    # Check admin
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership or membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    # Get workspace and regenerate code
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    workspace.generate_invite_code()
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            f'<span id="invite-code" class="font-mono bg-gray-100 px-2 py-1 rounded">{workspace.invite_code}</span>',
        )
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{workspace_id}/invites")
async def create_team_invite(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
    email: Annotated[str, Form()],
    name: Annotated[str | None, Form()] = None,
):
    """Create a new team invite (admin only)."""
    # Check admin
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership or membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    email = email.lower().strip()
    
    # Check if already a member
    from app.models.user import User
    result = await db.execute(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.workspace_id == workspace_id,
            User.email == email,
        )
    )
    if result.scalar_one_or_none():
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-red-500 text-sm">This user is already a member</div>', status_code=400)
        raise HTTPException(status_code=400, detail="User is already a member")
    
    # Check for existing pending invite
    result = await db.execute(
        select(TeamInvite).where(
            TeamInvite.workspace_id == workspace_id,
            TeamInvite.email == email,
            TeamInvite.status == InviteStatus.PENDING,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-yellow-600 text-sm">Invite already pending for this email</div>', status_code=400)
        raise HTTPException(status_code=400, detail="Invite already pending")
    
    # Create invite
    invite = TeamInvite.create(
        workspace_id=workspace_id,
        email=email,
        name=name.strip() if name else None,
        invited_by_id=user.id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    
    if request.headers.get("HX-Request"):
        # Return the new invite row HTML
        return HTMLResponse(f'''
            <li class="py-3 flex items-center justify-between" id="invite-{invite.id}">
                <div class="flex items-center">
                    <div class="w-8 h-8 rounded-full bg-yellow-100 flex items-center justify-center">
                        <svg class="w-4 h-4 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                        </svg>
                    </div>
                    <div class="ml-3">
                        <p class="text-sm font-medium text-gray-900">{invite.name or invite.email}</p>
                        <p class="text-sm text-gray-500">{invite.email}</p>
                    </div>
                </div>
                <div class="flex items-center space-x-3">
                    <span class="text-xs text-gray-400">Expires {invite.expires_at.strftime('%b %d')}</span>
                    <button onclick="copyInviteLink('{invite.token}')" class="text-xs text-indigo-600 hover:text-indigo-500">Copy Link</button>
                    <button hx-delete="/workspaces/{workspace_id}/invites/{invite.id}" hx-target="#invite-{invite.id}" hx-swap="outerHTML" class="text-xs text-red-600 hover:text-red-500">Cancel</button>
                </div>
            </li>
        ''')
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{workspace_id}/invites/{invite_id}")
async def cancel_team_invite(
    request: Request,
    workspace_id: int,
    invite_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Cancel a pending invite (admin only)."""
    # Check admin
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership or membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    # Get and cancel invite
    result = await db.execute(
        select(TeamInvite).where(
            TeamInvite.id == invite_id,
            TeamInvite.workspace_id == workspace_id,
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    
    invite.status = InviteStatus.CANCELLED
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # Remove the row
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )
