"""
OAuth authentication providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from app.settings import settings


@dataclass
class OAuthUserInfo:
    """User info returned from OAuth provider."""
    
    provider: str
    sub: str  # Subject ID from provider
    email: str
    name: str
    picture: str | None = None
    domain: str | None = None  # Google Workspace domain
    extra: dict[str, Any] | None = None


class OAuthProvider(ABC):
    """Base class for OAuth providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @property
    @abstractmethod
    def authorization_url(self) -> str:
        """Authorization URL for OAuth flow."""
        pass
    
    @abstractmethod
    def get_authorization_params(self, state: str) -> dict[str, str]:
        """Get authorization URL parameters."""
        pass
    
    @abstractmethod
    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for tokens."""
        pass
    
    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user info from provider."""
        pass


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth provider."""
    
    name = "google"
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri
        self.allowed_domain = settings.google_allowed_domain
    
    def get_authorization_params(self, state: str) -> dict[str, str]:
        """Get Google OAuth authorization parameters."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        
        # Restrict to specific domain if configured
        if self.allowed_domain:
            params["hd"] = self.allowed_domain
        
        return params
    
    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user info from Google."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
        
        # Extract domain from email
        email = data["email"]
        domain = email.split("@")[1] if "@" in email else None
        
        return OAuthUserInfo(
            provider="google",
            sub=data["id"],
            email=email,
            name=data.get("name", email.split("@")[0]),
            picture=data.get("picture"),
            domain=domain,
        )


class BuildlyOAuthProvider(OAuthProvider):
    """Buildly Labs OAuth provider."""
    
    name = "buildly"
    
    def __init__(self):
        self.client_id = settings.buildly_client_id
        self.client_secret = settings.buildly_client_secret
        self.redirect_uri = settings.buildly_redirect_uri
        self.auth_url = settings.buildly_auth_url
        self.api_url = settings.buildly_api_url
    
    @property
    def authorization_url(self) -> str:
        return f"{self.auth_url}/oauth/authorize"
    
    @property
    def token_url(self) -> str:
        return f"{self.auth_url}/oauth/token"
    
    @property
    def userinfo_url(self) -> str:
        return f"{self.api_url}/coreuser/me/"
    
    def get_authorization_params(self, state: str) -> dict[str, str]:
        """Get Buildly OAuth authorization parameters."""
        return {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "read write",
            "state": state,
        }
    
    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user info from Buildly Labs."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
        
        return OAuthUserInfo(
            provider="buildly",
            sub=str(data.get("core_user_uuid", data.get("id"))),
            email=data["email"],
            name=data.get("first_name", "") + " " + data.get("last_name", ""),
            picture=data.get("avatar"),
            extra={
                "organization_uuid": data.get("organization", {}).get("organization_uuid"),
            },
        )


def get_oauth_provider(provider_name: str) -> OAuthProvider | None:
    """Get OAuth provider by name."""
    providers = {
        "google": GoogleOAuthProvider if settings.google_oauth_enabled else None,
        "buildly": BuildlyOAuthProvider if settings.buildly_oauth_enabled else None,
    }
    
    provider_class = providers.get(provider_name)
    if provider_class:
        return provider_class()
    return None


def get_available_providers() -> list[str]:
    """Get list of available OAuth providers."""
    providers = []
    if settings.google_oauth_enabled:
        providers.append("google")
    if settings.buildly_oauth_enabled:
        providers.append("buildly")
    return providers
