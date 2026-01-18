"""
Workspace management router.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.channel import Channel
from app.models.membership import Membership, MembershipRole
from app.models.workspace import Workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
templates = Jinja2Templates(directory="app/templates")


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
    
    return templates.TemplateResponse(
        "workspaces/settings.html",
        {
            "request": request,
            "user": user,
            "workspace": workspace,
            "membership": membership,
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
