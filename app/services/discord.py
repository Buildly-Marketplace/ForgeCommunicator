"""
Discord integration service for receiving notifications.

Handles OAuth flow, webhook events, and notification processing.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)


class DiscordService:
    """Service for Discord OAuth and notification handling."""
    
    # Discord API endpoints
    OAUTH_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
    OAUTH_TOKEN_URL = "https://discord.com/api/oauth2/token"
    OAUTH_REVOKE_URL = "https://discord.com/api/oauth2/token/revoke"
    API_BASE_URL = "https://discord.com/api/v10"
    
    # OAuth scopes for reading messages
    SCOPES = [
        "identify",             # Read user info
        "guilds",               # Read server list
        "guilds.members.read",  # Read server member info
        "messages.read",        # Read messages in channels user has access to
    ]
    
    def __init__(self):
        self.client_id = getattr(settings, 'discord_client_id', None)
        self.client_secret = getattr(settings, 'discord_client_secret', None)
        self.bot_token = getattr(settings, 'discord_bot_token', None)
    
    @property
    def is_configured(self) -> bool:
        """Check if Discord integration is configured."""
        return bool(self.client_id and self.client_secret)
    
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate Discord OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "state": state,
            "prompt": "consent",
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
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code != 200:
                logger.error(f"Discord token exchange failed: {response.status_code} - {response.text}")
                return None
            
            return response.json()
    
    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Refresh Discord access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code != 200:
                logger.error(f"Discord token refresh failed: {response.status_code}")
                return None
            
            return response.json()
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke Discord access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_REVOKE_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "token": token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            return response.status_code == 200
    
    async def get_current_user(self, access_token: str) -> dict[str, Any] | None:
        """Get current authenticated user info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                logger.error(f"Discord get user failed: {response.status_code}")
                return None
            
            return response.json()
    
    async def get_user_guilds(self, access_token: str) -> list[dict[str, Any]] | None:
        """Get list of guilds (servers) the user is in."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                logger.error(f"Discord get guilds failed: {response.status_code}")
                return None
            
            return response.json()
    
    async def get_dm_channels(self, access_token: str) -> list[dict[str, Any]] | None:
        """Get user's DM channels."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/users/@me/channels",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                logger.error(f"Discord get DM channels failed: {response.status_code}")
                return None
            
            return response.json()
    
    async def get_guild_channels(self, guild_id: str, bot_token: str | None = None) -> list[dict[str, Any]] | None:
        """
        Get channels in a guild (requires bot token with appropriate permissions).
        
        Args:
            guild_id: Discord server/guild ID
            bot_token: Bot token (uses configured bot token if not provided)
        """
        token = bot_token or self.bot_token
        if not token:
            logger.error("No bot token available for getting guild channels")
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/guilds/{guild_id}/channels",
                headers={"Authorization": f"Bot {token}"},
            )
            
            if response.status_code != 200:
                logger.error(f"Discord get guild channels failed: {response.status_code}")
                return None
            
            # Filter to text channels only (type 0 = text, 5 = announcement)
            channels = response.json()
            return [c for c in channels if c.get("type") in [0, 5]]
    
    async def get_channel_messages(
        self,
        channel_id: str,
        access_token: str | None = None,
        bot_token: str | None = None,
        limit: int = 10,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get message history from a Discord channel.
        
        Args:
            channel_id: Discord channel ID
            access_token: User OAuth token (for DMs)
            bot_token: Bot token (for guild channels)
            limit: Maximum number of messages (default 10, max 100)
            before: Get messages before this message ID
            after: Get messages after this message ID
        
        Returns:
            List of message dictionaries (newest first)
        """
        # Prefer bot token for guild channels, user token for DMs
        token = bot_token or self.bot_token or access_token
        token_type = "Bot" if (bot_token or self.bot_token) else "Bearer"
        
        if not token:
            logger.error("No token available for getting Discord messages")
            return []
        
        async with httpx.AsyncClient() as client:
            params = {"limit": min(limit, 100)}
            if before:
                params["before"] = before
            if after:
                params["after"] = after
            
            response = await client.get(
                f"{self.API_BASE_URL}/channels/{channel_id}/messages",
                headers={"Authorization": f"{token_type} {token}"},
                params=params,
            )
            
            if response.status_code != 200:
                logger.error(f"Discord get messages failed: {response.status_code} - {response.text}")
                return []
            
            return response.json()
    
    async def post_message(
        self,
        channel_id: str,
        content: str,
        access_token: str | None = None,
        bot_token: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Post a message to a Discord channel.
        
        Args:
            channel_id: Discord channel ID
            content: Message content (supports Discord markdown)
            access_token: User OAuth token
            bot_token: Bot token
        
        Returns:
            Message data if successful, None if failed
        """
        token = bot_token or self.bot_token or access_token
        token_type = "Bot" if (bot_token or self.bot_token) else "Bearer"
        
        if not token:
            logger.error("No token available for posting Discord message")
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE_URL}/channels/{channel_id}/messages",
                headers={
                    "Authorization": f"{token_type} {token}",
                    "Content-Type": "application/json",
                },
                json={"content": content},
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Discord post message failed: {response.status_code} - {response.text}")
                return None
            
            return response.json()
    
    async def get_user(self, user_id: str, bot_token: str | None = None) -> dict[str, Any] | None:
        """Get Discord user info by ID."""
        token = bot_token or self.bot_token
        if not token:
            logger.error("No bot token available for getting user info")
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/users/{user_id}",
                headers={"Authorization": f"Bot {token}"},
            )
            
            if response.status_code != 200:
                return None
            
            return response.json()

    def build_message_url(
        self,
        guild_id: str | None,
        channel_id: str,
        message_id: str,
    ) -> str:
        """Build URL to open message in Discord."""
        if guild_id:
            return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        else:
            # DM channel
            return f"https://discord.com/channels/@me/{channel_id}/{message_id}"
    
    def get_avatar_url(self, user_id: str, avatar_hash: str | None, discriminator: str = "0") -> str:
        """Get Discord user avatar URL."""
        if avatar_hash:
            ext = "gif" if avatar_hash.startswith("a_") else "png"
            return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}"
        else:
            # Default avatar based on discriminator
            default_avatar = int(discriminator) % 5 if discriminator != "0" else int(user_id) >> 22 % 6
            return f"https://cdn.discordapp.com/embed/avatars/{default_avatar}.png"
    
    def parse_webhook_event(self, event_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse Discord Gateway event into notification data.
        
        Note: Discord doesn't have traditional webhooks for user notifications.
        This would require a bot with MESSAGE_CONTENT intent, which is more complex.
        For now, we'll implement polling-based notification fetching.
        """
        event_type = event_data.get("t")
        data = event_data.get("d", {})
        
        if event_type == "MESSAGE_CREATE":
            # Skip bot messages
            if data.get("author", {}).get("bot"):
                return None
            
            channel_type = data.get("channel_type", 0)
            
            # Channel types: 0=guild text, 1=DM, 3=group DM
            if channel_type == 1:
                source = "discord_dm"
            elif channel_type == 3:
                source = "discord_dm"  # Group DM treated as DM
            else:
                source = "discord_channel"
            
            author = data.get("author", {})
            
            return {
                "source": source,
                "channel_id": data.get("channel_id"),
                "guild_id": data.get("guild_id"),
                "message_id": data.get("id"),
                "user_id": author.get("id"),
                "username": author.get("username"),
                "avatar": author.get("avatar"),
                "discriminator": author.get("discriminator", "0"),
                "text": data.get("content", ""),
                "timestamp": data.get("timestamp"),
                "mentions": [m.get("id") for m in data.get("mentions", [])],
            }
        
        return None


# Singleton instance
discord_service = DiscordService()
