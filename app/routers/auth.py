"""
Authentication router for local auth and OAuth.
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.db import get_db
from app.deps import CurrentUser, CurrentUserOptional, DBSession
from app.models.user import AuthProvider, User
from app.services.auth_providers import get_available_providers, get_oauth_provider
from app.services.password import hash_password, validate_password, verify_password
from app.services.rate_limiter import auth_rate_limiter
from app.settings import settings
from app.templates_config import templates

router = APIRouter(prefix="/auth", tags=["auth"])


def get_client_ip(request: Request) -> str:
    """Get client IP for rate limiting."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: CurrentUserOptional,
    next: str = "/workspaces",
    error: str | None = None,
):
    """Render login page."""
    if user:
        return RedirectResponse(url=next, status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "next": next,
            "error": error,
            "oauth_providers": get_available_providers(),
        },
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: DBSession,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/workspaces",
):
    """Handle local login."""
    client_ip = get_client_ip(request)
    
    # Rate limiting
    if not auth_rate_limiter.is_allowed(f"login:{client_ip}"):
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                '<div class="text-red-500">Too many login attempts. Please try again later.</div>',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts",
        )
    
    # Find user
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    user = result.scalar_one_or_none()
    
    # Verify credentials
    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                '<div class="text-red-500">Invalid email or password</div>',
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return RedirectResponse(
            url=f"/auth/login?error=Invalid+credentials&next={next}",
            status_code=status.HTTP_302_FOUND,
        )
    
    if not user.is_active:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                '<div class="text-red-500">Account is disabled</div>',
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return RedirectResponse(
            url="/auth/login?error=Account+disabled",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Create session
    session_token = user.generate_session_token()
    user.update_last_seen()
    await db.commit()
    
    # Set cookie and redirect
    redirect = RedirectResponse(url=next, status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.session_expire_hours * 3600,
    )
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = next
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=not settings.debug,
            samesite="lax",
            max_age=settings.session_expire_hours * 3600,
        )
        return response
    
    return redirect


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    user: CurrentUserOptional,
    error: str | None = None,
):
    """Render registration page."""
    if user:
        return RedirectResponse(url="/workspaces", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(
        "auth/register.html",
        {
            "request": request,
            "error": error,
            "oauth_providers": get_available_providers(),
            "registration_mode": settings.registration_mode,
        },
    )


@router.post("/register")
async def register(
    request: Request,
    db: DBSession,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
):
    """Handle local registration."""
    client_ip = get_client_ip(request)
    
    # Check registration mode
    if settings.registration_mode == "closed":
        error = "Registration is currently closed"
        if request.headers.get("HX-Request"):
            return HTMLResponse(f'<div class="text-red-500">{error}</div>', status_code=403)
        return RedirectResponse(
            url=f"/auth/register?error={error.replace(' ', '+')}",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Rate limiting
    if not auth_rate_limiter.is_allowed(f"register:{client_ip}"):
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                '<div class="text-red-500">Too many registration attempts. Please try again later.</div>',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts",
        )
    
    # Validate password
    if password != confirm_password:
        error = "Passwords do not match"
        if request.headers.get("HX-Request"):
            return HTMLResponse(f'<div class="text-red-500">{error}</div>', status_code=400)
        return RedirectResponse(
            url=f"/auth/register?error={error.replace(' ', '+')}",
            status_code=status.HTTP_302_FOUND,
        )
    
    is_valid, error = validate_password(password, settings.password_min_length)
    if not is_valid:
        if request.headers.get("HX-Request"):
            return HTMLResponse(f'<div class="text-red-500">{error}</div>', status_code=400)
        return RedirectResponse(
            url=f"/auth/register?error={error.replace(' ', '+')}",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Check if email exists
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    if result.scalar_one_or_none():
        error = "Email already registered"
        if request.headers.get("HX-Request"):
            return HTMLResponse(f'<div class="text-red-500">{error}</div>', status_code=400)
        return RedirectResponse(
            url=f"/auth/register?error={error.replace(' ', '+')}",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Create user
    user = User(
        email=email.lower(),
        display_name=display_name.strip(),
        hashed_password=hash_password(password),
        auth_provider=AuthProvider.LOCAL,
        is_platform_admin=settings.is_admin_email(email),
    )
    session_token = user.generate_session_token()
    db.add(user)
    await db.commit()
    
    # Set cookie and redirect
    redirect = RedirectResponse(url="/workspaces", status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.session_expire_hours * 3600,
    )
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = "/workspaces"
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=not settings.debug,
            samesite="lax",
            max_age=settings.session_expire_hours * 3600,
        )
        return response
    
    return redirect


@router.post("/logout")
async def logout(
    request: Request,
    db: DBSession,
    user: CurrentUserOptional,
):
    """Handle logout."""
    if user:
        user.clear_session()
        await db.commit()
    
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session_token")
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = "/auth/login"
        response.delete_cookie("session_token")
    
    return response


@router.get("/logout")
async def logout_get(
    request: Request,
    db: DBSession,
    user: CurrentUserOptional,
):
    """Handle logout via GET (for links)."""
    return await logout(request, db, user)


# OAuth routes
@router.get("/oauth/{provider}")
async def oauth_start(
    request: Request,
    provider: str,
):
    """Start OAuth flow."""
    oauth_provider = get_oauth_provider(provider)
    if not oauth_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider}' not available",
        )
    
    # Generate state token
    state = secrets.token_urlsafe(32)
    
    # Store state in cookie for verification
    params = oauth_provider.get_authorization_params(state)
    auth_url = f"{oauth_provider.authorization_url}?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )
    
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=600,  # 10 minutes
    )
    return response


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    request: Request,
    db: DBSession,
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle OAuth callback."""
    oauth_provider = get_oauth_provider(provider)
    if not oauth_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider}' not available",
        )
    
    # Verify state
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(
            url="/auth/login?error=Invalid+OAuth+state",
            status_code=status.HTTP_302_FOUND,
        )
    
    try:
        # Exchange code for tokens
        tokens = await oauth_provider.exchange_code(code)
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)  # Default 1 hour
        
        # Get user info
        user_info = await oauth_provider.get_user_info(access_token)
        
        # Check domain restriction for Google
        if provider == "google" and settings.google_allowed_domain:
            if user_info.domain != settings.google_allowed_domain:
                return RedirectResponse(
                    url=f"/auth/login?error=Email+domain+not+allowed",
                    status_code=status.HTTP_302_FOUND,
                )
        
        # Find or create user
        result = await db.execute(
            select(User).where(
                (User.email == user_info.email) |
                ((User.auth_provider == provider) & (User.provider_sub == user_info.sub))
            )
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update OAuth info
            user.provider_sub = user_info.sub
            if user_info.picture:
                user.avatar_url = user_info.picture
            # Sync display name on each login for Buildly users
            if provider == "buildly" and user_info.name:
                user.display_name = user_info.name
            # Store Buildly-specific data for cross-app identity
            if provider == "buildly" and user_info.extra:
                if user_info.extra.get("labs_user_id"):
                    user.labs_user_id = user_info.extra["labs_user_id"]
                if user_info.extra.get("organization_uuid"):
                    user.labs_org_uuid = user_info.extra["organization_uuid"]
            # Store OAuth tokens for Labs API access
            if provider == "buildly":
                from datetime import timedelta
                user.labs_access_token = access_token
                user.labs_refresh_token = refresh_token
                user.labs_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        else:
            # Create new user
            user = User(
                email=user_info.email,
                display_name=user_info.name,
                auth_provider=AuthProvider(provider),
                provider_sub=user_info.sub,
                avatar_url=user_info.picture,
            )
            # Store Buildly-specific data for new users
            if provider == "buildly" and user_info.extra:
                if user_info.extra.get("labs_user_id"):
                    user.labs_user_id = user_info.extra["labs_user_id"]
                if user_info.extra.get("organization_uuid"):
                    user.labs_org_uuid = user_info.extra["organization_uuid"]
            # Store OAuth tokens for new Buildly users
            if provider == "buildly":
                from datetime import timedelta
                user.labs_access_token = access_token
                user.labs_refresh_token = refresh_token
                user.labs_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            db.add(user)
        
        # Create session
        session_token = user.generate_session_token()
        user.update_last_seen()
        await db.commit()
        
        # Redirect with session cookie
        response = RedirectResponse(url="/workspaces", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=not settings.debug,
            samesite="lax",
            max_age=settings.session_expire_hours * 3600,
        )
        response.delete_cookie("oauth_state")
        return response
        
    except Exception as e:
        return RedirectResponse(
            url=f"/auth/login?error=OAuth+failed",
            status_code=status.HTTP_302_FOUND,
        )


# Google Workspace account linking (for calendar integration)
@router.get("/google/link")
async def google_link_start(
    request: Request,
    user: CurrentUser,
):
    """
    Start Google account linking flow.
    This allows users to link their Google Workspace account for calendar integration
    without changing their primary auth provider.
    """
    from app.services.auth_providers import GoogleOAuthProvider
    
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google integration is not enabled",
        )
    
    # Build redirect URI respecting X-Forwarded-Proto for load balancers
    proto = request.headers.get("X-Forwarded-Proto", "https" if not settings.debug else "http")
    host = request.headers.get("X-Forwarded-Host", request.url.netloc)
    base_url = f"{proto}://{host}"
    link_redirect = f"{base_url}/auth/google/link/callback"
    google_provider = GoogleOAuthProvider(include_calendar=True, redirect_uri_override=link_redirect)
    
    # Generate state token
    state = secrets.token_urlsafe(32)
    
    params = google_provider.get_authorization_params(state)
    auth_url = f"{google_provider.authorization_url}?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )
    
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="google_link_state",
        value=state,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=600,  # 10 minutes
    )
    return response


@router.get("/google/link/callback")
async def google_link_callback(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Handle Google account linking callback.
    Links Google tokens to the current user for calendar access.
    """
    from datetime import timezone
    from app.services.auth_providers import GoogleOAuthProvider
    
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google integration is not enabled",
        )
    
    # Verify state
    stored_state = request.cookies.get("google_link_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(
            url="/profile?error=Invalid+state",
            status_code=status.HTTP_302_FOUND,
        )
    
    try:
        # Build redirect URI respecting X-Forwarded-Proto for load balancers
        proto = request.headers.get("X-Forwarded-Proto", "https" if not settings.debug else "http")
        host = request.headers.get("X-Forwarded-Host", request.url.netloc)
        base_url = f"{proto}://{host}"
        link_redirect = f"{base_url}/auth/google/link/callback"
        google_provider = GoogleOAuthProvider(include_calendar=True, redirect_uri_override=link_redirect)
        
        # Exchange code for tokens
        tokens = await google_provider.exchange_code(code)
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)
        
        # Get Google user info to verify identity
        user_info = await google_provider.get_user_info(access_token)
        
        # Store tokens on user
        user.set_google_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            google_sub=user_info.sub,
        )
        
        # Immediately sync calendar status
        try:
            status_val, status_msg = await google_provider.get_current_status_from_calendar(access_token)
            user.update_calendar_status(status_val, status_msg)
        except Exception:
            pass  # Calendar sync failure shouldn't block linking
        
        await db.commit()
        
        response = RedirectResponse(
            url="/profile?success=Google+account+linked",
            status_code=status.HTTP_302_FOUND,
        )
        response.delete_cookie("google_link_state")
        return response
        
    except Exception as e:
        return RedirectResponse(
            url="/profile?error=Google+linking+failed",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/google/unlink")
async def google_unlink(
    request: Request,
    db: DBSession,
    user: CurrentUser,
):
    """Unlink Google account from user."""
    user.clear_google_tokens()
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<div class="text-green-400">Google account unlinked</div>',
            headers={"HX-Trigger": "google-unlinked"},
        )
    
    return RedirectResponse(
        url="/profile?success=Google+account+unlinked",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/google/sync-calendar")
async def google_sync_calendar(
    request: Request,
    db: DBSession,
    user: CurrentUser,
):
    """Manually sync calendar status from Google."""
    from app.services.google_calendar import sync_user_calendar_status
    
    if not user.has_google_linked:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                '<div class="text-yellow-400">Google account not linked</div>',
                status_code=400,
            )
        raise HTTPException(status_code=400, detail="Google account not linked")
    
    success = await sync_user_calendar_status(user, db)
    
    if request.headers.get("HX-Request"):
        if success:
            status_msg = user.google_calendar_message or user.effective_status_value
            return HTMLResponse(
                f'<div class="text-green-400">Calendar synced: {status_msg}</div>',
                headers={"HX-Trigger": "calendar-synced"},
            )
        else:
            return HTMLResponse(
                '<div class="text-red-400">Failed to sync calendar</div>',
                status_code=500,
            )
    
    return {"status": "synced", "calendar_status": user.google_calendar_status}
