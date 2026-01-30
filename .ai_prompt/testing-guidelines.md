# Testing Guidelines for Buildly Forge

All code changes in Forge Communicator should include appropriate tests. This document defines testing requirements and patterns that AI assistants should follow.

## Testing Requirements

### When Tests Are Required

| Change Type | Test Required |
|-------------|---------------|
| New endpoint | ✅ Yes |
| New service method | ✅ Yes |
| Bug fix | ✅ Yes (regression test) |
| New model | ✅ Yes (basic CRUD) |
| Refactoring | ✅ Yes (preserve existing) |
| Template changes | ⚠️ Optional (E2E if complex) |
| Config changes | ⚠️ Optional |

### Coverage Targets

| Component | Minimum Coverage |
|-----------|-----------------|
| Services | 80% |
| Routers | 70% |
| Models | 60% |
| Overall | 70% |

## Test File Organization

```
tests/
├── conftest.py                    # Shared fixtures
├── test_slash_commands.py         # Unit tests for services
├── test_push_notifications.py     # Endpoint tests
├── test_in_app_notifications.py   # Integration tests
└── integration/                   # Complex integration tests
    ├── test_auth_flow.py
    └── test_workspace_lifecycle.py
```

## Writing Tests

### Test Naming

Use descriptive names that explain the scenario:

```python
# ✅ Good - describes what is being tested and expected outcome
def test_login_with_invalid_password_returns_401():
def test_slash_command_decision_creates_artifact():
def test_user_cannot_access_other_workspace():

# ❌ Bad - too vague
def test_login():
def test_slash_command():
def test_user():
```

### Test Structure (Arrange-Act-Assert)

```python
def test_user_can_join_workspace_with_valid_invite():
    # Arrange
    workspace = create_test_workspace(invite_code="ABC123")
    user = create_test_user()
    
    # Act
    result = workspace_service.join_with_invite(user, "ABC123")
    
    # Assert
    assert result.success
    assert user in workspace.members
```

### Unit Tests

Test individual functions/methods in isolation:

```python
# tests/test_slash_commands.py

import pytest
from app.services.slash_commands import parse_slash_command, SlashCommandType

class TestParseSlashCommand:
    """Test slash command parsing."""
    
    def test_decision_command(self):
        """Test /decision command parsing."""
        result = parse_slash_command("/decision Use PostgreSQL")
        
        assert result is not None
        assert result["type"] == SlashCommandType.ARTIFACT
        assert result["title"] == "Use PostgreSQL"
    
    def test_unknown_command_returns_none(self):
        """Unknown commands should return None."""
        result = parse_slash_command("/unknown test")
        assert result is None
    
    def test_regular_message_returns_none(self):
        """Non-command messages should return None."""
        result = parse_slash_command("Hello world")
        assert result is None
    
    @pytest.mark.parametrize("command,expected", [
        ("/DECISION Test", SlashCommandType.ARTIFACT),
        ("/Decision Test", SlashCommandType.ARTIFACT),
        ("/decision Test", SlashCommandType.ARTIFACT),
    ])
    def test_case_insensitive(self, command, expected):
        """Commands should be case-insensitive."""
        result = parse_slash_command(command)
        assert result["type"] == expected
```

### API Endpoint Tests

Test HTTP endpoints using FastAPI TestClient:

```python
# tests/test_push_notifications.py

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.settings import settings

client = TestClient(app)

def test_vapid_public_key_returns_key_when_configured():
    """VAPID endpoint returns public key if configured."""
    response = client.get("/push/vapid-public-key")
    
    if settings.vapid_public_key:
        assert response.status_code == 200
        data = response.json()
        assert "publicKey" in data
    else:
        assert response.status_code == 501

def test_subscribe_requires_authentication():
    """Subscribe endpoint requires user authentication."""
    response = client.post("/push/subscribe", data={
        "endpoint": "https://example.com/push",
        "p256dh": "key",
        "auth": "auth"
    })
    
    # Should redirect to login or return 401
    assert response.status_code in (302, 401)
```

### Async Tests

Use `pytest.mark.asyncio` for async tests:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_user_service_creates_user(db_session: AsyncSession):
    """UserService.create() should create a new user."""
    from app.services.user_service import user_service
    
    user = await user_service.create(
        db_session,
        email="test@example.com",
        display_name="Test User"
    )
    
    assert user.id is not None
    assert user.email == "test@example.com"
```

### Fixtures

Define reusable fixtures in `conftest.py`:

```python
# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User, AuthProvider
from app.services.password import hash_password

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)

@pytest.fixture
def test_user():
    """Create a test user fixture."""
    return User(
        email="test@example.com",
        display_name="Test User",
        hashed_password=hash_password("password123"),
        auth_provider=AuthProvider.LOCAL,
        is_active=True
    )

@pytest.fixture
def authenticated_client(client, test_user):
    """Create client with authenticated session."""
    response = client.post("/auth/login", data={
        "email": test_user.email,
        "password": "password123"
    }, follow_redirects=False)
    return client
```

### Mocking External Services

Mock external dependencies:

```python
from unittest.mock import patch, AsyncMock

@patch("app.services.push.webpush")
def test_push_notification_sends_to_endpoint(mock_webpush):
    """Push service should call webpush with correct params."""
    mock_webpush.return_value = None
    
    push_service.send(subscription, "Test Title", "Test Body")
    
    mock_webpush.assert_called_once()
    call_args = mock_webpush.call_args
    assert "Test Title" in str(call_args)

@patch("app.services.buildly_client.httpx.AsyncClient")
async def test_labs_sync_handles_api_error(mock_client):
    """Labs sync should handle API errors gracefully."""
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    result = await labs_sync.sync_products(workspace_id)
    
    assert result.success is False
    assert "API Error" in result.error
```

## Test Patterns

### Testing Error Cases

```python
def test_login_with_wrong_password():
    """Login with wrong password should fail."""
    response = client.post("/auth/login", data={
        "email": "user@example.com",
        "password": "wrongpassword"
    })
    
    assert response.status_code in (401, 302)  # 302 redirect to login with error

def test_access_without_auth():
    """Protected endpoint without auth should return 401."""
    response = client.get("/profile")
    
    assert response.status_code in (401, 302)
```

### Testing Edge Cases

```python
@pytest.mark.parametrize("input_value,expected", [
    ("", None),                    # Empty string
    ("   ", None),                 # Whitespace only
    ("/decision ", None),          # Command without content
    ("/decision a" * 1000, None),  # Very long input
])
def test_slash_command_edge_cases(input_value, expected):
    """Slash command parser handles edge cases."""
    result = parse_slash_command(input_value)
    if expected is None:
        assert result is None or result.get("title") == ""
```

### Database Tests

When testing database operations:

```python
@pytest.mark.asyncio
async def test_create_user_with_duplicate_email_fails(db_session):
    """Creating user with duplicate email should raise error."""
    from sqlalchemy.exc import IntegrityError
    
    # Create first user
    await user_service.create(db_session, "test@example.com", "User 1")
    await db_session.commit()
    
    # Try to create duplicate
    with pytest.raises(IntegrityError):
        await user_service.create(db_session, "test@example.com", "User 2")
        await db_session.commit()
```

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=html

# Run specific file
pytest tests/test_slash_commands.py

# Run specific test
pytest tests/test_slash_commands.py::TestParseSlashCommand::test_decision_command

# Run tests matching pattern
pytest -k "login"

# Run and show print statements
pytest -s
```

## Checklist for AI

When generating tests, ensure:

- [ ] Tests are in the correct location (`tests/`)
- [ ] Test names are descriptive
- [ ] Both success and failure cases are covered
- [ ] Edge cases are considered
- [ ] Mocks are used for external services
- [ ] Fixtures are used for common setup
- [ ] Tests are independent (no shared state)
- [ ] Async tests use `@pytest.mark.asyncio`

---

*See [data-management.md](./data-management.md) for database testing patterns.*
