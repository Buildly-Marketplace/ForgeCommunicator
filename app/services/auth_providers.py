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
    """Google OAuth provider with Calendar API support."""
    
    name = "google"
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    calendar_url = "https://www.googleapis.com/calendar/v3"
    
    # Scopes for Calendar integration
    CALENDAR_SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",  # Read calendar events
        "https://www.googleapis.com/auth/calendar.events",    # Create calendar events (for meeting requests)
    ]
    
    def __init__(self, include_calendar: bool = False, redirect_uri_override: str | None = None):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = redirect_uri_override or settings.google_redirect_uri
        self.allowed_domain = settings.google_allowed_domain
        self.include_calendar = include_calendar
    
    def get_authorization_params(self, state: str) -> dict[str, str]:
        """Get Google OAuth authorization parameters."""
        # Base scopes for authentication
        scopes = ["openid", "email", "profile"]
        
        # Add calendar scopes if requested
        if self.include_calendar:
            scopes.extend(self.CALENDAR_SCOPES)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
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
    
    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh the access token using the refresh token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()
    
    async def get_calendar_events(
        self, 
        access_token: str,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get calendar events from Google Calendar.
        
        Args:
            access_token: OAuth access token with calendar scope
            time_min: Start time in RFC3339 format (defaults to now)
            time_max: End time in RFC3339 format (defaults to 24h from now)
            max_results: Maximum number of events to return
            
        Returns:
            List of calendar events (stripped of sensitive details)
        """
        from datetime import datetime, timedelta, timezone
        
        # Default time range: now to 24 hours from now
        now = datetime.now(timezone.utc)
        if not time_min:
            time_min = now.isoformat()
        if not time_max:
            time_max = (now + timedelta(hours=24)).isoformat()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.calendar_url}/calendars/primary/events",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "maxResults": max_results,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )
            response.raise_for_status()
            data = response.json()
        
        return data.get("items", [])
    
    async def get_current_status_from_calendar(
        self, 
        access_token: str,
    ) -> tuple[str, str | None]:
        """
        Determine user's status from their calendar.
        
        Returns:
            Tuple of (status, status_message) where status is one of:
            - "active" - free, no current events
            - "dnd" - in a meeting
            - "away" - on vacation/out of office
        """
        from datetime import datetime, timedelta, timezone
        
        now = datetime.now(timezone.utc)
        
        try:
            # Check for events happening now or in next 5 minutes
            events = await self.get_calendar_events(
                access_token,
                time_min=now.isoformat(),
                time_max=(now + timedelta(hours=8)).isoformat(),
                max_results=5,
            )
            
            for event in events:
                # Skip all-day events for "in meeting" status
                if "dateTime" not in event.get("start", {}):
                    # Check if it's an all-day vacation/OOO event
                    summary = event.get("summary", "").lower()
                    if any(word in summary for word in ["vacation", "pto", "ooo", "out of office", "holiday", "off"]):
                        return "away", "On vacation"
                    continue
                
                # Parse event times
                start_str = event["start"]["dateTime"]
                end_str = event["end"]["dateTime"]
                
                # Parse ISO format with timezone
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                
                # Check if event is happening now
                if start <= now <= end:
                    # Check for vacation/OOO events
                    summary = event.get("summary", "").lower()
                    if any(word in summary for word in ["vacation", "pto", "ooo", "out of office", "holiday", "off"]):
                        return "away", "On vacation"
                    
                    # User is in a meeting (don't expose meeting details)
                    return "dnd", "In a meeting"
                
                # Check if event is starting soon (within 5 minutes)
                if now < start <= now + timedelta(minutes=5):
                    return "dnd", "In a meeting soon"
            
            # No current events
            return "active", None
            
        except Exception as e:
            # If calendar access fails, don't change status
            return "active", None
    
    async def create_meeting_event(
        self,
        access_token: str,
        summary: str,
        start_time: str,
        end_time: str,
        attendees: list[str],
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a calendar event (meeting request).
        
        Args:
            access_token: OAuth access token with calendar.events scope
            summary: Event title
            start_time: Start time in RFC3339 format
            end_time: End time in RFC3339 format  
            attendees: List of email addresses to invite
            description: Optional event description
            
        Returns:
            Created event data
        """
        event_body = {
            "summary": summary,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
            "attendees": [{"email": email} for email in attendees],
        }
        
        if description:
            event_body["description"] = description
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.calendar_url}/calendars/primary/events",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=event_body,
                params={"sendUpdates": "all"},  # Send invites
            )
            response.raise_for_status()
            return response.json()


class BuildlyOAuthProvider(OAuthProvider):
    """Buildly Labs OAuth provider.
    
    Labs acts as the identity provider for all Buildly apps:
    - labs.buildly.io (identity provider)
    - comms.buildly.io (this app)
    - collab.buildly.io
    """
    
    name = "buildly"
    
    def __init__(self):
        self.client_id = settings.buildly_client_id
        self.client_secret = settings.buildly_client_secret
        self.redirect_uri = settings.buildly_redirect_uri
        self.oauth_url = settings.buildly_oauth_url
        self.api_url = settings.buildly_api_url
    
    @property
    def authorization_url(self) -> str:
        return f"{self.oauth_url}/oauth/authorize"
    
    @property
    def token_url(self) -> str:
        return f"{self.oauth_url}/oauth/token"
    
    @property
    def userinfo_url(self) -> str:
        return f"{self.api_url}/me"
    
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
        """Get user info from Buildly Labs.
        
        Labs /me endpoint returns:
        {
            "data": {
                "id": 123,
                "uuid": "...",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "avatar_url": "...",
                "organization_uuid": "..."
            }
        }
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            result = response.json()
        
        # Handle both direct response and wrapped response
        data = result.get("data", result)
        
        # Build display name from first/last or fall back to email
        first = data.get("first_name", "")
        last = data.get("last_name", "")
        name = f"{first} {last}".strip() or data["email"].split("@")[0]
        
        return OAuthUserInfo(
            provider="buildly",
            sub=str(data.get("uuid", data.get("id"))),
            email=data["email"],
            name=name,
            picture=data.get("avatar_url") or data.get("avatar"),
            extra={
                "organization_uuid": data.get("organization_uuid"),
                "labs_user_id": data.get("id"),
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
