"""
Tests for the Capture paywall (app/services/capture_billing.py, app/routers/billing_api.py).

Parsing tests always run; API tests need PostgreSQL at DATABASE_URL (see test_capture_api.py).
"""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import capture_billing
from app.settings import settings
from tests.test_capture_api import client, needs_db  # noqa: F401  (shared fixtures)

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
ENT = settings.revenuecat_entitlement_id


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def subscriber(entitlement: dict | None = None, subscriptions=None, non_subscriptions=None):
    return {
        "entitlements": {ENT: entitlement} if entitlement else {},
        "subscriptions": subscriptions or {},
        "non_subscriptions": non_subscriptions or {},
        "management_url": "https://apps.apple.com/account/subscriptions",
    }


# ---------------------------------------------------------------------------
# RevenueCat payload parsing (pure)
# ---------------------------------------------------------------------------


class TestEntitlementParsing:
    def test_active_subscription(self):
        exp = NOW + timedelta(days=20)
        out = capture_billing.entitlement_from_subscriber(subscriber(
            {"expires_date": iso(exp), "product_identifier": "capture_monthly"},
            subscriptions={"capture_monthly": {"store": "app_store", "unsubscribe_detected_at": None,
                                               "billing_issues_detected_at": None}},
        ), now=NOW)
        assert out["active"] and not out["is_lifetime"]
        assert out["expires_at"] == exp
        assert out["store"] == "app_store" and out["will_renew"] is True
        assert out["management_url"].startswith("https://")

    def test_expired_subscription(self):
        out = capture_billing.entitlement_from_subscriber(subscriber(
            {"expires_date": iso(NOW - timedelta(days=1)), "product_identifier": "capture_monthly"}), now=NOW)
        assert out["active"] is False

    def test_cancelled_but_not_yet_expired_stays_active(self):
        out = capture_billing.entitlement_from_subscriber(subscriber(
            {"expires_date": iso(NOW + timedelta(days=3)), "product_identifier": "m"},
            subscriptions={"m": {"store": "play_store", "unsubscribe_detected_at": iso(NOW)}},
        ), now=NOW)
        assert out["active"] is True and out["will_renew"] is False

    def test_grace_period_extends_access(self):
        out = capture_billing.entitlement_from_subscriber(subscriber(
            {"expires_date": iso(NOW - timedelta(hours=1)),
             "grace_period_expires_date": iso(NOW + timedelta(days=6)), "product_identifier": "m"}), now=NOW)
        assert out["active"] is True

    def test_refund_ends_access(self):
        out = capture_billing.entitlement_from_subscriber(subscriber(
            {"expires_date": iso(NOW + timedelta(days=20)), "product_identifier": "m"},
            subscriptions={"m": {"store": "app_store", "refunded_at": iso(NOW - timedelta(hours=1))}},
        ), now=NOW)
        assert out["active"] is False

    def test_lifetime_purchase(self):
        out = capture_billing.entitlement_from_subscriber(subscriber(
            {"expires_date": None, "product_identifier": "capture_lifetime"},
            non_subscriptions={"capture_lifetime": [{"store": "play_store"}]},
        ), now=NOW)
        assert out["active"] and out["is_lifetime"] and out["expires_at"] is None
        assert out["store"] == "play_store"

    def test_no_entitlement(self):
        out = capture_billing.entitlement_from_subscriber(subscriber(None), now=NOW)
        assert out["active"] is False

    def test_app_user_id_round_trip_and_webhook_ids(self):
        assert capture_billing.app_user_id(SimpleNamespace(id=42)) == "forge_42"
        assert capture_billing.user_id_from_app_user_id("forge_42") == 42
        assert capture_billing.user_id_from_app_user_id("$RCAnonymousID:abc") is None
        assert capture_billing.user_id_from_app_user_id("forge_x") is None
        payload = {"event": {"type": "TRANSFER", "transferred_from": ["forge_1", "$RCAnonymousID:z"],
                             "transferred_to": ["forge_2"]}}
        assert capture_billing.user_ids_in_webhook(payload) == {1, 2}


# ---------------------------------------------------------------------------
# API (needs PostgreSQL)
# ---------------------------------------------------------------------------


def register(client):  # noqa: F811
    r = client.post("/mobile/v1/auth/register", json={
        "email": f"bill-{os.urandom(4).hex()}@example.com", "password": "Sup3r-secret-pw!", "display_name": "B"})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]


def workspace_for(client, user_id):  # noqa: F811
    from app.db import async_session_maker
    from app.models.membership import Membership, MembershipRole
    from app.models.product import Product
    from app.models.workspace import Workspace

    async def seed():
        async with async_session_maker() as db:
            suffix = os.urandom(4).hex()
            ws = Workspace(name=f"Bill {suffix}", slug=f"bill-{suffix}")
            db.add(ws)
            await db.flush()
            db.add(Membership(workspace_id=ws.id, user_id=user_id, role=MembershipRole.OWNER))
            product = Product(workspace_id=ws.id, name="P")
            db.add(product)
            await db.commit()
            return ws.id, product.id

    return client.portal.call(seed)


LIFETIME = subscriber({"expires_date": None, "product_identifier": "capture_lifetime"},
                      non_subscriptions={"capture_lifetime": [{"store": "app_store"}]})


@needs_db
class TestPaywallAPI:
    def test_unpaid_user_can_browse_but_not_save(self, client):  # noqa: F811
        headers, user = register(client)
        ws, product = workspace_for(client, user["id"])

        status = client.get("/mobile/v1/billing/status", headers=headers).json()
        assert status["required"] is True and status["active"] is False
        assert status["app_user_id"] == f"forge_{user['id']}"

        r = client.post("/mobile/v1/ideas", headers=headers, data={"workspace_id": ws, "product_id": product, "body": "x"})
        assert r.status_code == 402
        assert r.json()["detail"]["code"] == "subscription_required"
        assert client.get("/mobile/v1/ideas", headers=headers).status_code == 200
        assert client.get(f"/mobile/v1/workspaces/{ws}/products", headers=headers).status_code == 200

    def test_purchase_sync_unlocks(self, client):  # noqa: F811
        headers, user = register(client)
        ws, product = workspace_for(client, user["id"])
        with patch.object(settings, "revenuecat_secret_api_key", "sk_test"), \
             patch.object(capture_billing, "fetch_subscriber", AsyncMock(return_value=LIFETIME)) as fetch:
            r = client.post("/mobile/v1/billing/sync", headers=headers)
        assert r.status_code == 200, r.text
        assert fetch.await_args.args[0] == f"forge_{user['id']}"
        assert r.json()["active"] is True and r.json()["kind"] == "lifetime"
        r = client.post("/mobile/v1/ideas", headers=headers, data={"workspace_id": ws, "product_id": product, "body": "now paid"})
        assert r.status_code == 201

    def test_sync_without_revenuecat_configured(self, client):  # noqa: F811
        headers, _ = register(client)
        with patch.object(settings, "revenuecat_secret_api_key", None):
            assert client.post("/mobile/v1/billing/sync", headers=headers).status_code == 503

    def test_webhook_auth_and_expiry(self, client):  # noqa: F811
        headers, user = register(client)
        app_user = f"forge_{user['id']}"
        event = {"event": {"type": "INITIAL_PURCHASE", "app_user_id": app_user}}
        with patch.object(settings, "revenuecat_webhook_auth", "hook-secret"):
            assert client.post("/mobile/v1/billing/revenuecat/webhook", json=event).status_code == 401
            assert client.post("/mobile/v1/billing/revenuecat/webhook", json=event,
                               headers={"Authorization": "wrong"}).status_code == 401

            active = subscriber({"expires_date": iso(datetime.now(timezone.utc) + timedelta(days=30)),
                                 "product_identifier": "capture_monthly"},
                                subscriptions={"capture_monthly": {"store": "play_store"}})
            with patch.object(settings, "revenuecat_secret_api_key", "sk_test"), \
                 patch.object(capture_billing, "fetch_subscriber", AsyncMock(return_value=active)):
                r = client.post("/mobile/v1/billing/revenuecat/webhook", json=event,
                                headers={"Authorization": "Bearer hook-secret"})
            assert r.status_code == 200 and r.json()["synced"] == 1
            s = client.get("/mobile/v1/billing/status", headers=headers).json()
            assert s["active"] and s["kind"] == "subscription"

            expired = subscriber({"expires_date": iso(datetime.now(timezone.utc) - timedelta(minutes=1)),
                                  "product_identifier": "capture_monthly"})
            with patch.object(settings, "revenuecat_secret_api_key", "sk_test"), \
                 patch.object(capture_billing, "fetch_subscriber", AsyncMock(return_value=expired)):
                client.post("/mobile/v1/billing/revenuecat/webhook",
                            json={"event": {"type": "EXPIRATION", "app_user_id": app_user}},
                            headers={"Authorization": "hook-secret"})
            assert client.get("/mobile/v1/billing/status", headers=headers).json()["active"] is False

    def test_webhook_ignores_unknown_users(self, client):  # noqa: F811
        with patch.object(settings, "revenuecat_webhook_auth", "s"):
            r = client.post("/mobile/v1/billing/revenuecat/webhook",
                            json={"event": {"app_user_id": "forge_999999999"}}, headers={"Authorization": "s"})
        assert r.status_code == 200 and r.json()["synced"] == 0

    def test_paywall_off_and_comped_emails(self, client):  # noqa: F811
        headers, user = register(client)
        with patch.object(settings, "capture_paywall_enabled", False):
            assert client.get("/mobile/v1/billing/status", headers=headers).json()["active"] is True
        with patch.object(settings, "capture_free_emails", f"x@y.z, {user['email'].upper()}"):
            s = client.get("/mobile/v1/billing/status", headers=headers).json()
            assert s["active"] is True and s["required"] is False

    def test_admin_grants(self, client):  # noqa: F811
        headers, user = register(client)
        admin_headers, admin = register(client)
        body = {"email": user["email"], "note": "beta tester"}
        assert client.post("/mobile/v1/billing/grants", headers=admin_headers, json=body).status_code == 403

        from app.db import async_session_maker
        from app.models.user import User

        async def promote():
            async with async_session_maker() as db:
                (await db.get(User, admin["id"])).is_platform_admin = True
                await db.commit()

        client.portal.call(promote)
        r = client.post("/mobile/v1/billing/grants", headers=admin_headers, json=body)
        assert r.status_code == 200 and r.json()["kind"] == "grant"
        assert client.get("/mobile/v1/billing/status", headers=headers).json()["active"] is True
        r = client.delete(f"/mobile/v1/billing/grants/{user['email']}", headers=admin_headers)
        assert r.json()["active"] is False
