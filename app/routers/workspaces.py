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
from app.models.artifact import Artifact
from app.models.channel import Channel
from app.models.membership import Membership, MembershipRole
from app.models.product import Product
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
    
    # Get channels for management
    result = await db.execute(
        select(Channel)
        .where(
            Channel.workspace_id == workspace_id,
            Channel.is_archived == False,
        )
        .options(selectinload(Channel.product))
        .order_by(Channel.name)
    )
    channels = result.scalars().all()
    
    # Get products for management
    result = await db.execute(
        select(Product)
        .where(Product.workspace_id == workspace_id)
        .order_by(Product.name)
    )
    products = result.scalars().all()
    
    # Get artifacts (docs) for management
    result = await db.execute(
        select(Artifact)
        .where(Artifact.workspace_id == workspace_id)
        .options(selectinload(Artifact.product))
        .order_by(Artifact.title)
    )
    artifacts = result.scalars().all()
    
    return templates.TemplateResponse(
        "workspaces/settings.html",
        {
            "request": request,
            "user": user,
            "workspace": workspace,
            "membership": membership,
            "pending_invites": pending_invites,
            "channels": channels,
            "products": products,
            "artifacts": artifacts,
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


@router.delete("/{workspace_id}/products/{product_id}")
async def delete_product(
    request: Request,
    workspace_id: int,
    product_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Delete a product and its associated channels/artifacts (admin only)."""
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
    
    # Get and delete product
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.workspace_id == workspace_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    # Delete associated artifacts first
    await db.execute(
        Artifact.__table__.delete().where(Artifact.product_id == product_id)
    )
    
    # Delete associated channels
    await db.execute(
        Channel.__table__.delete().where(Channel.product_id == product_id)
    )
    
    # Delete product
    await db.delete(product)
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # Remove the row
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{workspace_id}/artifacts/{artifact_id}")
async def delete_artifact(
    request: Request,
    workspace_id: int,
    artifact_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Delete an artifact/document (admin only)."""
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
    
    # Get and delete artifact
    result = await db.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.workspace_id == workspace_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    
    await db.delete(artifact)
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # Remove the row
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{workspace_id}/products")
async def delete_all_products(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Delete all products in workspace (admin only) - bulk cleanup."""
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
    
    # Delete all artifacts in workspace
    await db.execute(
        Artifact.__table__.delete().where(Artifact.workspace_id == workspace_id)
    )
    
    # Delete all product-linked channels
    await db.execute(
        Channel.__table__.delete().where(
            Channel.workspace_id == workspace_id,
            Channel.product_id.isnot(None)
        )
    )
    
    # Delete all products
    await db.execute(
        Product.__table__.delete().where(Product.workspace_id == workspace_id)
    )
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse('<div class="text-green-400">All products deleted successfully. Refresh the page to see changes.</div>')
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.put("/{workspace_id}")
async def update_workspace(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
):
    """Update workspace name and description (owner only)."""
    # Check owner
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership or membership.role != MembershipRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")
    
    # Get workspace
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    # Update workspace
    workspace.name = name.strip()
    workspace.slug = slugify(name)
    workspace.description = description.strip() if description else None
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'''
            <div class="text-green-600 text-sm mb-2">Workspace updated successfully!</div>
            <script>
                setTimeout(() => {{
                    document.querySelector('.text-green-600')?.remove();
                }}, 3000);
            </script>
        ''')
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{workspace_id}")
async def delete_workspace(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Delete workspace (owner only). This deletes EVERYTHING in the workspace."""
    # Check owner
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership or membership.role != MembershipRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")
    
    # Get workspace
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    # Delete all related data (in order due to foreign keys)
    # Artifacts
    await db.execute(
        Artifact.__table__.delete().where(Artifact.workspace_id == workspace_id)
    )
    
    # Team invites
    await db.execute(
        TeamInvite.__table__.delete().where(TeamInvite.workspace_id == workspace_id)
    )
    
    # Channels (this will cascade delete messages)
    await db.execute(
        Channel.__table__.delete().where(Channel.workspace_id == workspace_id)
    )
    
    # Products
    await db.execute(
        Product.__table__.delete().where(Product.workspace_id == workspace_id)
    )
    
    # Memberships
    await db.execute(
        Membership.__table__.delete().where(Membership.workspace_id == workspace_id)
    )
    
    # Finally delete the workspace
    await db.delete(workspace)
    await db.commit()
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = "/workspaces"
        return response
    
    return RedirectResponse(
        url="/workspaces",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{workspace_id}/labs/api-token")
async def configure_labs_api_token(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
    api_token: Annotated[str, Form()],
    org_uuid: Annotated[str | None, Form()] = None,
):
    """Configure Labs API token for workspace (admin only)."""
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
    
    # Get workspace
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    # Validate token by making a test API call
    try:
        from app.services.labs_sync import LabsSyncService
        service = LabsSyncService(api_key=api_token.strip())
        me = await service.get_me()
        labs_email = me.get("data", {}).get("email", "unknown")
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HTMLResponse(f'<div class="text-red-600 text-sm">❌ Invalid API token: {str(e)}</div>')
        raise HTTPException(status_code=400, detail=f"Invalid API token: {str(e)}")
    
    # Update workspace
    workspace.labs_api_token = api_token.strip()
    workspace.labs_connected_by_id = user.id
    if org_uuid:
        workspace.buildly_org_uuid = org_uuid.strip()
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'''
            <div class="text-green-600 text-sm">✓ Labs API token configured successfully! Connected as {labs_email}</div>
            <script>setTimeout(() => location.reload(), 1500);</script>
        ''')
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("/{workspace_id}/labs/disconnect")
async def disconnect_labs(
    request: Request,
    workspace_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Disconnect Labs integration from workspace (admin only)."""
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
    
    # Get workspace
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    # Clear Labs integration
    workspace.labs_api_token = None
    workspace.labs_access_token = None
    workspace.labs_refresh_token = None
    workspace.labs_token_expires_at = None
    workspace.labs_connected_by_id = None
    workspace.buildly_org_uuid = None
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse('''
            <div class="text-green-600 text-sm">✓ Labs integration disconnected</div>
            <script>setTimeout(() => location.reload(), 1500);</script>
        ''')
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/settings",
        status_code=status.HTTP_302_FOUND,
    )
