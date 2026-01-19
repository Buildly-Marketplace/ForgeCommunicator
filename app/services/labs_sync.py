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
from app.models.channel import Channel
from app.models.membership import Membership
from app.models.message import Message
from app.models.product import Product
from app.models.team_invite import TeamInvite, InviteStatus
from app.models.user import User
from app.settings import settings


class LabsSyncService:
    """Service for syncing data from Buildly Labs API."""
    
    BASE_URL = settings.labs_api_url
    
    def __init__(self, api_key: str | None = None, access_token: str | None = None):
        """Initialize with either an API key or OAuth access token."""
        self.token = access_token or api_key or settings.labs_api_key
        if not self.token:
            raise ValueError("Labs API key or access token is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
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
        product_uuid: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Get backlog items for a product. product_uuid is required by Labs API."""
        params = {"limit": limit, "offset": offset}
        if product_uuid:
            params["product_uuid"] = product_uuid
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
    
    async def get_team_members(self, org_uuid: str | None = None) -> dict:
        """Get team members for the current organization or specified org."""
        params = {}
        if org_uuid:
            params["organization_uuid"] = org_uuid
        return await self._request("GET", "/team", params=params)
    
    async def get_organization(self) -> dict:
        """Get current user's organization info."""
        return await self._request("GET", "/organization")
    
    async def get_insights(self, product_id: int | None = None) -> dict:
        """Get product insights."""
        params = {}
        if product_id:
            params["product_id"] = product_id
        return await self._request("GET", "/insights", params=params)
    
    # Sync methods
    
    async def sync_products(
        self,
        db: AsyncSession,
        workspace_id: int,
        user_id: int | None = None,
    ) -> dict[str, int]:
        """
        Sync all products from Labs to the workspace.
        Creates a channel for each new product.
        
        Returns dict with counts: {"created": N, "updated": N, "skipped": N, "channels_created": N}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "channels_created": 0}
        
        try:
            response = await self.get_products()
            # Labs API may return data in different formats
            # Try "data" key first, then "results", then treat response as list
            labs_products = response.get("data") or response.get("results") or []
            if isinstance(response, list):
                labs_products = response
            print(f"[Labs Sync] Products API returned {len(labs_products)} products")
            print(f"[Labs Sync] Response structure: {list(response.keys()) if isinstance(response, dict) else 'list'}")
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch products from Labs API: {e}")
        
        for labs_product in labs_products:
            # Log the product structure for debugging
            if labs_products.index(labs_product) == 0:
                print(f"[Labs Sync] First product keys: {list(labs_product.keys()) if isinstance(labs_product, dict) else 'not a dict'}")
            
            # Try multiple possible UUID field names
            labs_uuid = str(
                labs_product.get("product_uuid") or 
                labs_product.get("uuid") or 
                labs_product.get("id") or 
                ""
            )
            
            if not labs_uuid:
                print(f"[Labs Sync] Skipping product with no UUID: {labs_product}")
                stats["skipped"] += 1
                continue
            
            print(f"[Labs Sync] Processing product: {labs_product.get('name', 'unnamed')} (uuid={labs_uuid})")
            
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
                product_name = labs_product.get("name", "Untitled Product")
                new_product = Product(
                    workspace_id=workspace_id,
                    name=product_name,
                    description=labs_product.get("description"),
                    buildly_product_uuid=labs_uuid,
                    icon_url=labs_product.get("icon_url"),
                    is_active=labs_product.get("is_active", True),
                )
                db.add(new_product)
                await db.flush()  # Get the product ID
                
                # Create a channel for this product
                channel_name = product_name.lower().replace(" ", "-")[:80]
                channel = Channel(
                    workspace_id=workspace_id,
                    product_id=new_product.id,
                    name=channel_name,
                    description=f"Discussion channel for {product_name}",
                    topic=labs_product.get("description", "")[:250] if labs_product.get("description") else None,
                    is_default=True,
                )
                db.add(channel)
                stats["channels_created"] += 1
                
                # Create a welcome message if we have a user
                if user_id:
                    await db.flush()  # Get the channel ID
                    welcome_msg = Message(
                        channel_id=channel.id,
                        user_id=user_id,
                        content=f"📦 **{product_name}** synced from Buildly Labs\n\n{labs_product.get('description', '')}",
                    )
                    db.add(welcome_msg)
                
                stats["created"] += 1
        
        await db.commit()
        return stats
    
    async def sync_backlog(
        self,
        db: AsyncSession,
        workspace_id: int,
        product_uuid: str | None = None,
        local_product_id: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, int]:
        """
        Sync backlog items from Labs to artifacts.
        Links artifacts to the product's channel.
        
        Args:
            db: Database session
            workspace_id: Workspace to sync to
            product_uuid: Labs product UUID to filter by (required by Labs API)
            local_product_id: Local product ID to link artifacts to
            user_id: User ID to set as creator for new items
            
        Returns dict with counts: {"created": N, "updated": N, "skipped": N}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}
        
        if not product_uuid:
            # Can't fetch backlog without a product - Labs API requires it
            return stats
        
        try:
            response = await self.get_backlog(product_uuid=product_uuid)
            backlog_items = response.get("data", [])
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch backlog from Labs API: {e}")
        
        # Find the product's default channel
        channel_id = None
        if local_product_id:
            result = await db.execute(
                select(Channel).where(
                    Channel.product_id == local_product_id,
                    Channel.is_default == True,
                )
            )
            channel = result.scalar_one_or_none()
            if channel:
                channel_id = channel.id
        
        new_items = []
        
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
                # Link to channel if not already linked
                if channel_id and not existing.channel_id:
                    existing.channel_id = channel_id
                stats["updated"] += 1
            else:
                if not user_id:
                    stats["skipped"] += 1
                    continue
                
                # Create new artifact linked to the channel
                new_artifact = Artifact(
                    workspace_id=workspace_id,
                    product_id=local_product_id,
                    channel_id=channel_id,
                    type=artifact_type,
                    title=item.get("title", "Untitled Item"),
                    body=item.get("description"),
                    status=artifact_status,
                    tags=item.get("tags"),
                    created_by=user_id,
                    buildly_item_uuid=labs_uuid,
                )
                db.add(new_artifact)
                new_items.append(item)
                stats["created"] += 1
        
        # Post a summary message to the channel with the new backlog items
        if channel_id and user_id and new_items:
            summary_lines = [f"📋 **{len(new_items)} backlog items synced from Labs:**\n"]
            for item in new_items[:10]:  # Limit to first 10
                item_type = item.get("type", "feature")
                emoji = {"feature": "✨", "bug": "🐛", "task": "📝", "story": "📖"}.get(item_type, "📌")
                summary_lines.append(f"- {emoji} {item.get('title', 'Untitled')}")
            if len(new_items) > 10:
                summary_lines.append(f"- ... and {len(new_items) - 10} more")
            
            summary_msg = Message(
                channel_id=channel_id,
                user_id=user_id,
                content="\n".join(summary_lines),
            )
            db.add(summary_msg)
        
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
    
    async def sync_team(
        self,
        db: AsyncSession,
        workspace_id: int,
        invited_by_id: int,
    ) -> dict[str, int]:
        """
        Sync team members from Labs and create invites.
        
        Args:
            db: Database session
            workspace_id: Workspace to create invites for
            invited_by_id: User ID who is inviting
            
        Returns dict with counts: {"invited": N, "already_member": N, "already_invited": N, "skipped": N}
        """
        stats = {"invited": 0, "already_member": 0, "already_invited": 0, "skipped": 0}
        
        try:
            response = await self.get_team_members()
            team_members = response.get("data", [])
        except httpx.HTTPError as e:
            # Team endpoint might not exist or user might not have access
            # Just return empty stats rather than failing the whole sync
            return stats
        
        if not team_members:
            return stats
        
        # Get current inviting user's email to skip
        inviter_result = await db.execute(
            select(User).where(User.id == invited_by_id)
        )
        inviter = inviter_result.scalar_one_or_none()
        inviter_email = inviter.email.lower() if inviter else None
        
        # Get existing workspace members
        members_result = await db.execute(
            select(User.email)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.workspace_id == workspace_id)
        )
        existing_member_emails = {row[0].lower() for row in members_result.all()}
        
        # Get existing pending invites
        invites_result = await db.execute(
            select(TeamInvite.email)
            .where(
                TeamInvite.workspace_id == workspace_id,
                TeamInvite.status == InviteStatus.PENDING,
            )
        )
        existing_invite_emails = {row[0].lower() for row in invites_result.all()}
        
        for member in team_members:
            email = member.get("email", "").lower().strip()
            
            if not email or "@" not in email:
                stats["skipped"] += 1
                continue
            
            # Skip the person doing the inviting
            if inviter_email and email == inviter_email:
                stats["skipped"] += 1
                continue
            
            # Skip if already a workspace member
            if email in existing_member_emails:
                stats["already_member"] += 1
                continue
            
            # Skip if already has pending invite
            if email in existing_invite_emails:
                stats["already_invited"] += 1
                continue
            
            # Create invite
            name = member.get("name") or member.get("display_name") or member.get("first_name", "")
            if member.get("last_name"):
                name = f"{name} {member.get('last_name')}".strip()
            
            labs_user_uuid = str(member.get("id") or member.get("uuid", "")) or None
            
            invite = TeamInvite.create(
                workspace_id=workspace_id,
                email=email,
                name=name if name else None,
                role="member",
                invited_by_id=invited_by_id,
                labs_user_uuid=labs_user_uuid,
                expires_in_days=14,  # 2 week expiry for synced invites
            )
            db.add(invite)
            existing_invite_emails.add(email)  # Prevent duplicates in same batch
            stats["invited"] += 1
        
        await db.commit()
        return stats


async def sync_all_from_labs(
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
    api_key: str | None = None,
    access_token: str | None = None,
) -> dict[str, dict[str, int]]:
    """
    Sync all data from Labs API for a workspace.
    Creates channels for products and links artifacts to them.
    
    Returns dict with sync stats for each entity type.
    """
    service = LabsSyncService(api_key=api_key, access_token=access_token)
    
    results = {}
    
    # Sync products first (creates channels for new products)
    results["products"] = await service.sync_products(db, workspace_id, user_id=user_id)
    
    # Sync backlog items for each product (Labs API requires product_uuid)
    backlog_stats = {"created": 0, "updated": 0, "skipped": 0}
    
    # Get all products in this workspace that have a Labs UUID
    product_result = await db.execute(
        select(Product).where(
            Product.workspace_id == workspace_id,
            Product.buildly_product_uuid.isnot(None),
        )
    )
    products = product_result.scalars().all()
    
    for product in products:
        product_stats = await service.sync_backlog(
            db,
            workspace_id,
            product_uuid=product.buildly_product_uuid,
            local_product_id=product.id,
            user_id=user_id,
        )
        backlog_stats["created"] += product_stats["created"]
        backlog_stats["updated"] += product_stats["updated"]
        backlog_stats["skipped"] += product_stats["skipped"]
    
    results["backlog"] = backlog_stats
    
    # Sync team members and create invites
    results["team"] = await service.sync_team(db, workspace_id, invited_by_id=user_id)
    
    return results


# Create a default instance for easy import
def get_labs_service(api_key: str | None = None, access_token: str | None = None) -> LabsSyncService:
    """Get a Labs sync service instance."""
    return LabsSyncService(api_key=api_key, access_token=access_token)
