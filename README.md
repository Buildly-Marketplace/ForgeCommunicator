# Forge Communicator

A modern, real-time team communication platform built with FastAPI, HTMX, and WebSockets. Features Slack-like channels, threading, Buildly Labs integration, and white-label branding support.

## Features

- **Real-time messaging** with WebSocket support
- **Message threading** for organized conversations
- **Channels** - Public and private channels per workspace
- **Multi-workspace** - Users can belong to multiple workspaces
- **OAuth Support** - Google and Buildly Labs SSO
- **White-label branding** - Customizable colors, logos, and themes
- **Dark mode** - Beautiful futuristic dark theme by default
- **Buildly Labs Integration** - Sync products and artifacts
- **Push notifications** - Web push via VAPID
- **Search** - Full-text search across messages

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis (optional, for caching)

### Installation

1. **Clone and install dependencies:**

   ```bash
   git clone https://github.com/buildly/ForgeCommunicator.git
   cd ForgeCommunicator
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Set up your environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start the database:**

   ```bash
   # Using Docker
   docker run -d --name forge-db \
     -e POSTGRES_USER=forge \
     -e POSTGRES_PASSWORD=forge \
     -e POSTGRES_DB=forge_communicator \
     -p 5432:5432 postgres:14
   ```

4. **Run the application:**

   ```bash
   uvicorn app.main:app --reload
   ```

5. **Open** http://localhost:8000

---

## Admin Setup

### Setting Up Your First Platform Admin

ForgeCommunicator uses environment variables to designate platform administrators. This is more secure than hardcoded credentials.

**Before your first deployment:**

1. Set the `PLATFORM_ADMIN_EMAILS` environment variable with your admin email(s):

   ```bash
   # Single admin
   PLATFORM_ADMIN_EMAILS=admin@yourcompany.com

   # Multiple admins (comma-separated)
   PLATFORM_ADMIN_EMAILS=admin@yourcompany.com,devops@yourcompany.com
   ```

2. Start the application and **register** with one of those email addresses

3. You will automatically have platform admin access!

### What Can Platform Admins Do?

- Access the **Admin Dashboard** at `/admin`
- Manage all users across the platform
- View and manage all workspaces
- Configure branding and themes at `/admin/config/branding`
- Toggle user admin status
- Deactivate/reactivate user accounts

### Adding More Admins Later

**Option 1:** Add their email to `PLATFORM_ADMIN_EMAILS` before they register

**Option 2:** Existing platform admin can grant admin access:
1. Go to `/admin/users`
2. Find the user
3. Click "Toggle Admin"

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator` |
| `SECRET_KEY` | Session encryption key | (required in production) |
| `PLATFORM_ADMIN_EMAILS` | Comma-separated admin emails | `""` |
| `REGISTRATION_MODE` | `open`, `invite_only`, or `closed` | `open` |

### Branding

| Variable | Description | Default |
|----------|-------------|---------|
| `BRAND_NAME` | Product name | `Communicator` |
| `BRAND_COMPANY` | Company name | `Buildly` |
| `BRAND_LOGO_URL` | Logo URL | `/static/forge-logo.png` |
| `BRAND_PRIMARY_COLOR` | Primary theme color | `#3b82f6` |
| `BRAND_SECONDARY_COLOR` | Secondary color | `#0f172a` |
| `BRAND_ACCENT_COLOR` | Accent color | `#a855f7` |

### OAuth Providers

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret |
| `GOOGLE_REDIRECT_URI` | Callback URL |
| `BUILDLY_CLIENT_ID` | Buildly Labs OAuth client ID |
| `BUILDLY_CLIENT_SECRET` | Buildly Labs OAuth secret |

---

## Development

### Seed Demo Data

```bash
python scripts/seed.py
```

This creates demo users (alice, bob, carol) and a sample workspace.

### Run Tests

```bash
pytest
```

### Project Structure

```
app/
├── models/          # SQLAlchemy models
├── routers/         # FastAPI route handlers
├── services/        # Business logic
├── templates/       # Jinja2 templates
└── static/          # CSS, JS, images
```

---

## Deployment

### Docker

```bash
docker build -t forge-communicator .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://... \
  -e SECRET_KEY=your-secret-key \
  -e PLATFORM_ADMIN_EMAILS=admin@yourcompany.com \
  forge-communicator
```

### Railway / Render / Fly.io

Set the environment variables in your platform's dashboard and deploy.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

Built with love by [Buildly](https://buildly.io)
