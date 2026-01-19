"""
Authentication router for local auth and OAuth.
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.db import get_db
from app.deps import CurrentUser, CurrentUserOptional, DBSession
from app.models.user import AuthProvider, User
from app.services.auth_providers import get_available_providers, get_oauth_provider
from app.services.password import hash_password, validate_password, verify_password
from app.services.rate_limiter import auth_rate_limiter
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


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
