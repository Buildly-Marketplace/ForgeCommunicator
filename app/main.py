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
from fastapi.templating import Jinja2Templates

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


# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")


# Health check endpoint
@app.get("/healthz", tags=["health"])
async def healthz():
    """Health check endpoint for load balancers."""
    return {"status": "healthy"}


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
from app.routers import artifacts, auth, channels, messages, realtime, workspaces

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(channels.router)
app.include_router(messages.router)
app.include_router(artifacts.router)
app.include_router(realtime.router)


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
