"""
Billing endpoints for the Capture mobile app.

- GET  /mobile/v1/billing/status          what the paywall should show
- POST /mobile/v1/billing/sync            re-check RevenueCat right after a purchase/restore
- POST /mobile/v1/billing/revenuecat/webhook   RevenueCat -> server (shared-secret auth)
- POST/DELETE /mobile/v1/billing/grants   platform admins comp access for a user
"""

import hmac
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db import async_session_maker
from app.deps import DBSession
from app.models.user import User
from app.routers.mobile_api import MobileUser
from app.services import capture_billing
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile/v1/billing", tags=["billing"])


class BillingStatus(BaseModel):
    required: bool
    active: bool
    source: str | None = None
    kind: str | None = None
    product_id: str | None = None
    expires_at: datetime | None = None
    will_renew: bool | None = None
    management_url: str | None = None
    app_user_id: str
    entitlement_id: str
    purchases_enabled: bool  # False if the server has no RevenueCat key (can't verify purchases)


async def _status(db, user: User) -> BillingStatus:
    access = await capture_billing.get_access(db, user)
    return BillingStatus(
        **access.__dict__,
        app_user_id=capture_billing.app_user_id(user),
        entitlement_id=settings.revenuecat_entitlement_id,
        purchases_enabled=bool(settings.revenuecat_secret_api_key),
    )


@router.get("/status", response_model=BillingStatus)
async def billing_status(user: MobileUser, db: DBSession):
    return await _status(db, user)


@router.post("/sync", response_model=BillingStatus)
async def billing_sync(user: MobileUser, db: DBSession):
    """Called by the app after a purchase or "Restore purchases"."""
    try:
        await capture_billing.sync_from_revenuecat(db, user.id)
        await db.commit()
    except capture_billing.BillingNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPError as e:
        logger.warning("RevenueCat sync failed for user %s: %s", user.id, e)
        raise HTTPException(status_code=502, detail="Couldn’t confirm the purchase right now. Try again shortly.")
    return await _status(db, user)


@router.post("/revenuecat/webhook")
async def revenuecat_webhook(request: Request):
    """RevenueCat event webhook. Every event triggers a fresh pull from RevenueCat's API."""
    expected = settings.revenuecat_webhook_auth
    provided = request.headers.get("Authorization", "")
    if provided.startswith("Bearer "):
        provided = provided[7:]
    if not expected or not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid webhook authorization")

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    synced, failed = [], []
    async with async_session_maker() as db:
        for user_id in capture_billing.user_ids_in_webhook(payload):
            if not await db.get(User, user_id):
                continue
            try:
                await capture_billing.sync_from_revenuecat(db, user_id)
                synced.append(user_id)
            except Exception as e:
                logger.warning("Webhook sync failed for user %s: %s", user_id, e)
                failed.append(user_id)
        await db.commit()
    if failed:
        # Non-2xx makes RevenueCat retry the delivery later
        raise HTTPException(status_code=502, detail=f"Sync failed for {len(failed)} user(s)")
    return {"ok": True, "synced": len(synced)}


class GrantRequest(BaseModel):
    email: str
    expires_at: datetime | None = None  # None = no expiry
    note: str | None = Field(default=None, max_length=500)


async def require_platform_admin(user: MobileUser) -> User:
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin only")
    return user


@router.post("/grants", response_model=BillingStatus)
async def grant_access(body: GrantRequest, db: DBSession, admin: User = Depends(require_platform_admin)):
    target = (await db.execute(select(User).where(User.email == body.email.lower().strip()))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    note = body.note or f"Granted by {admin.email}"
    await capture_billing.grant(db, target.id, body.expires_at, note)
    await db.commit()
    return await _status(db, target)


@router.delete("/grants/{email}", response_model=BillingStatus)
async def revoke_access(email: str, db: DBSession, admin: User = Depends(require_platform_admin)):
    target = (await db.execute(select(User).where(User.email == email.lower().strip()))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await capture_billing.revoke_grant(db, target.id)
    await db.commit()
    return await _status(db, target)
