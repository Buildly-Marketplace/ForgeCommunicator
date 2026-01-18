"""
Push notifications router for web push subscriptions.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select

from app.deps import CurrentUser, DBSession
from app.models.push_subscription import PushSubscription
from app.settings import settings

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Get the VAPID public key for push subscription."""
    if not settings.vapid_public_key:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Push notifications not configured"
        )
    return JSONResponse({"publicKey": settings.vapid_public_key})


@router.post("/subscribe")
async def subscribe(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    endpoint: Annotated[str, Form()],
    p256dh: Annotated[str, Form()],
    auth: Annotated[str, Form()],
):
    """Subscribe to push notifications."""
    if not settings.vapid_public_key:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Push notifications not configured"
        )
    
    # Check if subscription already exists
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == endpoint,
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update keys in case they changed
        existing.p256dh_key = p256dh
        existing.auth_key = auth
        existing.user_agent = request.headers.get("User-Agent")
    else:
        # Create new subscription
        subscription = PushSubscription(
            user_id=user.id,
            endpoint=endpoint,
            p256dh_key=p256dh,
            auth_key=auth,
            user_agent=request.headers.get("User-Agent"),
        )
        db.add(subscription)
    
    await db.commit()
    
    return JSONResponse({"status": "subscribed"})


@router.post("/unsubscribe")
async def unsubscribe(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    endpoint: Annotated[str, Form()],
):
    """Unsubscribe from push notifications."""
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == endpoint,
        )
    )
    subscription = result.scalar_one_or_none()
    
    if subscription:
        await db.delete(subscription)
        await db.commit()
    
    return JSONResponse({"status": "unsubscribed"})
