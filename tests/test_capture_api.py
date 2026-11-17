"""
Tests for the Forge Capture flow (app/routers/capture_api.py, app/services/idea_refiner.py).

The refiner tests are pure and always run. The API tests drive the real app
against PostgreSQL and are skipped unless one is reachable at DATABASE_URL, e.g.

    DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5432/forge_test pytest tests/test_capture_api.py
"""

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services import idea_refiner


def make_idea(**kw):
    defaults = dict(id=1, kind="idea", title=None, body="Let users export reports as CSV",
                    context=None, attachments=None, product=None, workspace_id=1)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Refiner (pure)
# ---------------------------------------------------------------------------


class TestRefiner:
    def test_extract_json_handles_code_fence_and_prose(self):
        text = 'Sure! Here you go:\n```json\n{"title": "x", "items": []}\n```\nThanks'
        assert idea_refiner._extract_json(text) == {"title": "x", "items": []}
        assert idea_refiner._extract_json('blah {"a": 1} blah') == {"a": 1}
        with pytest.raises(ValueError):
            idea_refiner._extract_json("no json here")

    def test_normalize_clamps_bad_values(self):
        data = {
            "title": "CSV export",
            "items": [
                {"type": "weird", "title": "Export button", "priority": "urgent!!",
                 "estimate": {"points": 4, "human_hours": "6", "ai_hours": -2, "confidence": "?"},
                 "builder": "robot", "acceptance_criteria": "single string"},
                {"title": ""},  # dropped
                "garbage",  # dropped
            ],
            "questions": ["Which columns?", ""],
        }
        out = idea_refiner.normalize_breakdown(data, make_idea(), "test")
        assert len(out["items"]) == 1
        item = out["items"][0]
        assert item["type"] == "feature"
        assert item["priority"] == "medium"
        assert item["builder"] == "pair"
        assert item["estimate"]["points"] in (3, 5)  # nearest Fibonacci to 4
        assert item["estimate"]["human_hours"] == 6.0
        assert item["estimate"]["ai_hours"] == 2.0  # negative -> default human/3
        assert item["estimate"]["confidence"] == "medium"
        assert item["acceptance_criteria"] == ["single string"]
        assert item["selected"] is True
        assert out["questions"] == ["Which columns?"]
        assert out["totals"]["human_hours"] == 6.0

    def test_normalize_bug_defaults_to_issue(self):
        out = idea_refiner.normalize_breakdown({"items": [{"title": "Crash"}]}, make_idea(kind="bug"), "t")
        assert out["items"][0]["type"] == "issue"

    def test_normalize_rejects_empty(self):
        with pytest.raises(ValueError):
            idea_refiner.normalize_breakdown({"items": []}, make_idea(), "t")

    def test_heuristic_breakdown(self):
        out = idea_refiner.heuristic_breakdown(make_idea(kind="bug", body="App crashes on login\nmore detail"))
        assert out["engine"] == "heuristic"
        assert out["items"][0]["type"] == "issue"
        assert out["items"][0]["title"] == "App crashes on login"
        assert out["items"][0]["priority"] == "high"

    def test_totals_respect_selection(self):
        items = [
            {"selected": True, "estimate": {"points": 3, "human_hours": 6, "ai_hours": 2}},
            {"selected": False, "estimate": {"points": 8, "human_hours": 20, "ai_hours": 5}},
        ]
        assert idea_refiner.compute_totals(items) == {"points": 3, "human_hours": 6, "ai_hours": 2}

    def test_markdown_includes_estimates_and_attachments(self):
        idea = make_idea(attachments=[{"url": "https://cdn/x.png", "filename": "x.png"}],
                         context={"app_name": "Labs", "os": "iOS 19"})
        breakdown = idea_refiner.heuristic_breakdown(idea)
        md = idea_refiner.render_item_markdown(breakdown["items"][0], idea, breakdown)
        assert "Story points" in md and "AI agent" in md
        assert "![x.png](https://cdn/x.png)" in md
        assert "app_name: Labs" in md
        assert "> Let users export reports as CSV" in md

    def test_prompt_mentions_product_and_context(self):
        idea = make_idea(context={"app_name": "Foo"}, attachments=[{"filename": "s.png"}])
        prompt = idea_refiner.build_user_prompt(idea, "Labs", "Product mgmt")
        assert "Product: Labs" in prompt and "app_name=Foo" in prompt and "s.png" in prompt


# ---------------------------------------------------------------------------
# API (needs PostgreSQL)
# ---------------------------------------------------------------------------


def _db_available() -> bool:
    if "DATABASE_URL" not in os.environ:
        return False
    try:
        import asyncpg

        async def ping():
            url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
            conn = await asyncpg.connect(url, timeout=3)
            await conn.close()

        asyncio.run(ping())
        return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available at DATABASE_URL")


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:  # runs lifespan -> create_all
        yield c


@pytest.fixture(scope="module")
def seeded(client):
    """A user (logged in via the mobile API), a workspace and a product."""
    from app.db import async_session_maker
    from app.models.membership import Membership, MembershipRole
    from app.models.product import Product
    from app.models.workspace import Workspace

    suffix = os.urandom(4).hex()
    email = f"capture-{suffix}@example.com"
    r = client.post("/mobile/v1/auth/register",
                    json={"email": email, "password": "Sup3r-secret-pw!", "display_name": "Cap"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    user_id = r.json()["user"]["id"]

    async def seed():
        async with async_session_maker() as db:
            ws = Workspace(name=f"Capture WS {suffix}", slug=f"capture-{suffix}")
            db.add(ws)
            await db.flush()
            db.add(Membership(workspace_id=ws.id, user_id=user_id, role=MembershipRole.OWNER))
            other = Workspace(name=f"Other {suffix}", slug=f"other-{suffix}")
            db.add(other)
            await db.flush()
            product = Product(workspace_id=ws.id, name="Labs Web", buildly_product_uuid="11111111-2222-3333-4444-555555555555")
            db.add(product)
            await db.commit()
            return ws.id, other.id, product.id

    # Run on the app's event loop — the DB pool is bound to it
    ws_id, other_ws_id, product_id = client.portal.call(seed)
    return SimpleNamespace(headers={"Authorization": f"Bearer {token}"},
                           ws_id=ws_id, other_ws_id=other_ws_id, product_id=product_id)


@needs_db
class TestCaptureAPI:
    def test_requires_auth(self, client):
        assert client.get("/mobile/v1/ideas").status_code == 401

    def test_bootstrap_and_products(self, client, seeded):
        r = client.get("/mobile/v1/capture/bootstrap", headers=seeded.headers)
        assert r.status_code == 200
        assert seeded.ws_id in [w["id"] for w in r.json()["workspaces"]]

        r = client.get(f"/mobile/v1/workspaces/{seeded.ws_id}/products", headers=seeded.headers)
        assert r.status_code == 200
        assert r.json()[0]["labs_uuid"] == "11111111-2222-3333-4444-555555555555"

    def test_cannot_capture_into_foreign_workspace(self, client, seeded):
        r = client.post("/mobile/v1/ideas", headers=seeded.headers,
                        data={"workspace_id": seeded.other_ws_id, "body": "nope"})
        assert r.status_code == 403

    def test_empty_capture_rejected(self, client, seeded):
        r = client.post("/mobile/v1/ideas", headers=seeded.headers,
                        data={"workspace_id": seeded.ws_id, "body": "  "})
        assert r.status_code == 422

    def test_full_flow_refine_edit_submit(self, client, seeded):
        # 1. capture (with client_id for idempotency)
        form = {"workspace_id": seeded.ws_id, "product_id": seeded.product_id, "kind": "idea",
                "body": "Let users export their backlog as CSV from the product page",
                "client_id": f"c-{os.urandom(4).hex()}",
                "context": json.dumps({"app_name": "Labs", "os": "iOS"})}
        r = client.post("/mobile/v1/ideas", headers=seeded.headers, data=form)
        assert r.status_code == 201, r.text
        idea = r.json()
        assert idea["status"] == "draft" and idea["product_name"] == "Labs Web"
        assert idea["context"]["app_name"] == "Labs"

        r2 = client.post("/mobile/v1/ideas", headers=seeded.headers, data=form)
        assert r2.json()["id"] == idea["id"]  # offline retry doesn't duplicate

        # 2. refine with a fake AI
        ai_json = {
            "title": "CSV backlog export",
            "summary": "Export backlog to CSV",
            "items": [
                {"type": "feature", "title": "CSV export endpoint", "priority": "medium",
                 "estimate": {"points": 3, "human_hours": 6, "ai_hours": 1.5, "confidence": "high"},
                 "builder": "ai", "acceptance_criteria": ["Returns CSV"]},
                {"type": "feature", "title": "Export button UI", "priority": "low",
                 "estimate": {"points": 2, "human_hours": 3, "ai_hours": 1, "confidence": "medium"},
                 "builder": "dev"},
            ],
            "questions": ["Which columns?"],
        }
        fake = AsyncMock()
        fake.chat.return_value = SimpleNamespace(content="```json\n" + json.dumps(ai_json) + "\n```")
        with patch.object(idea_refiner, "_resolve_provider", AsyncMock(return_value=(fake, "anthropic:test"))):
            r = client.post(f"/mobile/v1/ideas/{idea['id']}/refine", headers=seeded.headers)
        assert r.status_code == 200, r.text
        refined = r.json()
        assert refined["status"] == "refined"
        assert refined["title"] == "CSV backlog export"
        assert refined["breakdown"]["engine"] == "anthropic:test"
        assert refined["breakdown"]["totals"]["points"] == 5

        # 3. deselect the UI item, flip builder on the first
        r = client.patch(f"/mobile/v1/ideas/{idea['id']}", headers=seeded.headers,
                         json={"items": [{"id": "item-2", "selected": False},
                                         {"id": "item-1", "builder": "pair"}]})
        assert r.status_code == 200, r.text
        bd = r.json()["breakdown"]
        assert bd["items"][1]["selected"] is False
        assert bd["items"][0]["builder"] == "pair"
        assert bd["totals"]["points"] == 3

        # 4. submit — Labs push mocked
        with patch("app.services.labs_sync.LabsSyncService.create_backlog_item",
                   AsyncMock(return_value={"uuid": "labs-item-1"})) as push, \
             patch("app.routers.capture_api.get_workspace_labs_token",
                   AsyncMock(return_value=("tok", "user_oauth"))):
            r = client.post(f"/mobile/v1/ideas/{idea['id']}/submit", headers=seeded.headers, json={})
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["labs_pushed"] == 1 and result["warnings"] == []
        assert len(result["created"]) == 1
        assert result["created"][0]["labs_uuid"] == "labs-item-1"
        assert push.await_args.kwargs["product_uuid"] == "11111111-2222-3333-4444-555555555555"
        assert push.await_args.kwargs["item_type"] == "story"
        assert "Story points" in push.await_args.kwargs["description"]
        assert result["idea"]["status"] == "submitted"

        # Artifact shows up in the product backlog
        r = client.get(f"/mobile/v1/products/{seeded.product_id}/items", headers=seeded.headers)
        assert "CSV export endpoint" in [i["title"] for i in r.json()]

        # Can't submit twice
        r = client.post(f"/mobile/v1/ideas/{idea['id']}/submit", headers=seeded.headers, json={})
        assert r.status_code == 409

    def test_one_tap_submit_without_ai_or_labs(self, client, seeded):
        r = client.post("/mobile/v1/ideas", headers=seeded.headers,
                        data={"workspace_id": seeded.ws_id, "kind": "bug", "body": "Login button does nothing"})
        idea_id = r.json()["id"]
        with patch.object(idea_refiner, "_resolve_provider", AsyncMock(return_value=(None, "heuristic"))), \
             patch("app.routers.capture_api.get_workspace_labs_token", AsyncMock(return_value=(None, "none"))):
            r = client.post(f"/mobile/v1/ideas/{idea_id}/submit", headers=seeded.headers, json={})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["created"][0]["type"] == "issue"
        assert body["labs_pushed"] == 0
        assert any("not connected" in w for w in body["warnings"])

    def test_ideas_are_private_to_author(self, client, seeded):
        r = client.post("/mobile/v1/auth/register",
                        json={"email": f"other-{os.urandom(4).hex()}@example.com",
                              "password": "Sup3r-secret-pw!", "display_name": "Other"})
        other = {"Authorization": f"Bearer {r.json()['token']}"}
        r = client.post("/mobile/v1/ideas", headers=seeded.headers,
                        data={"workspace_id": seeded.ws_id, "body": "secret idea"})
        assert client.get(f"/mobile/v1/ideas/{r.json()['id']}", headers=other).status_code == 404

    def test_oauth_start_scheme(self, client):
        with patch("app.services.auth_providers.get_oauth_provider") as gp:
            gp.return_value = SimpleNamespace(
                authorization_url="https://labs.example/oauth/authorize",
                get_authorization_params=lambda state: {"state": state, "client_id": "x"},
            )
            r = client.get("/mobile/v1/auth/oauth/buildly/start?app_scheme=forgecapture")
            assert r.status_code == 200
            assert r.json()["state"].startswith("forgecapture.")
            assert client.get("/mobile/v1/auth/oauth/buildly/start?app_scheme=evil").status_code == 400
