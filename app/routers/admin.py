"""
Platform admin routes for user management and configuration.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from app.db import DBSession
from app.deps import CurrentUser
from app.models.user import User
from app.models.workspace import Workspace
from app.models.membership import Membership
from app.settings import settings
from app.templates_config import templates


router = APIRouter(prefix="/admin", tags=["admin"])


async def require_platform_admin(user: User) -> None:
    """Require user to be a platform admin."""
    if not user.is_platform_admin and not settings.is_admin_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: CurrentUser,
    db: DBSession,
):
    """Admin dashboard overview."""
    await require_platform_admin(user)
    
    # Get counts
    user_count = await db.scalar(select(func.count()).select_from(User))
    workspace_count = await db.scalar(select(func.count()).select_from(Workspace))
    
    # Recent users
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(10)
    )
    recent_users = result.scalars().all()
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": user,
            "user_count": user_count,
            "workspace_count": workspace_count,
            "recent_users": recent_users,
            "registration_mode": settings.registration_mode,
        },
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    page: int = Query(default=1, ge=1),
    search: str | None = None,
):
    """List all users with pagination and search."""
    await require_platform_admin(user)
    
    per_page = 25
    offset = (page - 1) * per_page
    
    # Build query
    query = select(User)
    count_query = select(func.count()).select_from(User)
    
    if search:
        search_filter = User.email.ilike(f"%{search}%") | User.display_name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # Get total count
    total = await db.scalar(count_query) or 0
    total_pages = (total + per_page - 1) // per_page
    
    # Get users
    result = await db.execute(
        query.order_by(User.created_at.desc()).offset(offset).limit(per_page)
    )
    users = result.scalars().all()
    
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "search": search or "",
        },
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    user_id: int,
):
    """View/edit a specific user."""
    await require_platform_admin(user)
    
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's workspaces
    result = await db.execute(
        select(Membership).where(Membership.user_id == user_id)
    )
    memberships = result.scalars().all()
    
    return templates.TemplateResponse(
        "admin/user_detail.html",
        {
            "request": request,
            "user": user,
            "target_user": target_user,
            "memberships": memberships,
        },
    )


@router.post("/users/{user_id}/toggle-active")
async def toggle_user_active(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    user_id: int,
):
    """Toggle user active status."""
    await require_platform_admin(user)
    
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Can't deactivate yourself
    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    target_user.is_active = not target_user.is_active
    await db.commit()
    
    if request.headers.get("HX-Request"):
        status_text = "Active" if target_user.is_active else "Inactive"
        status_class = "bg-green-100 text-green-800" if target_user.is_active else "bg-red-100 text-red-800"
        return HTMLResponse(
            f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {status_class}">{status_text}</span>'
        )
    
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/users/{user_id}/toggle-admin")
async def toggle_user_admin(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    user_id: int,
):
    """Toggle user platform admin status."""
    await require_platform_admin(user)
    
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Can't remove your own admin
    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin status")
    
    target_user.is_platform_admin = not target_user.is_platform_admin
    await db.commit()
    
    if request.headers.get("HX-Request"):
        if target_user.is_platform_admin:
            return HTMLResponse(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">Admin</span>'
            )
        return HTMLResponse('<span class="text-gray-400 text-sm">—</span>')
    
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.get("/workspaces", response_class=HTMLResponse)
async def admin_workspaces(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    page: int = Query(default=1, ge=1),
):
    """List all workspaces."""
    await require_platform_admin(user)
    
    per_page = 25
    offset = (page - 1) * per_page
    
    total = await db.scalar(select(func.count()).select_from(Workspace)) or 0
    total_pages = (total + per_page - 1) // per_page
    
    result = await db.execute(
        select(Workspace).order_by(Workspace.created_at.desc()).offset(offset).limit(per_page)
    )
    workspaces = result.scalars().all()
    
    return templates.TemplateResponse(
        "admin/workspaces.html",
        {
            "request": request,
            "user": user,
            "workspaces": workspaces,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    user: CurrentUser,
):
    """View platform settings."""
    await require_platform_admin(user)
    
    return templates.TemplateResponse(
        "admin/settings.html",
        {
            "request": request,
            "user": user,
            "settings": {
                "registration_mode": settings.registration_mode,
                "platform_admin_emails": settings.platform_admin_emails,
                "brand_name": settings.brand_name,
                "brand_company": settings.brand_company,
                "buildly_oauth_enabled": settings.buildly_oauth_enabled,
                "google_oauth_enabled": settings.google_oauth_enabled,
                "push_enabled": settings.push_enabled,
            },
        },
    )
