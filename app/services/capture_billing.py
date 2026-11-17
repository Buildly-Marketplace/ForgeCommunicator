"""
Access control + RevenueCat sync for the Capture app's paid features.

Flow:
  1. The app identifies the user to RevenueCat with app_user_id(user).
  2. The user buys a subscription or one-time product through the App Store / Play Store.
  3. The app calls POST /mobile/v1/billing/sync; RevenueCat also sends a webhook.
  4. Either way the server asks RevenueCat's REST API for the subscriber and stores
     the entitlement. The client's own claims are never trusted.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capture_entitlement import CaptureEntitlement
from app.models.user import User
from app.settings import settings

logger = logging.getLogger(__name__)

SOURCE_REVENUECAT = "revenuecat"
SOURCE_GRANT = "grant"


class BillingNotConfigured(Exception):
    pass


def app_user_id(user: User) -> str:
    return f"{settings.revenuecat_app_user_prefix}_{user.id}"


def user_id_from_app_user_id(value: str | None) -> int | None:
    prefix = f"{settings.revenuecat_app_user_prefix}_"
    if not value or not value.startswith(prefix):
        return None  # anonymous RevenueCat ids ($RCAnonymousID:...) or other apps
    rest = value[len(prefix):]
    return int(rest) if rest.isdigit() else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class AccessStatus:
    required: bool  # is the paywall on for this user at all?
    active: bool
    source: str | None = None  # revenuecat | grant | admin | free | None
    kind: str | None = None  # subscription | lifetime | grant | complimentary
    product_id: str | None = None
    expires_at: datetime | None = None
    will_renew: bool | None = None
    management_url: str | None = None


async def get_access(db: AsyncSession, user: User) -> AccessStatus:
    if not settings.capture_paywall_enabled:
        return AccessStatus(required=False, active=True, source="free", kind="complimentary")
    if user.is_platform_admin or settings.has_free_capture_access(user.email):
        return AccessStatus(required=False, active=True, source="admin", kind="complimentary")

    result = await db.execute(select(CaptureEntitlement).where(CaptureEntitlement.user_id == user.id))
    rows = result.scalars().all()
    now = datetime.now(timezone.utc)
    current = [r for r in rows if r.is_current(now)]
    if not current:
        latest = max(rows, key=lambda r: r.expires_at or now, default=None)
        return AccessStatus(
            required=True,
            active=False,
            source=latest.source if latest else None,
            product_id=latest.product_id if latest else None,
            expires_at=latest.expires_at if latest else None,
            management_url=latest.management_url if latest else None,
        )
    # Prefer lifetime, then the furthest expiry
    best = sorted(current, key=lambda r: (not r.is_lifetime, -(r.expires_at or now).timestamp()))[0]
    if best.source == SOURCE_GRANT:
        kind = "grant"
    else:
        kind = "lifetime" if best.is_lifetime else "subscription"
    return AccessStatus(
        required=True,
        active=True,
        source=best.source,
        kind=kind,
        product_id=best.product_id,
        expires_at=best.expires_at,
        will_renew=best.will_renew,
        management_url=best.management_url,
    )


async def fetch_subscriber(app_user: str) -> dict:
    if not settings.revenuecat_secret_api_key:
        raise BillingNotConfigured("RevenueCat is not configured on this server")
    url = f"{settings.revenuecat_api_url.rstrip('/')}/v1/subscribers/{quote(app_user, safe='')}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            url, headers={"Authorization": f"Bearer {settings.revenuecat_secret_api_key}"}
        )
        response.raise_for_status()
        return response.json().get("subscriber") or {}


def entitlement_from_subscriber(subscriber: dict, now: datetime | None = None) -> dict:
    """Reduce a RevenueCat v1 subscriber payload to the fields we store."""
    now = now or datetime.now(timezone.utc)
    ent = (subscriber.get("entitlements") or {}).get(settings.revenuecat_entitlement_id)
    if not ent:
        return {"active": False, "is_lifetime": False, "expires_at": None, "product_id": None,
                "store": None, "will_renew": None, "raw": None,
                "management_url": subscriber.get("management_url")}

    product_id = ent.get("product_identifier")
    expires_at = _parse_dt(ent.get("expires_date"))
    # Billing grace period: store keeps access while retrying the card
    grace = _parse_dt(ent.get("grace_period_expires_date"))
    if grace and (expires_at is None or grace > expires_at):
        expires_at = grace
    is_lifetime = ent.get("expires_date") is None

    store = None
    will_renew = None
    sub = (subscriber.get("subscriptions") or {}).get(product_id or "")
    if sub:
        store = sub.get("store")
        will_renew = sub.get("unsubscribe_detected_at") is None and sub.get("billing_issues_detected_at") is None
        if sub.get("refunded_at"):
            expires_at = min(expires_at or now, _parse_dt(sub["refunded_at"]) or now)
    else:
        purchases = (subscriber.get("non_subscriptions") or {}).get(product_id or "") or []
        if purchases:
            store = purchases[-1].get("store")
    return {
        "active": is_lifetime or (expires_at is not None and expires_at > now),
        "is_lifetime": is_lifetime,
        "expires_at": None if is_lifetime else expires_at,
        "product_id": product_id,
        "store": store,
        "will_renew": None if is_lifetime else will_renew,
        "management_url": subscriber.get("management_url"),
        "raw": ent,
    }


async def _upsert(db: AsyncSession, user_id: int, source: str, fields: dict) -> CaptureEntitlement:
    result = await db.execute(
        select(CaptureEntitlement).where(
            CaptureEntitlement.user_id == user_id, CaptureEntitlement.source == source
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        row = CaptureEntitlement(user_id=user_id, source=source)
        db.add(row)
    for key, value in fields.items():
        setattr(row, key, value)
    return row


async def sync_from_revenuecat(db: AsyncSession, user_id: int) -> CaptureEntitlement:
    """Pull the user's entitlement from RevenueCat and store it. Caller commits."""
    subscriber = await fetch_subscriber(f"{settings.revenuecat_app_user_prefix}_{user_id}")
    fields = entitlement_from_subscriber(subscriber)
    fields["last_synced_at"] = datetime.now(timezone.utc)
    return await _upsert(db, user_id, SOURCE_REVENUECAT, fields)


async def grant(
    db: AsyncSession, user_id: int, expires_at: datetime | None, note: str | None
) -> CaptureEntitlement:
    """Comp access (admin action). expires_at=None means no expiry."""
    return await _upsert(db, user_id, SOURCE_GRANT, {
        "active": True,
        "is_lifetime": expires_at is None,
        "expires_at": expires_at,
        "product_id": "grant",
        "note": note,
        "last_synced_at": datetime.now(timezone.utc),
    })


async def revoke_grant(db: AsyncSession, user_id: int) -> None:
    await _upsert(db, user_id, SOURCE_GRANT, {"active": False})


def user_ids_in_webhook(payload: dict) -> set[int]:
    """Every Forge user an event touches (incl. both sides of a TRANSFER)."""
    event = payload.get("event") or {}
    candidates: list[str | None] = [event.get("app_user_id"), event.get("original_app_user_id")]
    for key in ("aliases", "transferred_from", "transferred_to"):
        candidates += event.get(key) or []
    return {uid for uid in map(user_id_from_app_user_id, candidates) if uid is not None}
