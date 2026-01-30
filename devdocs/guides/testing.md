# Testing Guide

This guide covers testing practices and patterns for Forge Communicator following Buildly Forge standards.

## Test Framework

- **pytest** - Test runner and framework
- **pytest-asyncio** - Async test support
- **FastAPI TestClient** - HTTP endpoint testing
- **Coverage.py** - Code coverage reporting

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures (to be created)
├── test_push_notifications.py
├── test_in_app_notifications.py
├── test_slash_commands.py
└── integration/             # Integration tests (future)
    └── test_auth_flow.py
```

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_slash_commands.py

# Run specific test class
pytest tests/test_slash_commands.py::TestParseSlashCommand

# Run specific test method
pytest tests/test_slash_commands.py::TestParseSlashCommand::test_decision_command

# Run tests matching pattern
pytest -k "decision"

# Run with print output visible
pytest -s
```

### Configuration

Tests are configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

## Test Categories

### 1. Unit Tests

Test individual functions and classes in isolation.

**Example: Slash Command Parser Tests**

```python
# tests/test_slash_commands.py

import pytest
from app.services.slash_commands import (
    parse_slash_command,
    SlashCommandType,
    ArtifactType,
)

class TestParseSlashCommand:
    """Test slash command parsing."""

    def test_decision_command(self):
        """Test /decision command parsing."""
        result = parse_slash_command("/decision Use PostgreSQL")
        
        assert result is not None
        assert result["type"] == SlashCommandType.ARTIFACT
        assert result["artifact_type"] == ArtifactType.DECISION
        assert result["title"] == "Use PostgreSQL"

    def test_unknown_command(self):
        """Test unknown command returns None."""
        result = parse_slash_command("/unknown something")
        assert result is None

    def test_not_a_command(self):
        """Test regular message returns None."""
        result = parse_slash_command("Hello, world")
        assert result is None
```

### 2. API Endpoint Tests

Test HTTP endpoints using FastAPI's TestClient.

**Example: Push Notification Endpoint Tests**

```python
# tests/test_push_notifications.py

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.settings import settings

client = TestClient(app)

def test_vapid_public_key():
    """Test VAPID public key endpoint."""
    response = client.get("/push/vapid-public-key")
    
    if settings.vapid_public_key:
        assert response.status_code == 200
        assert "publicKey" in response.json()
    else:
        assert response.status_code == 501

def test_push_subscribe_requires_auth():
    """Test subscribe endpoint requires authentication."""
    response = client.post("/push/subscribe", data={
        "endpoint": "https://example.com/endpoint",
        "p256dh": "key",
        "auth": "auth"
    })
    # Should redirect to login or return 401
    assert response.status_code in (302, 401)
```

### 3. Integration Tests

Test multiple components working together.

**Example: Authentication Flow Test**

```python
# tests/integration/test_auth_flow.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestAuthFlow:
    """Test complete authentication flows."""

    def test_register_and_login(self):
        """Test user registration and login flow."""
        # Register
        response = client.post("/auth/register", data={
            "email": "test@example.com",
            "display_name": "Test User",
            "password": "securepassword123",
            "password_confirm": "securepassword123"
        }, follow_redirects=False)
        assert response.status_code in (302, 200)
        
        # Login
        response = client.post("/auth/login", data={
            "email": "test@example.com",
            "password": "securepassword123"
        }, follow_redirects=False)
        assert response.status_code == 302
        assert "session" in response.cookies
```

## Fixtures

### Recommended Fixtures (conftest.py)

```python
# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, get_db
from app.models.user import User, AuthProvider
from app.services.password import hash_password

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator_test"

@pytest.fixture(scope="session")
def engine():
    """Create test database engine."""
    return create_async_engine(TEST_DATABASE_URL, echo=True)

@pytest.fixture(scope="function")
async def db_session(engine):
    """Create a clean database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)

@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        display_name="Test User",
        hashed_password=hash_password("password123"),
        auth_provider=AuthProvider.LOCAL,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
def authenticated_client(client, test_user):
    """Create authenticated test client."""
    # Login to get session
    response = client.post("/auth/login", data={
        "email": test_user.email,
        "password": "password123"
    }, follow_redirects=False)
    return client
```

## Test Patterns

### Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await some_async_function()
    assert result == expected
```

### Testing Error Cases

```python
def test_invalid_input():
    """Test that invalid input raises appropriate error."""
    with pytest.raises(ValueError, match="Invalid input"):
        function_that_should_raise("invalid")
```

### Parameterized Tests

```python
import pytest

@pytest.mark.parametrize("command,expected_type", [
    ("/decision Test", ArtifactType.DECISION),
    ("/feature Test", ArtifactType.FEATURE),
    ("/issue Test", ArtifactType.ISSUE),
    ("/task Test", ArtifactType.TASK),
])
def test_artifact_commands(command, expected_type):
    """Test all artifact commands."""
    result = parse_slash_command(command)
    assert result["artifact_type"] == expected_type
```

### Mocking External Services

```python
from unittest.mock import patch, AsyncMock

@patch("app.services.push.webpush")
def test_push_notification(mock_webpush):
    """Test push notification with mocked webpush."""
    mock_webpush.return_value = None
    
    # Call service
    result = push_service.send(subscription, "Test")
    
    # Verify mock was called
    mock_webpush.assert_called_once()
```

## Code Coverage

### Generate Coverage Report

```bash
# Run with coverage
pytest --cov=app --cov-report=html

# View report
open htmlcov/index.html
```

### Coverage Targets

| Component | Target |
|-----------|--------|
| Services | 80%+ |
| Routers | 70%+ |
| Models | 60%+ |
| Overall | 70%+ |

## Best Practices

### 1. Test Naming

Use descriptive test names that explain what is being tested:

```python
# Good
def test_login_with_invalid_password_returns_401():

# Bad
def test_login():
```

### 2. Arrange-Act-Assert

Structure tests clearly:

```python
def test_something():
    # Arrange
    user = create_test_user()
    
    # Act
    result = perform_action(user)
    
    # Assert
    assert result.success
```

### 3. Isolation

Each test should be independent:
- Use fixtures for setup/teardown
- Don't rely on test execution order
- Clean up after each test

### 4. Test Real Behavior

Test behavior, not implementation:

```python
# Good - tests behavior
def test_user_can_join_workspace():
    workspace.add_member(user)
    assert user in workspace.members

# Bad - tests implementation
def test_membership_created():
    membership = Membership(user_id=1, workspace_id=1)
    assert membership.user_id == 1
```

## Continuous Integration

Tests run automatically on CI/CD:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest --cov=app
```

---

*For migration testing, see [Database Migrations](./migrations.md).*
