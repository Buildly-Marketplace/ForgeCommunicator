"""
FastAPI application entry point.
"""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import close_db, init_db
from app.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s" if settings.log_format == "text" else None,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Forge Communicator...")
    await init_db()
    yield
    logger.info("Shutting down Forge Communicator...")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests for logging."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Session refresh middleware - keeps cookies in sync with sliding sessions
@app.middleware("http")
async def refresh_session_cookie(request: Request, call_next):
    """Refresh session cookie on authenticated requests to implement sliding sessions.
    
    PWA Note: Uses longer expiration (30 days for PWA vs 7 days for browser) to handle
    iOS Safari's aggressive cookie clearing in standalone mode.
    """
    response = await call_next(request)
    
    # Check if session was refreshed (marked by the dependency)
    if hasattr(request.state, 'session_refreshed') and request.state.session_refreshed:
        session_token = request.cookies.get('session_token')
        if session_token:
            # Detect PWA mode from Sec-Fetch-Dest header or display-mode
            is_pwa = request.headers.get('Sec-Fetch-Dest') == 'document' and \
                     request.headers.get('Sec-Fetch-Mode') == 'navigate' and \
                     'standalone' in request.headers.get('Sec-Fetch-Site', '')
            
            # Use longer expiration for PWA to prevent frequent logouts on iOS
            # iOS Safari in PWA mode can be aggressive about clearing cookies
            max_age = settings.session_expire_hours * 3600
            if is_pwa or request.headers.get('X-PWA-Mode') == 'standalone':
                max_age = max(max_age, 30 * 24 * 3600)  # At least 30 days for PWA
            
            response.set_cookie(
                key="session_token",
                value=session_token,
                httponly=True,
                secure=not settings.debug,
                samesite="lax",
                max_age=max_age,
                path="/",  # Explicit path ensures cookie works across all routes
            )
    
    return response


# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Use shared templates with brand context
from app.templates_config import templates


# Health check endpoint
@app.get("/healthz", tags=["health"])
@app.get("/health", tags=["health"])
async def healthz():
    """Health check endpoint for load balancers."""
    return {"status": "healthy"}


# Offline page for PWA
@app.get("/offline", response_class=HTMLResponse)
async def offline_page(request: Request):
    """Offline page for PWA."""
    return templates.TemplateResponse(
        "offline.html",
        {"request": request},
    )


# Meta endpoint for Forge Marketplace diagnostics
@app.get("/meta", tags=["meta"])
async def meta():
    """Return application metadata for marketplace diagnostics."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "build_sha": settings.build_sha,
    }


# Root redirect
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to workspaces or login."""
    from app.deps import get_current_user_optional, get_db
    
    async for db in get_db():
        user = await get_current_user_optional(
            request=request,
            db=db,
            session_token=request.cookies.get("session_token"),
        )
        if user:
            return templates.TemplateResponse(
                "redirect.html",
                {"request": request, "redirect_url": "/workspaces"},
            )
        return templates.TemplateResponse(
            "redirect.html",
            {"request": request, "redirect_url": "/auth/login"},
        )


# Import and include routers
from app.routers import admin, artifacts, auth, channels, invites, messages, notes, profile, push, realtime, sync, workspaces

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(channels.router)
app.include_router(channels.dm_router)  # DM JSON API
app.include_router(messages.router)
app.include_router(artifacts.router)
app.include_router(realtime.router)
app.include_router(profile.router)
app.include_router(push.router)
app.include_router(sync.router)
app.include_router(admin.router)
app.include_router(invites.router)
app.include_router(notes.router)

# Import and include integrations router
from app.routers import integrations
app.include_router(integrations.router)


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler."""
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<div class="text-red-500 p-4">Page not found</div>',
            status_code=404,
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": "Page not found", "status_code": 404},
        status_code=404,
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    """Custom 500 handler."""
    logger.error(f"Server error: {exc}", exc_info=True)
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<div class="text-red-500 p-4">Server error</div>',
            status_code=500,
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": "Server error", "status_code": 500},
        status_code=500,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
