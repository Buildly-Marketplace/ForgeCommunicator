"""
Push notification service using web-push.
"""

import json
import logging
from typing import Optional

from pywebpush import webpush, WebPushException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.settings import settings

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Service for sending web push notifications."""
    
    def __init__(self):
        self.vapid_private_key = settings.vapid_private_key
        self.vapid_public_key = settings.vapid_public_key
        self.vapid_claims = {
            "sub": f"mailto:{settings.vapid_contact_email}"
        }
    
    async def send_notification(
        self,
        db: AsyncSession,
        user_id: int,
        title: str,
        body: str,
        url: Optional[str] = None,
        icon: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> int:
        """Send push notification to all subscriptions for a user.
        
        Returns the number of successful notifications sent.
        """
        if not self.vapid_private_key:
            logger.warning("VAPID keys not configured, skipping push notification")
            return 0
        
        # Get user's push subscriptions
        result = await db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        subscriptions = result.scalars().all()
        
        if not subscriptions:
            return 0
        
        # Build notification payload
        payload = {
            "title": title,
            "body": body,
            "icon": icon or "/static/icons/icon-192x192.png",
            "badge": "/static/icons/icon-96x96.png",
            "tag": tag,
            "silent": False,  # Ensure sound plays
            "requireInteraction": False,
            "data": {
                "url": url or "/",
                "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            }
        }
        
        sent_count = 0
        failed_subscriptions = []
        
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {
                            "p256dh": sub.p256dh_key,
                            "auth": sub.auth_key,
                        }
                    },
                    data=json.dumps(payload),
                    vapid_private_key=self.vapid_private_key,
                    vapid_claims=self.vapid_claims,
                )
                sent_count += 1
            except WebPushException as e:
                logger.error(f"Push notification failed: {e}")
                # If subscription is expired/invalid, mark for deletion
                if e.response and e.response.status_code in (404, 410):
                    failed_subscriptions.append(sub)
        
        # Clean up invalid subscriptions
        for sub in failed_subscriptions:
            await db.delete(sub)
        
        if failed_subscriptions:
            await db.commit()
        
        return sent_count
    
    async def notify_mention(
        self,
        db: AsyncSession,
        mentioned_user_id: int,
        sender_name: str,
        channel_name: str,
        workspace_id: int,
        channel_id: int,
        message_preview: str,
    ):
        """Send notification for a @mention."""
        await self.send_notification(
            db=db,
            user_id=mentioned_user_id,
            title=f"{sender_name} mentioned you in {channel_name}",
            body=message_preview[:100],
            url=f"/workspaces/{workspace_id}/channels/{channel_id}",
            tag=f"mention-{channel_id}",
        )
    
    async def notify_dm(
        self,
        db: AsyncSession,
        recipient_user_id: int,
        sender_name: str,
        workspace_id: int,
        channel_id: int,
        message_preview: str,
    ):
        """Send notification for a direct message."""
        await self.send_notification(
            db=db,
            user_id=recipient_user_id,
            title=f"New message from {sender_name}",
            body=message_preview[:100],
            url=f"/workspaces/{workspace_id}/channels/{channel_id}",
            tag=f"dm-{channel_id}",
        )


# Singleton instance
push_service = PushNotificationService()
