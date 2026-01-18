"""
Buildly Labs API client for product integration.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.settings import settings


@dataclass
class BuildlyProduct:
    """Product info from Buildly Labs."""
    
    uuid: str
    name: str
    description: str | None = None
    organization_uuid: str | None = None


class BuildlyClient:
    """Client for Buildly Labs API."""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = settings.buildly_api_url
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Make authenticated request to Buildly API."""
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
    
    async def get_products(self) -> list[BuildlyProduct]:
        """Fetch products list from Buildly Labs."""
        data = await self._request("GET", "/product/")
        
        products = []
        for item in data.get("results", data if isinstance(data, list) else []):
            products.append(
                BuildlyProduct(
                    uuid=item["product_uuid"],
                    name=item["name"],
                    description=item.get("description"),
                    organization_uuid=item.get("organization_uuid"),
                )
            )
        return products
    
    async def get_product(self, product_uuid: str) -> BuildlyProduct | None:
        """Fetch single product by UUID."""
        try:
            data = await self._request("GET", f"/product/{product_uuid}/")
            return BuildlyProduct(
                uuid=data["product_uuid"],
                name=data["name"],
                description=data.get("description"),
                organization_uuid=data.get("organization_uuid"),
            )
        except httpx.HTTPStatusError:
            return None
    
    async def push_artifact(
        self,
        product_uuid: str,
        artifact_type: str,
        title: str,
        body: str | None = None,
        **extra,
    ) -> dict[str, Any] | None:
        """Push artifact to Buildly Labs (stub for future implementation)."""
        # TODO: Implement when Buildly Labs supports artifact sync
        # This is a placeholder for the interface
        return None
    
    async def get_organization(self) -> dict[str, Any] | None:
        """Get current user's organization."""
        try:
            data = await self._request("GET", "/organization/")
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return data.get("results", [{}])[0] if "results" in data else None
        except (httpx.HTTPStatusError, IndexError, KeyError):
            return None
