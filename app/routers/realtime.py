"""
WebSocket realtime router for live message updates.
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db import async_session_maker
from app.models.channel import Channel
from app.models.membership import ChannelMembership, Membership
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realtime"])


# Connection manager for WebSocket connections
class ConnectionManager:
    """Manage WebSocket connections per channel."""
    
    def __init__(self):
        # channel_id -> set of WebSocket connections
        self.active_connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, channel_id: int) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections[channel_id].add(websocket)
        logger.info(f"WebSocket connected to channel {channel_id}")
    
    async def disconnect(self, websocket: WebSocket, channel_id: int) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self.active_connections[channel_id].discard(websocket)
            if not self.active_connections[channel_id]:
                del self.active_connections[channel_id]
        logger.info(f"WebSocket disconnected from channel {channel_id}")
    
    async def broadcast_to_channel(self, channel_id: int, message: dict[str, Any]) -> None:
        """Broadcast a message to all connections in a channel."""
        async with self._lock:
            connections = self.active_connections.get(channel_id, set()).copy()
        
        disconnected = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            await self.disconnect(conn, channel_id)
    
    def get_connection_count(self, channel_id: int) -> int:
        """Get number of active connections for a channel."""
        return len(self.active_connections.get(channel_id, set()))


# Global connection manager
manager = ConnectionManager()


async def verify_websocket_access(
    websocket: WebSocket,
    workspace_id: int,
    channel_id: int,
) -> User | None:
    """Verify WebSocket connection has access to channel."""
    session_token = websocket.cookies.get("session_token")
    if not session_token:
        return None
    
    async with async_session_maker() as db:
        # Get user from session
        result = await db.execute(
            select(User).where(User.session_token == session_token)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_session_valid():
            return None
        
        # Check workspace membership
        result = await db.execute(
            select(Membership).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == user.id,
            )
        )
        if not result.scalar_one_or_none():
            return None
        
        # Check channel access
        result = await db.execute(
            select(Channel).where(
                Channel.id == channel_id,
                Channel.workspace_id == workspace_id,
            )
        )
        channel = result.scalar_one_or_none()
        if not channel:
            return None
        
        # Check private channel access
        if channel.is_private:
            result = await db.execute(
                select(ChannelMembership).where(
                    ChannelMembership.channel_id == channel_id,
                    ChannelMembership.user_id == user.id,
                )
            )
            if not result.scalar_one_or_none():
                return None
        
        return user


@router.websocket("/ws/workspaces/{workspace_id}/channels/{channel_id}")
async def websocket_channel(
    websocket: WebSocket,
    workspace_id: int,
    channel_id: int,
):
    """WebSocket endpoint for real-time channel updates."""
    # Verify access
    user = await verify_websocket_access(websocket, workspace_id, channel_id)
    if not user:
        await websocket.close(code=4003)
        return
    
    # Connect
    await manager.connect(websocket, channel_id)
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "channel_id": channel_id,
            "user_id": user.id,
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()
                
                # Handle ping/pong for keepalive
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
                # Handle typing indicator
                elif data.get("type") == "typing":
                    await manager.broadcast_to_channel(channel_id, {
                        "type": "typing",
                        "user_id": user.id,
                        "user_name": user.display_name,
                    })
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue
    
    finally:
        await manager.disconnect(websocket, channel_id)


async def broadcast_new_message(
    channel_id: int,
    message_html: str,
    message_id: int,
    user_id: int,
    user_name: str,
) -> None:
    """Broadcast a new message to channel subscribers."""
    await manager.broadcast_to_channel(channel_id, {
        "type": "new_message",
        "message_id": message_id,
        "user_id": user_id,
        "user_name": user_name,
        "html": message_html,
    })


async def broadcast_message_update(
    channel_id: int,
    message_id: int,
    message_html: str,
) -> None:
    """Broadcast a message update to channel subscribers."""
    await manager.broadcast_to_channel(channel_id, {
        "type": "message_updated",
        "message_id": message_id,
        "html": message_html,
    })


async def broadcast_message_delete(
    channel_id: int,
    message_id: int,
) -> None:
    """Broadcast a message deletion to channel subscribers."""
    await manager.broadcast_to_channel(channel_id, {
        "type": "message_deleted",
        "message_id": message_id,
    })
