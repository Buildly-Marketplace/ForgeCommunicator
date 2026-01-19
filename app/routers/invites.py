"""
Invite acceptance router.

Handles accepting team invites via token link.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.deps import CurrentUser, DBSession, get_current_user_optional
from app.models.membership import Membership, MembershipRole
from app.models.team_invite import TeamInvite, InviteStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.templates_config import templates

router = APIRouter(prefix="/invites", tags=["invites"])

# Optional user dependency for viewing invites
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


@router.get("/{token}", response_class=HTMLResponse)
async def view_invite(
    request: Request,
    token: str,
    db: DBSession,
    user: OptionalUser,
):
    """View an invite and optionally accept it."""
    # Find the invite
    result = await db.execute(
        select(TeamInvite)
        .where(TeamInvite.token == token)
    )
    invite = result.scalar_one_or_none()
    
    if not invite:
        return templates.TemplateResponse(
            "invites/invalid.html",
            {"request": request, "message": "This invite link is invalid."},
            status_code=404,
        )
    
    if invite.status == InviteStatus.ACCEPTED:
        return templates.TemplateResponse(
            "invites/invalid.html",
            {"request": request, "message": "This invite has already been accepted."},
        )
    
    if invite.status == InviteStatus.CANCELLED:
        return templates.TemplateResponse(
            "invites/invalid.html",
            {"request": request, "message": "This invite has been cancelled."},
        )
    
    if datetime.now(timezone.utc) > invite.expires_at:
        invite.status = InviteStatus.EXPIRED
        await db.commit()
        return templates.TemplateResponse(
            "invites/invalid.html",
            {"request": request, "message": "This invite has expired."},
        )
    
    # Get workspace
    result = await db.execute(
        select(Workspace).where(Workspace.id == invite.workspace_id)
    )
    workspace = result.scalar_one_or_none()
    
    # If user is logged in and their email matches, auto-redirect to accept
    if user and user.email.lower() == invite.email.lower():
        return RedirectResponse(
            url=f"/invites/{token}/accept",
            status_code=status.HTTP_302_FOUND,
        )
    
    return templates.TemplateResponse(
        "invites/view.html",
        {
            "request": request,
            "invite": invite,
            "workspace": workspace,
            "user": user,
        },
    )


@router.get("/{token}/accept")
@router.post("/{token}/accept")
async def accept_invite(
    request: Request,
    token: str,
    user: CurrentUser,
    db: DBSession,
):
    """Accept an invite and join the workspace."""
    # Find the invite
    result = await db.execute(
        select(TeamInvite)
        .where(TeamInvite.token == token)
    )
    invite = result.scalar_one_or_none()
    
    if not invite or not invite.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite",
        )
    
    # Check if user is already a member
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == invite.workspace_id,
            Membership.user_id == user.id,
        )
    )
    existing_membership = result.scalar_one_or_none()
    
    if existing_membership:
        # Already a member, just redirect
        return RedirectResponse(
            url=f"/workspaces/{invite.workspace_id}",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Map invite role to membership role
    role_map = {
        "owner": MembershipRole.OWNER,
        "admin": MembershipRole.ADMIN,
        "member": MembershipRole.MEMBER,
        "guest": MembershipRole.GUEST,
    }
    membership_role = role_map.get(invite.role, MembershipRole.MEMBER)
    
    # Create membership
    membership = Membership(
        workspace_id=invite.workspace_id,
        user_id=user.id,
        role=membership_role,
    )
    db.add(membership)
    
    # Update invite status
    invite.status = InviteStatus.ACCEPTED
    invite.accepted_at = datetime.now(timezone.utc)
    invite.accepted_by_id = user.id
    
    await db.commit()
    
    return RedirectResponse(
        url=f"/workspaces/{invite.workspace_id}",
        status_code=status.HTTP_302_FOUND,
    )
