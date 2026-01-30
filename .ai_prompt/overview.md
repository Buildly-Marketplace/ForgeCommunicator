# Project Overview for AI Assistants

## What is Forge Communicator?

Forge Communicator is a **real-time team communication platform** built as part of the Buildly Forge ecosystem. It provides Slack-like functionality with:

- Real-time messaging via WebSockets
- Message threading
- Multi-workspace support
- OAuth integration (Google, Buildly Labs)
- Push notifications
- Artifact creation from slash commands
- White-label branding

## Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend                             │
│  HTMX + Tailwind CSS + Vanilla JS                       │
│  Templates: Jinja2                                       │
├─────────────────────────────────────────────────────────┤
│                     Backend                              │
│  FastAPI (Python 3.11+)                                 │
│  Async throughout                                        │
├─────────────────────────────────────────────────────────┤
│                   Database                               │
│  PostgreSQL 14+ with SQLAlchemy 2.0 (asyncpg)           │
│  Migrations: Alembic                                     │
├─────────────────────────────────────────────────────────┤
│                   Integrations                           │
│  Google OAuth, Buildly Labs SSO, Web Push (VAPID)       │
└─────────────────────────────────────────────────────────┘
```

## Application Architecture

### Directory Structure

```
app/
├── main.py           # FastAPI app, middleware, lifespan
├── settings.py       # Pydantic settings (env vars)
├── db.py             # Async SQLAlchemy engine & sessions
├── deps.py           # FastAPI dependencies (auth, db)
├── models/           # ORM models (User, Workspace, Channel, etc.)
├── routers/          # API endpoints organized by domain
├── services/         # Business logic (stateless)
├── templates/        # Jinja2 HTML templates
└── static/           # CSS, JS, icons
```

### Key Design Patterns

#### 1. Dependency Injection

```python
# Dependencies defined in app/deps.py
from app.deps import CurrentUser, DBSession

@router.get("/profile")
async def get_profile(
    user: CurrentUser,      # Authenticated user (raises 401 if not)
    db: DBSession,          # Async database session
):
    ...
```

#### 2. Service Layer

Business logic is in services, routers are thin:

```python
# Router calls service
from app.services.push import PushNotificationService

push_service = PushNotificationService()
await push_service.send_notification(db, user_id, "Title", "Body")
```

#### 3. Async Database Operations

```python
from sqlalchemy import select
from app.models.user import User

# Always use async/await
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()
```

#### 4. Multi-Tenancy

Data is isolated by Workspace:

```
User → Membership → Workspace → Channels → Messages
```

Always filter queries by workspace context.

## Core Models

| Model | Purpose |
|-------|---------|
| `User` | User identity, auth, profile |
| `Workspace` | Multi-tenant organization |
| `Membership` | User ↔ Workspace relationship |
| `Channel` | Communication channel |
| `Message` | Messages with threading support |
| `Artifact` | Decisions, features, issues, tasks |

## Router Organization

| Router | Prefix | Purpose |
|--------|--------|---------|
| `auth` | `/auth` | Login, register, OAuth |
| `workspaces` | `/workspaces` | Workspace CRUD |
| `channels` | (nested) | Channel operations |
| `messages` | (nested) | Message CRUD |
| `artifacts` | `/artifacts` | Artifact management |
| `admin` | `/admin` | Admin dashboard |
| `push` | `/push` | Push notifications |
| `realtime` | `/ws` | WebSockets |

## Configuration

All config via environment variables using Pydantic settings:

```python
from app.settings import settings

# Access settings anywhere
db_url = settings.database_url
is_debug = settings.debug
```

## When Working on This Codebase

### Before Making Changes

1. Understand the affected models in `app/models/`
2. Check existing services in `app/services/`
3. Review related tests in `tests/`
4. Check for migrations needed in `alembic/versions/`

### Common Tasks

- **Add a new endpoint**: Create in appropriate router, add service if needed
- **Add a model field**: Update model, create Alembic migration
- **Add a feature**: Model → Service → Router → Template flow
- **Fix a bug**: Write failing test first, then fix

### Files You'll Touch Most

- `app/models/*.py` - Data models
- `app/routers/*.py` - Endpoints
- `app/services/*.py` - Business logic
- `app/templates/*.html` - UI templates
- `tests/*.py` - Test files
- `alembic/versions/*.py` - Migrations

---

*See [coding-standards.md](./coding-standards.md) for code style requirements.*
