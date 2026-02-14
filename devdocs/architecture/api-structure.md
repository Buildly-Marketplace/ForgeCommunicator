# API Structure

Forge Communicator exposes a RESTful API with HTML (HTMX) and JSON response formats.

## Router Organization

| Router | Prefix | Tags | Description |
|--------|--------|------|-------------|
| `auth` | `/auth` | auth | Authentication and OAuth |
| `workspaces` | `/workspaces` | workspaces | Workspace management |
| `channels` | `/` | channels | Channel operations |
| `messages` | `/` | messages | Message CRUD |
| `artifacts` | `/artifacts` | artifacts | Artifact management |
| `profile` | `/profile` | profile | User profile |
| `admin` | `/admin` | admin | Admin dashboard |
| `push` | `/push` | push | Push notifications |
| `realtime` | `/ws` | realtime | WebSocket connections |
| `sync` | `/sync` | sync | Buildly Labs sync |
| `invites` | `/invite` | invites | Team invitations |
| `api` | `/api` | api | DRF-compatible API for CollabHub |

## Endpoint Conventions

### Response Format

Endpoints return **HTML** by default (for HTMX) or **JSON** when:
- Request includes `Accept: application/json`
- Request includes `HX-Request` header (partial HTML)
- Endpoint is explicitly JSON-only

### Authentication

Most endpoints require authentication via session cookie:

```python
from app.deps import CurrentUser

@router.get("/profile")
async def get_profile(user: CurrentUser):  # Raises 401 if not authenticated
    ...
```

For optional auth:

```python
from app.deps import CurrentUserOptional

@router.get("/public")
async def public_page(user: CurrentUserOptional):
    if user:
        # Show personalized content
    ...
```

## Key Endpoints

### Authentication (`/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/login` | Login page |
| POST | `/auth/login` | Login with email/password |
| GET | `/auth/register` | Registration page |
| POST | `/auth/register` | Create new account |
| GET | `/auth/logout` | Clear session |
| GET | `/auth/oauth/{provider}` | Start OAuth flow |
| GET | `/auth/callback/{provider}` | OAuth callback |

### Workspaces (`/workspaces`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/workspaces` | List user's workspaces |
| GET | `/workspaces/new` | New workspace form |
| POST | `/workspaces` | Create workspace |
| GET | `/workspaces/{slug}` | View workspace |
| GET | `/workspaces/{slug}/settings` | Workspace settings |
| POST | `/workspaces/{slug}/invite` | Generate invite link |

### Channels

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/workspaces/{slug}/channels/{name}` | View channel |
| GET | `/workspaces/{slug}/channels/new` | New channel form |
| POST | `/workspaces/{slug}/channels` | Create channel |
| DELETE | `/workspaces/{slug}/channels/{name}` | Delete channel |

### Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/channels/{id}/messages` | Get messages (paginated) |
| POST | `/channels/{id}/messages` | Send message |
| PUT | `/messages/{id}` | Edit message |
| DELETE | `/messages/{id}` | Delete message |
| GET | `/messages/{id}/thread` | Get thread replies |
| POST | `/messages/{id}/thread` | Reply to thread |

### Push Notifications (`/push`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/push/vapid-public-key` | Get VAPID public key |
| POST | `/push/subscribe` | Register push subscription |
| POST | `/push/unsubscribe` | Remove subscription |
| POST | `/push/test` | Send test notification |

### Admin (`/admin`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin` | Admin dashboard |
| GET | `/admin/users` | User management |
| GET | `/admin/users/{id}` | User detail |
| POST | `/admin/users/{id}/toggle-admin` | Toggle admin status |
| GET | `/admin/workspaces` | Workspace management |
| GET | `/admin/config/branding` | Branding settings |
| POST | `/admin/config/branding` | Update branding |

### Health & Meta

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health`, `/healthz` | Health check |
| GET | `/meta` | Application metadata |

## WebSocket API (`/ws`)

### Connection

```javascript
const ws = new WebSocket('wss://example.com/ws/channels/{channel_id}');
```

### Message Types

**Client → Server:**

```json
{
  "type": "message",
  "content": "Hello, world!"
}
```

```json
{
  "type": "typing",
  "is_typing": true
}
```

**Server → Client:**

```json
{
  "type": "message",
  "message": {
    "id": 123,
    "content": "Hello, world!",
    "user": {"id": 1, "display_name": "Alice"},
    "created_at": "2026-01-30T12:00:00Z"
  }
}
```

```json
{
  "type": "typing",
  "user": {"id": 2, "display_name": "Bob"},
  "is_typing": true
}
```

## Error Responses

### HTTP Errors

| Status | Description |
|--------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Server Error |

### Error Format (JSON)

```json
{
  "detail": "Error message here"
}
```

### Error Format (HTML)

Returns rendered error template with error message.

## Rate Limiting

Authentication endpoints are rate-limited:
- Login: 5 attempts per minute per IP
- Registration: 10 attempts per hour per IP

## CORS Configuration

CORS is enabled with configurable origins:

```python
# settings.py
cors_origins: list[str] = ["http://localhost:3000", "https://app.example.com"]
```

## CollabHub Integration API (`/api`)

The `/api` router provides a Django REST Framework-compatible API for integration
with Buildly CollabHub. This enables bi-directional profile sync and data sharing
across the Buildly ecosystem.

### Authentication

Supports both DRF Token auth and OAuth Bearer auth:

```bash
# DRF-style Token auth
curl -H "Authorization: Token <api_key>" https://comms.buildly.io/api/users/me/

# OAuth Bearer auth (Labs access token)
curl -H "Authorization: Bearer <labs_token>" https://comms.buildly.io/api/users/me/
```

### User Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me/` | Get current user profile |
| PATCH | `/api/users/me/` | Update current user profile |
| GET | `/api/users/{id}/` | Get user by ID |
| GET | `/api/users/` | List users (paginated, filterable) |

### Workspace Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workspaces/` | List user's workspaces |
| GET | `/api/workspaces/{id}/members/` | List workspace members |

### Activity & Stats Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/activity/` | Get activity feed |
| GET | `/api/stats/` | Get user statistics |
| POST | `/api/sync/profile/` | Sync profile with CollabHub |

### Response Format

All responses follow DRF pagination format:

```json
{
  "count": 42,
  "next": "https://comms.buildly.io/api/users/?offset=50",
  "previous": null,
  "results": [...]
}
```

### Profile Sync

The `/api/sync/profile/` endpoint supports bi-directional sync:

```bash
# Pull profile from CollabHub
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"direction": "pull"}' \
  https://comms.buildly.io/api/sync/profile/

# Push profile to CollabHub
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"direction": "push"}' \
  https://comms.buildly.io/api/sync/profile/
```

---

*For detailed endpoint documentation, see individual router files in `app/routers/`.*
