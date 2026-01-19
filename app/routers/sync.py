"""
Labs API sync router.

Endpoints for syncing data from Buildly Labs.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.workspace import Workspace
from app.models.membership import Membership, MembershipRole
from app.services.labs_sync import LabsSyncService, sync_all_from_labs
from app.settings import settings


router = APIRouter(prefix="/sync", tags=["sync"])


async def get_workspace_labs_token(
    db: AsyncSession,
    workspace_id: int,
    user: User,
) -> tuple[str | None, str]:
    """
    Get the Labs API token for a workspace.
    
    Priority:
    1. Workspace's API token (if configured)
    2. Workspace's OAuth token (if connected)
    3. User's personal OAuth token (fallback)
    4. Global API key (fallback)
    
    Returns (token, auth_method) tuple.
    """
    # Get workspace
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    
    if not workspace:
        return None, "none"
    
    # Priority 1: Workspace API token
    if workspace.labs_api_token:
        return workspace.labs_api_token, "workspace_api_token"
    
    # Priority 2: Workspace OAuth token
    if workspace.labs_access_token:
        return workspace.labs_access_token, "workspace_oauth"
    
    # Priority 3: User's personal OAuth token
    if user.labs_access_token:
        return user.labs_access_token, "user_oauth"
    
    # Priority 4: Global API key
    if settings.labs_api_key:
        return settings.labs_api_key, "global_api_key"
    
    return None, "none"


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
    
    # Get auth token for this workspace
    token, auth_method = await get_workspace_labs_token(db, workspace_id, current_user)
    if not token:
        raise HTTPException(status_code=400, detail="Configure Labs integration in workspace settings to enable sync")
    
    try:
        service = LabsSyncService(access_token=token)
        stats = await service.sync_products(db, workspace_id)
        return {
            "success": True,
            "message": f"Synced products: {stats['created']} created, {stats['updated']} updated",
            "stats": stats,
            "auth_method": auth_method,
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
    
    # Get auth token for this workspace
    token, auth_method = await get_workspace_labs_token(db, workspace_id, current_user)
    if not token:
        raise HTTPException(status_code=400, detail="Configure Labs integration in workspace settings to enable sync")
    
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
    
    # Get auth token for this workspace
    token, auth_method = await get_workspace_labs_token(db, workspace_id, current_user)
    if not token:
        if is_htmx:
            return HTMLResponse(
                '<div class="text-yellow-600 p-2 bg-yellow-50 rounded">⚠️ Configure Labs integration in workspace settings to enable sync</div>'
            )
        raise HTTPException(status_code=400, detail="Configure Labs integration in workspace settings to enable sync")
    
    try:
        results = await sync_all_from_labs(
            db,
            workspace_id,
            user_id=current_user.id,
            access_token=token,
        )
        
        # Build detailed stats
        products = results.get("products", {})
        backlog = results.get("backlog", {})
        team = results.get("team", {})
        
        products_created = products.get("created", 0)
        products_updated = products.get("updated", 0)
        channels_created = products.get("channels_created", 0)
        backlog_created = backlog.get("created", 0)
        backlog_updated = backlog.get("updated", 0)
        backlog_messages = backlog.get("messages", 0)
        team_invited = team.get("invited", 0)
        
        if is_htmx:
            # Build detailed breakdown
            errors = results.get("errors", [])
            backlog_errors = backlog.get("errors", 0)
            
            if errors or backlog_errors:
                # Partial success with warnings
                lines = ['<div class="p-2 bg-yellow-50 rounded border border-yellow-200">']
                lines.append('<span class="text-yellow-700">⚠️ Sync completed with some issues:</span><br>')
            else:
                lines = ['<div class="text-green-600 p-2 bg-green-50 rounded">']
                lines.append('✓ Sync complete:<br>')
            
            lines.append(f'<span class="text-gray-700">• Products: {products_created} new, {products_updated} updated</span><br>')
            lines.append(f'<span class="text-gray-700">• Channels: {channels_created} created</span><br>')
            lines.append(f'<span class="text-gray-700">• Backlog items: {backlog_created} new, {backlog_updated} updated')
            if backlog_messages:
                lines.append(f' ({backlog_messages} threads)')
            if backlog_errors:
                lines.append(f' <span class="text-orange-600">({backlog_errors} errors)</span>')
            lines.append('</span><br>')
            lines.append(f'<span class="text-gray-700">• Team invites: {team_invited} created</span>')
            
            if errors:
                lines.append('<br><span class="text-red-600 text-xs mt-1">')
                for err in errors:
                    lines.append(f'<br>• {err}')
                lines.append('</span>')
            
            lines.append('</div>')
            return HTMLResponse(''.join(lines))
        
        return {
            "success": True,
            "message": "Full sync complete",
            "results": results,
        }
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"Sync error: {error_detail}")  # Log to server
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
    # Use user's OAuth token if available, otherwise API key
    token = current_user.labs_access_token or settings.labs_api_key
    if not token:
        raise HTTPException(status_code=400, detail="Sign in with Buildly Labs to enable sync")
    
    try:
        service = LabsSyncService(access_token=token)
        return await service.get_products(limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {str(e)}")


@router.get("/labs/debug")
async def debug_labs_api(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Debug endpoint to see raw Labs API responses."""
    token = current_user.labs_access_token or settings.labs_api_key
    if not token:
        return {"error": "No token available", "has_labs_token": bool(current_user.labs_access_token), "has_api_key": bool(settings.labs_api_key)}
    
    try:
        service = LabsSyncService(access_token=token)
        
        # Get raw responses
        products_response = await service.get_products(limit=5)
        me_response = await service.get_me()
        
        # Analyze structure
        products_keys = list(products_response.keys()) if isinstance(products_response, dict) else "response is a list"
        
        # Try to find products in different locations
        products_in_data = products_response.get("data", []) if isinstance(products_response, dict) else []
        products_in_results = products_response.get("results", []) if isinstance(products_response, dict) else []
        products_direct = products_response if isinstance(products_response, list) else []
        
        first_product = None
        products_list = products_in_data or products_in_results or products_direct
        if products_list and len(products_list) > 0:
            first_product = products_list[0]
        
        return {
            "auth_method": "oauth" if current_user.labs_access_token else "api_key",
            "me": me_response,
            "products_response_keys": products_keys,
            "products_in_data_count": len(products_in_data),
            "products_in_results_count": len(products_in_results),
            "products_direct_count": len(products_direct),
            "first_product_keys": list(first_product.keys()) if first_product and isinstance(first_product, dict) else None,
            "first_product": first_product,
            "raw_products_response": products_response,
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


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
