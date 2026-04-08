"""
High-level regression tests for Forge Communicator.

These are simple smoke tests that verify core endpoints respond correctly
after changes. They do NOT require a database connection — they test
routing, middleware, and basic app wiring.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


# ============================================================
# Health & Meta Endpoints
# ============================================================

class TestHealthEndpoints:
    """Verify the app boots and health checks pass."""

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_healthz(self):
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_version(self):
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "build_sha" in data
        assert "cache_key" in data

    def test_manifest_json(self):
        response = client.get("/manifest.json")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "start_url" in data
        assert "icons" in data

    def test_service_worker(self):
        response = client.get("/sw.js")
        assert response.status_code == 200
        assert "javascript" in response.headers.get("content-type", "")


# ============================================================
# Auth Pages (unauthenticated)
# ============================================================

class TestAuthPages:
    """Verify auth pages render without errors."""

    def test_login_page(self):
        response = client.get("/auth/login")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_register_page(self):
        response = client.get("/auth/register")
        # 200 if open registration, redirect or 200 otherwise
        assert response.status_code in (200, 302, 307)

    def test_logout_redirects(self):
        response = client.get("/auth/logout", follow_redirects=False)
        # Should redirect to login page
        assert response.status_code in (302, 307)


# ============================================================
# Protected Pages Redirect When Unauthenticated
# ============================================================

class TestUnauthenticatedRedirects:
    """Verify protected pages redirect to login when not authenticated."""

    @pytest.mark.parametrize("path", [
        "/workspaces",
        "/profile",
        "/admin",
    ])
    def test_protected_page_redirects(self, path):
        response = client.get(path, follow_redirects=False)
        # Should redirect to login (302/307) or return 401/403
        assert response.status_code in (302, 307, 401, 403)

    def test_push_vapid_key_responds(self):
        """VAPID key is a public endpoint — should respond regardless of auth."""
        response = client.get("/push/vapid-public-key")
        # 200 if configured, 501 if not
        assert response.status_code in (200, 501)


# ============================================================
# Static Assets
# ============================================================

class TestStaticAssets:
    """Verify static files are served."""

    def test_app_js(self):
        response = client.get("/static/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers.get("content-type", "")

    def test_static_404(self):
        response = client.get("/static/nonexistent-file-xyz.js")
        assert response.status_code == 404


# ============================================================
# API / CollabHub Endpoints
# ============================================================

class TestCollabHubAPI:
    """Verify CollabHub API endpoint wiring."""

    def test_api_auth_required(self):
        """API endpoints should reject unauthenticated requests."""
        response = client.get("/api/users/me/")
        # 401/403 if no auth, or 404 if plugin disabled
        assert response.status_code in (401, 403, 404)


# ============================================================
# WebSocket Route Exists
# ============================================================

class TestWebSocket:
    """Verify the WebSocket route is registered."""

    def test_websocket_route_rejects_http(self):
        """The WS endpoint should not accept plain HTTP GET."""
        response = client.get("/ws/workspaces/1/channels/1")
        # FastAPI returns 403 or similar for non-WebSocket upgrade
        assert response.status_code in (403, 404, 426)


# ============================================================
# CORS Headers
# ============================================================

class TestCORS:
    """Verify CORS middleware is active."""

    def test_options_has_cors_headers(self):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


# ============================================================
# Slash Command Parser (unit-level sanity check)
# ============================================================

class TestSlashCommandSanity:
    """Quick sanity check that the slash command parser still works."""

    def test_decision_command_parses(self):
        from app.services.slash_commands import SlashCommandParser
        result = SlashCommandParser.parse("/decision Test decision")
        assert result is not None
        assert result.is_valid
        assert result.command == "decision"

    def test_plain_message_ignored(self):
        from app.services.slash_commands import SlashCommandParser
        result = SlashCommandParser.parse("just a regular message")
        assert result is None
