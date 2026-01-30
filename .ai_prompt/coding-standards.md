# Coding Standards for Buildly Forge

This document defines the coding standards for Forge Communicator. AI assistants should follow these conventions when generating or modifying code.

## Python Style

### Formatting

- **Line length**: 100 characters max
- **Formatter**: Ruff
- **Indent**: 4 spaces (no tabs)
- **Quotes**: Double quotes for strings
- **Imports**: Sorted with isort (via Ruff)

### Type Hints

Always use type hints for function signatures:

```python
# ✅ Good
async def get_user(db: AsyncSession, user_id: int) -> User | None:
    ...

# ❌ Bad
async def get_user(db, user_id):
    ...
```

Use `Mapped[]` for SQLAlchemy columns:

```python
# ✅ Good
class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Imports

Order: stdlib → third-party → local

```python
# Standard library
import json
import logging
from datetime import datetime
from typing import Optional

# Third-party
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Local
from app.db import get_db
from app.models.user import User
from app.services.auth import verify_token
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Variables | snake_case | `user_id`, `is_active` |
| Functions | snake_case | `get_user()`, `send_notification()` |
| Classes | PascalCase | `UserService`, `PushNotification` |
| Constants | SCREAMING_SNAKE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Files | snake_case | `user_service.py`, `auth_providers.py` |

## FastAPI Conventions

### Router Definition

```python
from fastapi import APIRouter

router = APIRouter(
    prefix="/users",
    tags=["users"],
)
```

### Endpoint Functions

```python
@router.get("/{user_id}")
async def get_user(
    user_id: int,
    current_user: CurrentUser,  # Dependency injection
    db: DBSession,
) -> UserResponse:
    """Get user by ID.
    
    Args:
        user_id: The user's unique identifier.
        
    Returns:
        The user data.
        
    Raises:
        HTTPException: 404 if user not found.
    """
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

### Form Data

Use Annotated for form fields:

```python
from typing import Annotated
from fastapi import Form

@router.post("/login")
async def login(
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    ...
```

## SQLAlchemy Conventions

### Model Definition

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin

class User(Base, TimestampMixin):
    """User account model.
    
    Attributes:
        id: Primary key.
        email: User's email address (unique).
        display_name: Display name for UI.
    """
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
```

### Async Queries

Always use async session methods:

```python
# ✅ Good - async
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()

# ✅ Good - relationships with selectinload
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(User)
    .options(selectinload(User.memberships))
    .where(User.id == user_id)
)

# ❌ Bad - synchronous
user = db.query(User).filter(User.id == user_id).first()
```

## Service Layer

### Service Structure

```python
# app/services/user_service.py

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations."""
    
    async def get_by_id(self, db: AsyncSession, user_id: int) -> User | None:
        """Get user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        """Get user by email (case-insensitive)."""
        result = await db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        db: AsyncSession,
        email: str,
        display_name: str,
        **kwargs,
    ) -> User:
        """Create a new user."""
        user = User(
            email=email.lower(),
            display_name=display_name,
            **kwargs,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user


user_service = UserService()
```

## Error Handling

### HTTP Exceptions

```python
from fastapi import HTTPException, status

# ✅ Good - specific status codes
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="User not found"
)

raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Not authorized to access this resource"
)

# ✅ Good - for HTMX responses
if request.headers.get("HX-Request"):
    return HTMLResponse(
        '<div class="text-red-500">Error message</div>',
        status_code=400,
    )
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# ✅ Good - appropriate levels
logger.debug("Processing request %s", request_id)
logger.info("User %s logged in", user.email)
logger.warning("Rate limit approaching for %s", client_ip)
logger.error("Failed to send notification: %s", error)
logger.exception("Unexpected error in payment processing")  # Includes traceback
```

## Docstrings

Use Google-style docstrings:

```python
def send_notification(
    user_id: int,
    title: str,
    body: str,
    url: str | None = None,
) -> int:
    """Send push notification to a user.
    
    Sends a web push notification to all registered devices for the user.
    Invalid subscriptions are automatically cleaned up.
    
    Args:
        user_id: The recipient user's ID.
        title: Notification title (max 50 chars).
        body: Notification body text.
        url: Optional URL to open when clicked.
        
    Returns:
        Number of notifications successfully sent.
        
    Raises:
        ValueError: If title exceeds 50 characters.
        
    Example:
        >>> sent = send_notification(123, "New Message", "You have a new message")
        >>> print(f"Sent {sent} notifications")
    """
    ...
```

## Code Organization

### File Size

- Keep files under 500 lines
- Split large files into logical modules
- One class per file for models

### Function Length

- Functions should do one thing
- Aim for under 30 lines per function
- Extract complex logic into helper functions

### Comments

```python
# ✅ Good - explains WHY
# Skip SSL for local dev (asyncpg handles SSL differently than psycopg2)
if is_local_database:
    ssl_context = None

# ❌ Bad - explains WHAT (obvious from code)
# Set user to None
user = None
```

## Templates (Jinja2)

### Template Naming

- Use lowercase with underscores: `user_profile.html`
- Partials start with underscore: `_message_item.html`
- Group by feature: `templates/auth/login.html`

### Template Structure

```html
{% extends "layout.html" %}

{% block title %}Page Title{% endblock %}

{% block content %}
<div class="container">
    <!-- Content here -->
</div>
{% endblock %}
```

---

*See [testing-guidelines.md](./testing-guidelines.md) for test requirements.*
