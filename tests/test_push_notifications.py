import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.settings import settings

client = TestClient(app)

@pytest.fixture(scope="module")
def test_user_token():
    # TODO: Replace with actual login or token fixture
    return "testtoken"


def test_vapid_public_key():
    """Test that the VAPID public key endpoint returns a key if configured."""
    response = client.get("/push/vapid-public-key")
    if settings.vapid_public_key:
        assert response.status_code == 200
        assert "publicKey" in response.json()
    else:
        assert response.status_code == 501


def test_push_subscribe_and_unsubscribe(test_user_token):
    """Test subscribing and unsubscribing to push notifications."""
    # Simulate login (replace with real auth if needed)
    headers = {"Authorization": f"Bearer {test_user_token}"}
    # Fake subscription data
    data = {
        "endpoint": "https://example.com/fake-endpoint",
        "p256dh": "fakep256dhkey",
        "auth": "fakeauthkey"
    }
    # Subscribe
    response = client.post("/push/subscribe", data=data, headers=headers)
    assert response.status_code in (200, 501)  # 501 if not configured
    # Unsubscribe
    response = client.post("/push/unsubscribe", data={"endpoint": data["endpoint"]}, headers=headers)
    assert response.status_code in (200, 404, 501)


def test_send_test_notification(test_user_token):
    """Test sending a test push notification."""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    response = client.post("/push/test", headers=headers)
    assert response.status_code in (200, 404, 501)

