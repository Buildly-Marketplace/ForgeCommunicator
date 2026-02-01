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
    
    async def list_channels(self, access_token: str, types: str = "public_channel,private_channel,mpim,im") -> list[dict[str, Any]]:
        """
        List all channels/conversations the user has access to.
        
        Args:
            access_token: User's OAuth access token
            types: Comma-separated list of channel types to include
        
        Returns:
            List of channel dictionaries with id, name, is_private, etc.
        """
        channels = []
        cursor = None
        
        async with httpx.AsyncClient() as client:
            while True:
                params = {
                    "types": types,
                    "limit": 200,
                    "exclude_archived": "true",
                }
                if cursor:
                    params["cursor"] = cursor
                
                response = await client.get(
                    f"{self.API_BASE_URL}/conversations.list",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to list Slack channels: {response.status_code}")
                    break
                
                data = response.json()
                if not data.get("ok"):
                    logger.error(f"Slack API error: {data.get('error')}")
                    break
                
                channels.extend(data.get("channels", []))
                
                # Pagination
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
        
        return channels
    
    async def get_channel_history(
        self, 
        access_token: str, 
        channel_id: str, 
        limit: int = 10,
        oldest: str | None = None,
        latest: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get message history from a Slack channel.
        
        Args:
            access_token: User's OAuth access token
            channel_id: Slack channel ID
            limit: Maximum number of messages to fetch (default 10)
            oldest: Only messages after this timestamp
            latest: Only messages before this timestamp
        
        Returns:
            List of message dictionaries (newest first)
        """
        async with httpx.AsyncClient() as client:
            params = {
                "channel": channel_id,
                "limit": min(limit, 1000),  # Slack max is 1000
            }
            if oldest:
                params["oldest"] = oldest
            if latest:
                params["latest"] = latest
            
            response = await client.get(
                f"{self.API_BASE_URL}/conversations.history",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get Slack history: {response.status_code}")
                return []
            
            data = response.json()
            if not data.get("ok"):
                logger.error(f"Slack API error: {data.get('error')}")
                return []
            
            return data.get("messages", [])
    
    async def post_message(
        self,
        access_token: str,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
        unfurl_links: bool = True,
    ) -> dict[str, Any] | None:
        """
        Post a message to a Slack channel.
        
        Args:
            access_token: User's OAuth access token (needs chat:write scope)
            channel_id: Slack channel ID
            text: Message text (supports Slack markdown)
            thread_ts: Optional thread timestamp to reply in a thread
            unfurl_links: Whether to unfurl URLs in the message
        
        Returns:
            Message data if successful, None if failed
        """
        async with httpx.AsyncClient() as client:
            payload = {
                "channel": channel_id,
                "text": text,
                "unfurl_links": unfurl_links,
            }
            if thread_ts:
                payload["thread_ts"] = thread_ts
            
            response = await client.post(
                f"{self.API_BASE_URL}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to post Slack message: {response.status_code}")
                return None
            
            data = response.json()
            if not data.get("ok"):
                logger.error(f"Slack API error posting message: {data.get('error')}")
                return None
            
            return data
    
    async def get_users_by_ids(self, access_token: str, user_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Get user info for multiple user IDs.
        
        Returns:
            Dictionary mapping user_id to user info
        """
        users = {}
        for user_id in user_ids:
            user_info = await self.get_user_info(access_token, user_id)
            if user_info:
                users[user_id] = user_info
        return users

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
