"""
User profile router.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.deps import CurrentUser, DBSession
from app.models.user import User, UserStatus
from app.models.membership import Membership
from app.models.workspace import Workspace
from app.templates_config import templates

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_class=HTMLResponse)
async def my_profile(
    request: Request,
    user: CurrentUser,
    db: DBSession,
):
    """View and edit own profile."""
    # Get user's workspaces
    result = await db.execute(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .order_by(Workspace.name)
    )
    workspaces = result.scalars().all()
    
    return templates.TemplateResponse(
        "profile/edit.html",
        {
            "request": request,
            "user": user,
            "profile_user": user,
            "workspaces": workspaces,
            "is_own_profile": True,
            "statuses": UserStatus,
        },
    )


@router.post("", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    display_name: Annotated[str, Form()],
    bio: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    timezone: Annotated[str | None, Form()] = None,
    status: Annotated[str | None, Form()] = None,
    status_message: Annotated[str | None, Form()] = None,
):
    """Update own profile."""
    if not display_name or not display_name.strip():
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="text-red-500">Display name is required</div>', status_code=400)
        raise HTTPException(status_code=400, detail="Display name is required")
    
    user.display_name = display_name.strip()[:100]
    user.bio = bio.strip() if bio else None
    user.title = title.strip()[:100] if title else None
    user.phone = phone.strip()[:30] if phone else None
    user.timezone = timezone.strip()[:50] if timezone else "UTC"
    
    if status and status in [s.value for s in UserStatus]:
        user.status = UserStatus(status)
    
    user.status_message = status_message.strip()[:100] if status_message else None
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<div class="text-green-600 dark:text-green-400">Profile updated successfully!</div>',
            headers={"HX-Trigger": "profileUpdated"}
        )
    
    return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)


@router.post("/avatar", response_class=HTMLResponse)
async def update_avatar_url(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    avatar_url: Annotated[str | None, Form()] = None,
):
    """Update avatar URL (use external image URL)."""
    if avatar_url:
        # Basic URL validation
        avatar_url = avatar_url.strip()
        if not avatar_url.startswith(('http://', 'https://')):
            if request.headers.get("HX-Request"):
                return HTMLResponse('<div class="text-red-500">Please enter a valid URL starting with http:// or https://</div>', status_code=400)
            raise HTTPException(status_code=400, detail="Invalid URL")
        
        user.avatar_url = avatar_url[:500]
    else:
        user.avatar_url = None
    
    await db.commit()
    
    if request.headers.get("HX-Request"):
        if user.avatar_url:
            return HTMLResponse(f'''
                <div class="text-green-600 dark:text-green-400 mb-2">Avatar updated!</div>
                <img src="{user.avatar_url}" alt="Avatar" class="w-32 h-32 rounded-full object-cover">
            ''')
        else:
            return HTMLResponse(f'''
                <div class="text-green-600 dark:text-green-400 mb-2">Avatar removed!</div>
                <div class="w-32 h-32 rounded-full bg-indigo-500 flex items-center justify-center">
                    <span class="text-white text-4xl font-medium">{user.display_name[0]}</span>
                </div>
            ''')
    
    return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)


@router.get("/user/{user_id}", response_class=HTMLResponse)
async def view_user_profile(
    request: Request,
    user_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """View another user's profile."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    profile_user = result.scalar_one_or_none()
    
    if not profile_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Get shared workspaces
    result = await db.execute(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(
            Membership.user_id == profile_user.id,
            Workspace.id.in_(
                select(Membership.workspace_id).where(Membership.user_id == user.id)
            )
        )
        .order_by(Workspace.name)
    )
    shared_workspaces = result.scalars().all()
    
    return templates.TemplateResponse(
        "profile/view.html",
        {
            "request": request,
            "user": user,
            "profile_user": profile_user,
            "shared_workspaces": shared_workspaces,
            "is_own_profile": user.id == profile_user.id,
        },
    )
