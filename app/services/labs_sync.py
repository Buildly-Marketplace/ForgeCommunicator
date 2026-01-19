"""
Buildly Labs API sync service.

Syncs products, backlog items, releases, and milestones from Labs API.
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact, ArtifactType, ArtifactStatus
from app.models.product import Product
from app.settings import settings


class LabsSyncService:
    """Service for syncing data from Buildly Labs API."""
    
    BASE_URL = settings.labs_api_url
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.labs_api_key
        if not self.api_key:
            raise ValueError("Labs API key is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """Make an authenticated request to the Labs API."""
        url = f"{self.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    
    async def get_me(self) -> dict:
        """Get current user profile."""
        return await self._request("GET", "/me")
    
    async def get_products(self, limit: int = 100, offset: int = 0) -> dict:
        """Get all products."""
        return await self._request("GET", "/products", params={"limit": limit, "offset": offset})
    
    async def get_product(self, product_id: int) -> dict:
        """Get a specific product."""
        return await self._request("GET", f"/products/{product_id}")
    
    async def get_backlog(
        self,
        product_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Get backlog items, optionally filtered by product."""
        params = {"limit": limit, "offset": offset}
        if product_id:
            params["product_id"] = product_id
        return await self._request("GET", "/backlog", params=params)
    
    async def get_backlog_item(self, item_id: int) -> dict:
        """Get a specific backlog item."""
        return await self._request("GET", f"/backlog/{item_id}")
    
    async def get_releases(self, product_id: int | None = None, limit: int = 100, offset: int = 0) -> dict:
        """Get releases, optionally filtered by product."""
        params = {"limit": limit, "offset": offset}
        if product_id:
            params["product_id"] = product_id
        return await self._request("GET", "/releases", params=params)
    
    async def get_milestones(self, product_id: int | None = None, limit: int = 100, offset: int = 0) -> dict:
        """Get milestones, optionally filtered by product."""
        params = {"limit": limit, "offset": offset}
        if product_id:
            params["product_id"] = product_id
        return await self._request("GET", "/milestones", params=params)
    
    async def get_insights(self, product_id: int | None = None) -> dict:
        """Get product insights."""
        params = {}
        if product_id:
            params["product_id"] = product_id
        return await self._request("GET", "/insights", params=params)
    
    # Sync methods
    
    async def sync_products(self, db: AsyncSession, workspace_id: int) -> dict[str, int]:
        """
        Sync all products from Labs to the workspace.
        
        Returns dict with counts: {"created": N, "updated": N, "skipped": N}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}
        
        try:
            response = await self.get_products()
            labs_products = response.get("data", [])
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch products from Labs API: {e}")
        
        for labs_product in labs_products:
            labs_uuid = str(labs_product.get("id") or labs_product.get("uuid", ""))
            
            if not labs_uuid:
                stats["skipped"] += 1
                continue
            
            # Check if product already exists
            result = await db.execute(
                select(Product).where(
                    Product.workspace_id == workspace_id,
                    Product.buildly_product_uuid == labs_uuid,
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing product
                existing.name = labs_product.get("name", existing.name)
                existing.description = labs_product.get("description", existing.description)
                existing.icon_url = labs_product.get("icon_url", existing.icon_url)
                existing.is_active = labs_product.get("is_active", True)
                stats["updated"] += 1
            else:
                # Create new product
                new_product = Product(
                    workspace_id=workspace_id,
                    name=labs_product.get("name", "Untitled Product"),
                    description=labs_product.get("description"),
                    buildly_product_uuid=labs_uuid,
                    icon_url=labs_product.get("icon_url"),
                    is_active=labs_product.get("is_active", True),
                )
                db.add(new_product)
                stats["created"] += 1
        
        await db.commit()
        return stats
    
    async def sync_backlog(
        self,
        db: AsyncSession,
        workspace_id: int,
        product_id: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, int]:
        """
        Sync backlog items from Labs to artifacts.
        
        Args:
            db: Database session
            workspace_id: Workspace to sync to
            product_id: Local product ID to filter by (optional)
            user_id: User ID to set as creator for new items
            
        Returns dict with counts: {"created": N, "updated": N, "skipped": N}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}
        
        # Get product's buildly_product_uuid if product_id is provided
        labs_product_id = None
        local_product = None
        if product_id:
            result = await db.execute(select(Product).where(Product.id == product_id))
            local_product = result.scalar_one_or_none()
            if local_product and local_product.buildly_product_uuid:
                labs_product_id = int(local_product.buildly_product_uuid)
        
        try:
            response = await self.get_backlog(product_id=labs_product_id)
            backlog_items = response.get("data", [])
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch backlog from Labs API: {e}")
        
        for item in backlog_items:
            labs_uuid = str(item.get("id") or item.get("uuid", ""))
            
            if not labs_uuid:
                stats["skipped"] += 1
                continue
            
            # Check if artifact already exists
            result = await db.execute(
                select(Artifact).where(
                    Artifact.workspace_id == workspace_id,
                    Artifact.buildly_item_uuid == labs_uuid,
                )
            )
            existing = result.scalar_one_or_none()
            
            # Map Labs item type to artifact type
            artifact_type = self._map_item_type(item.get("type", "feature"))
            artifact_status = self._map_item_status(item.get("status", "open"), artifact_type)
            
            if existing:
                # Update existing artifact
                existing.title = item.get("title", existing.title)
                existing.body = item.get("description", existing.body)
                existing.status = artifact_status
                existing.tags = item.get("tags", existing.tags)
                stats["updated"] += 1
            else:
                if not user_id:
                    stats["skipped"] += 1
                    continue
                
                # Create new artifact
                new_artifact = Artifact(
                    workspace_id=workspace_id,
                    product_id=product_id,
                    type=artifact_type,
                    title=item.get("title", "Untitled Item"),
                    body=item.get("description"),
                    status=artifact_status,
                    tags=item.get("tags"),
                    created_by=user_id,
                    buildly_item_uuid=labs_uuid,
                )
                db.add(new_artifact)
                stats["created"] += 1
        
        await db.commit()
        return stats
    
    def _map_item_type(self, labs_type: str) -> ArtifactType:
        """Map Labs item type to local artifact type."""
        type_map = {
            "feature": ArtifactType.FEATURE,
            "bug": ArtifactType.ISSUE,
            "issue": ArtifactType.ISSUE,
            "task": ArtifactType.TASK,
            "story": ArtifactType.FEATURE,
            "epic": ArtifactType.FEATURE,
            "decision": ArtifactType.DECISION,
        }
        return type_map.get(labs_type.lower(), ArtifactType.FEATURE)
    
    def _map_item_status(self, labs_status: str, artifact_type: ArtifactType) -> str:
        """Map Labs status to local artifact status."""
        # General status mappings
        status_map = {
            "open": ArtifactStatus.OPEN.value,
            "closed": ArtifactStatus.CLOSED.value,
            "done": ArtifactStatus.DONE.value,
            "todo": ArtifactStatus.TODO.value,
            "in_progress": ArtifactStatus.IN_PROGRESS.value,
            "in-progress": ArtifactStatus.IN_PROGRESS.value,
            "backlog": ArtifactStatus.TODO.value,
            "planned": ArtifactStatus.PLANNED.value,
            "shipped": ArtifactStatus.SHIPPED.value,
            "blocked": ArtifactStatus.BLOCKED.value,
        }
        
        mapped = status_map.get(labs_status.lower())
        if mapped:
            return mapped
        
        # Default to type-specific default
        return Artifact.get_default_status(artifact_type)


async def sync_all_from_labs(
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
    api_key: str | None = None,
) -> dict[str, dict[str, int]]:
    """
    Sync all data from Labs API for a workspace.
    
    Returns dict with sync stats for each entity type.
    """
    service = LabsSyncService(api_key=api_key)
    
    results = {}
    
    # Sync products first
    results["products"] = await service.sync_products(db, workspace_id)
    
    # Sync backlog items
    results["backlog"] = await service.sync_backlog(db, workspace_id, user_id=user_id)
    
    return results


# Create a default instance for easy import
def get_labs_service(api_key: str | None = None) -> LabsSyncService:
    """Get a Labs sync service instance."""
    return LabsSyncService(api_key=api_key)
