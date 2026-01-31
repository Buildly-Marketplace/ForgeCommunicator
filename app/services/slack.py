"""
Slack integration service for receiving notifications.

Handles OAuth flow, webhook events, and notification processing.
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)


class SlackService:
    """Service for Slack OAuth and notification handling."""
    
    # Slack API endpoints
    OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
    OAUTH_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
    API_BASE_URL = "https://slack.com/api"
    
    # Required OAuth scopes for receiving notifications
    # User scopes for reading user's DMs and mentions
    USER_SCOPES = [
        "users:read",           # Read user info
        "channels:read",        # Read public channel info
        "groups:read",          # Read private channel info
        "im:read",              # Read DMs
        "mpim:read",            # Read group DMs
        "im:history",           # Read DM history (for context)
        "mpim:history",         # Read group DM history
    ]
    
    def __init__(self):
        self.client_id = getattr(settings, 'slack_client_id', None)
        self.client_secret = getattr(settings, 'slack_client_secret', None)
        self.signing_secret = getattr(settings, 'slack_signing_secret', None)
    
    @property
    def is_configured(self) -> bool:
        """Check if Slack integration is configured."""
        return bool(self.client_id and self.client_secret)
    
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate Slack OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "scope": "",  # No bot scopes needed
            "user_scope": ",".join(self.USER_SCOPES),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{self.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
    
    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any] | None:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            
            if response.status_code != 200:
                logger.error(f"Slack token exchange failed: {response.status_code}")
                return None
            
            data = response.json()
            if not data.get("ok"):
                logger.error(f"Slack token exchange error: {data.get('error')}")
                return None
            
            return data
    
    async def get_user_info(self, access_token: str, user_id: str) -> dict[str, Any] | None:
        """Get user info from Slack."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/users.info",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"user": user_id},
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return data.get("user") if data.get("ok") else None
    
    async def get_team_info(self, access_token: str) -> dict[str, Any] | None:
        """Get team/workspace info from Slack."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/team.info",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return data.get("team") if data.get("ok") else None
    
    async def get_channel_info(self, access_token: str, channel_id: str) -> dict[str, Any] | None:
        """Get channel info from Slack."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/conversations.info",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"channel": channel_id},
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return data.get("channel") if data.get("ok") else None
    
    def verify_webhook_signature(
        self,
        signature: str,
        timestamp: str,
        body: bytes,
    ) -> bool:
        """Verify Slack webhook signature."""
        if not self.signing_secret:
            logger.warning("Slack signing secret not configured")
            return False
        
        # Check timestamp to prevent replay attacks (within 5 minutes)
        try:
            request_timestamp = int(timestamp)
            if abs(time.time() - request_timestamp) > 60 * 5:
                logger.warning("Slack webhook timestamp too old")
                return False
        except ValueError:
            return False
        
        # Compute signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        computed_signature = "v0=" + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    
    def build_message_url(
        self,
        team_id: str,
        channel_id: str,
        message_ts: str,
    ) -> str:
        """Build URL to open message in Slack."""
        # Convert timestamp to URL format (remove decimal point)
        ts_for_url = message_ts.replace(".", "")
        return f"https://slack.com/archives/{channel_id}/p{ts_for_url}"
    
    def parse_event(self, event_data: dict[str, Any]) -> dict[str, Any] | None:
        """Parse Slack event into notification data."""
        event = event_data.get("event", {})
        event_type = event.get("type")
        
        if event_type == "message":
            # Skip bot messages and message subtypes (edits, deletes, etc.)
            if event.get("bot_id") or event.get("subtype"):
                return None
            
            channel_type = event.get("channel_type", "")
            
            # Determine notification source
            if channel_type == "im":
                source = "slack_dm"
            elif channel_type == "mpim":
                source = "slack_dm"  # Group DM treated as DM
            else:
                # Check if user was mentioned
                text = event.get("text", "")
                # Slack mentions look like <@U123ABC>
                source = "slack_channel"  # Will check for mentions later
            
            return {
                "source": source,
                "channel_id": event.get("channel"),
                "user_id": event.get("user"),
                "text": event.get("text", ""),
                "ts": event.get("ts"),
                "team_id": event_data.get("team_id"),
            }
        
        return None


# Singleton instance
slack_service = SlackService()
