"""
Labs API sync router.

Endpoints for syncing data from Buildly Labs.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services.labs_sync import LabsSyncService, sync_all_from_labs
from app.settings import settings


router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status")
async def sync_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Check if Labs sync is configured and available."""
    # Check if user has Labs OAuth token
    has_user_token = bool(current_user.labs_access_token)
    has_api_key = bool(settings.labs_api_key)
    
    if has_user_token or has_api_key:
        try:
            # Prefer user's OAuth token over API key
            token = current_user.labs_access_token if has_user_token else settings.labs_api_key
            service = LabsSyncService(access_token=token)
            me = await service.get_me()
            return {
                "configured": True,
                "connected": True,
                "auth_method": "oauth" if has_user_token else "api_key",
                "labs_user": me.get("data", {}).get("email", "unknown"),
            }
        except Exception as e:
            return {
                "configured": True,
                "connected": False,
                "error": str(e),
            }
    
    return {
        "configured": False,
        "connected": False,
        "message": "Sign in with Buildly Labs to enable sync",
    }


@router.post("/products")
async def sync_products(
    request: Request,
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync products from Labs API to current workspace."""
    
    # Get auth token - prefer user's OAuth token
    token = current_user.labs_access_token or settings.labs_api_key
    if not token:
        raise HTTPException(status_code=400, detail="Sign in with Buildly Labs to enable sync")
    
    try:
        service = LabsSyncService(access_token=token)
        stats = await service.sync_products(db, workspace_id)
        return {
            "success": True,
            "message": f"Synced products: {stats['created']} created, {stats['updated']} updated",
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/backlog")
async def sync_backlog(
    request: Request,
    workspace_id: int,
    product_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync backlog items from Labs API to artifacts."""
    
    # Get auth token - prefer user's OAuth token
    token = current_user.labs_access_token or settings.labs_api_key
    if not token:
        raise HTTPException(status_code=400, detail="Sign in with Buildly Labs to enable sync")
    
    try:
        service = LabsSyncService(access_token=token)
        stats = await service.sync_backlog(
            db,
            workspace_id,
            product_id=product_id,
            user_id=current_user.id,
        )
        return {
            "success": True,
            "message": f"Synced backlog: {stats['created']} created, {stats['updated']} updated",
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/all")
async def sync_all(
    request: Request,
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync all data from Labs API (products and backlog)."""
    is_htmx = request.headers.get("HX-Request") == "true"
    
    # Get auth token - prefer user's OAuth token
    token = current_user.labs_access_token or settings.labs_api_key
    if not token:
        if is_htmx:
            return HTMLResponse(
                '<div class="text-yellow-600 p-2 bg-yellow-50 rounded">⚠️ Sign in with Buildly Labs to enable sync</div>'
            )
        raise HTTPException(status_code=400, detail="Sign in with Buildly Labs to enable sync")
    
    try:
        results = await sync_all_from_labs(
            db,
            workspace_id,
            user_id=current_user.id,
            access_token=token,
        )
        
        total_created = sum(r.get("created", 0) for r in results.values())
        total_updated = sum(r.get("updated", 0) for r in results.values())
        
        if is_htmx:
            return HTMLResponse(
                f'<div class="text-green-600 p-2 bg-green-50 rounded">✓ Sync complete: {total_created} created, {total_updated} updated</div>'
            )
        
        return {
            "success": True,
            "message": f"Full sync complete: {total_created} created, {total_updated} updated",
            "results": results,
        }
    except Exception as e:
        if is_htmx:
            return HTMLResponse(
                f'<div class="text-red-600 p-2 bg-red-50 rounded">❌ Sync failed: {str(e)}</div>'
            )
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/labs/products")
async def list_labs_products(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """List products directly from Labs API (preview before sync)."""
    if not settings.labs_api_key:
        raise HTTPException(status_code=400, detail="LABS_API_KEY not configured")
    
    try:
        service = LabsSyncService()
        return await service.get_products(limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {str(e)}")


@router.get("/labs/backlog")
async def list_labs_backlog(
    request: Request,
    product_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """List backlog items directly from Labs API (preview before sync)."""
    if not settings.labs_api_key:
        raise HTTPException(status_code=400, detail="LABS_API_KEY not configured")
    
    try:
        service = LabsSyncService()
        return await service.get_backlog(product_id=product_id, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {str(e)}")


@router.get("/labs/insights")
async def get_labs_insights(
    request: Request,
    product_id: int | None = None,
    current_user: User = Depends(get_current_user),
):
    """Get product insights from Labs API."""
    if not settings.labs_api_key:
        raise HTTPException(status_code=400, detail="LABS_API_KEY not configured")
    
    try:
        service = LabsSyncService()
        return await service.get_insights(product_id=product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {str(e)}")
