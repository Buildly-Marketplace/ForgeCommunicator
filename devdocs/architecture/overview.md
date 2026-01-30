# Architecture Overview

Forge Communicator is a modern, real-time team communication platform built with a clean, layered architecture following Buildly Forge standards.

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Web Framework** | FastAPI (async Python) |
| **Database** | PostgreSQL with SQLAlchemy 2.0 (async) |
| **Templates** | Jinja2 |
| **Frontend** | HTMX + Tailwind CSS |
| **Real-time** | WebSockets |
| **Push Notifications** | Web Push (VAPID) |
| **Migrations** | Alembic |

## Application Structure

```
app/
├── main.py              # FastAPI app entry point, middleware, lifespan
├── settings.py          # Pydantic settings (env vars)
├── db.py                # SQLAlchemy async engine, session management
├── deps.py              # FastAPI dependency injection
├── brand.py             # White-label branding utilities
├── templates_config.py  # Jinja2 template configuration
│
├── models/              # SQLAlchemy ORM models
│   ├── user.py          # User, AuthProvider, UserStatus
│   ├── workspace.py     # Workspace (multi-tenant org)
│   ├── channel.py       # Channel model
│   ├── membership.py    # Membership, ChannelMembership
│   ├── message.py       # Message model with threading
│   ├── artifact.py      # Artifact (decisions, features, issues, tasks)
│   ├── product.py       # Product model (Labs sync)
│   ├── push_subscription.py  # Web push subscriptions
│   ├── site_config.py   # Site-wide configuration
│   └── team_invite.py   # Workspace invitations
│
├── routers/             # FastAPI route handlers
│   ├── auth.py          # Authentication (local + OAuth)
│   ├── workspaces.py    # Workspace management
│   ├── channels.py      # Channel operations
│   ├── messages.py      # Message CRUD
│   ├── artifacts.py     # Artifact management
│   ├── profile.py       # User profile
│   ├── admin.py         # Admin dashboard
│   ├── push.py          # Push notification endpoints
│   ├── realtime.py      # WebSocket handlers
│   ├── sync.py          # Buildly Labs sync
│   └── invites.py       # Team invite handling
│
├── services/            # Business logic layer
│   ├── auth_providers.py    # OAuth provider implementations
│   ├── buildly_client.py    # Buildly Labs API client
│   ├── google_calendar.py   # Google Calendar integration
│   ├── labs_sync.py         # Labs product/artifact sync
│   ├── password.py          # Password hashing/verification
│   ├── push.py              # Push notification service
│   ├── rate_limiter.py      # Rate limiting service
│   └── slash_commands.py    # Slash command parser
│
├── templates/           # Jinja2 HTML templates
└── static/              # Static assets (JS, CSS, icons)
```

## Key Design Patterns

### 1. Dependency Injection (FastAPI)

All dependencies are injected via FastAPI's dependency system:

```python
from app.deps import CurrentUser, DBSession

@router.get("/profile")
async def get_profile(user: CurrentUser, db: DBSession):
    ...
```

### 2. Repository Pattern (via Services)

Business logic is encapsulated in service classes:

```python
from app.services.push import PushNotificationService

push_service = PushNotificationService()
await push_service.send_notification(db, user_id, title, body)
```

### 3. Async-First

All database operations use SQLAlchemy async:

```python
async with async_session_maker() as session:
    result = await session.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
```

### 4. Multi-Tenancy

Workspaces provide tenant isolation:

```
User → Membership → Workspace → Channels → Messages
```

## Request Flow

```
Request → Middleware → Router → Dependencies → Service → Database
                                    ↓
Response ← Template ← Service Result
```

### Middleware Stack

1. **CORS Middleware** - Cross-origin requests
2. **Request ID Middleware** - Tracing and logging
3. **Session Middleware** - User authentication (cookie-based)

## Database Connection

The application uses connection pooling with SSL support for managed databases:

- **Pool Size**: 5 connections (configurable)
- **Max Overflow**: 10 connections (configurable)
- **Pre-ping**: Enabled (validates connections)
- **SSL**: Auto-detected for managed DB hosts

## Real-time Architecture

WebSocket connections are managed per-channel:

```
Client ←→ WebSocket Handler ←→ Channel Manager ←→ Broadcast
```

Messages are delivered in real-time to all connected channel members.

## External Integrations

| Integration | Purpose |
|-------------|---------|
| **Google OAuth** | User authentication |
| **Buildly Labs OAuth** | SSO and org sync |
| **Google Calendar** | Status sync (DND when in meetings) |
| **Buildly Labs API** | Product and artifact sync |
| **Web Push (VAPID)** | Push notifications |

---

*See [Data Models](./data-models.md) for detailed model documentation.*
