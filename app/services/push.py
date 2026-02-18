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
        # Log VAPID configuration status at startup
        if self.vapid_private_key and self.vapid_public_key:
            logger.info("Push notifications enabled - VAPID keys configured")
            logger.info("VAPID public key length: %d, private key length: %d",
                       len(self.vapid_public_key), len(self.vapid_private_key))
        else:
            logger.warning("Push notifications disabled - VAPID keys not configured")
    
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
            logger.warning("VAPID keys not configured, skipping push notification for user %s", user_id)
            return 0
        
        # Get user's push subscriptions
        result = await db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        subscriptions = result.scalars().all()
        
        if not subscriptions:
            logger.warning("No push subscriptions found for user %s - they need to enable notifications in their browser", user_id)
            return 0
        
        logger.info("Sending push notification to user %s (%d subscriptions): %s", 
                   user_id, len(subscriptions), title)
        logger.info("Push body: %s", body[:100] if body else '(empty)')
        
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
        
        # Helper to ensure proper base64url padding
        def normalize_base64url(s):
            if s is None:
                return None
            # Add padding if needed
            padding = 4 - (len(s) % 4)
            if padding != 4:
                s += '=' * padding
            return s
        
        for sub in subscriptions:
            try:
                # Log key info for debugging
                logger.debug("Sending to subscription %s - endpoint: %s...", 
                           sub.id, sub.endpoint[:60] if sub.endpoint else 'none')
                logger.debug("p256dh key length: %d, auth key length: %d",
                           len(sub.p256dh_key) if sub.p256dh_key else 0,
                           len(sub.auth_key) if sub.auth_key else 0)
                
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
                logger.info("Successfully sent push to subscription %s", sub.id)
            except WebPushException as e:
                logger.error("Push notification failed for subscription %s: %s (status: %s)", 
                           sub.id, str(e), getattr(e.response, 'status_code', 'N/A') if e.response else 'N/A')
                # If subscription is expired/invalid, mark for deletion
                if e.response and e.response.status_code in (404, 410):
                    logger.info("Marking expired subscription %s for deletion", sub.id)
                    failed_subscriptions.append(sub)
            except Exception as e:
                # Catch crypto/key errors that aren't WebPushException
                logger.error("Push notification error: %s", str(e))
                logger.error("Subscription %s keys may be malformed - p256dh: %s..., auth: %s...",
                           sub.id, 
                           sub.p256dh_key[:20] if sub.p256dh_key else 'none',
                           sub.auth_key[:10] if sub.auth_key else 'none')
        
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
        workspace_name: str = None,
    ) -> int:
        """Send notification for a direct message.
        
        Returns number of push notifications sent.
        """
        # Build title with workspace name if available
        if workspace_name:
            title = f"{sender_name} ({workspace_name})"
        else:
            title = f"Message from {sender_name}"
        
        return await self.send_notification(
            db=db,
            user_id=recipient_user_id,
            title=title,
            body=message_preview[:100],
            url=f"/workspaces/{workspace_id}/channels/{channel_id}",
            tag=f"dm-{channel_id}",
        )


# Singleton instance
push_service = PushNotificationService()
