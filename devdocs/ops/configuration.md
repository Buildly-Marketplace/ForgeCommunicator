# Configuration Reference

Forge Communicator is configured via environment variables. This document lists all available settings.

## Environment Variables

### Application Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | string | `Forge Communicator` | Application name |
| `APP_VERSION` | string | `0.1.0` | Application version |
| `DEBUG` | bool | `false` | Enable debug mode |
| `SECRET_KEY` | string | *(required in prod)* | Session encryption key |
| `BUILD_SHA` | string | `dev` | Build commit SHA (set by CI) |

### Server Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HOST` | string | `0.0.0.0` | Server bind address |
| `PORT` | int | `8000` | Server port |

### Database Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | string | `postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator` | PostgreSQL connection string |
| `DATABASE_POOL_SIZE` | int | `5` | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | int | `10` | Max overflow connections |

**Database URL Formats:**

```bash
# Local development
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator

# Docker Compose
DATABASE_URL=postgresql+asyncpg://forge:forge@db:5432/forge_communicator

# DigitalOcean Managed Database
DATABASE_URL=postgresql://user:pass@host.db.ondigitalocean.com:25060/forge?sslmode=require
```

> **Note:** The app automatically converts `postgres://` to `postgresql+asyncpg://` and handles SSL for managed databases.

### Registration & Admin

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REGISTRATION_MODE` | string | `open` | `open`, `invite_only`, or `closed` |
| `PLATFORM_ADMIN_EMAILS` | string | `""` | Comma-separated admin emails |

### Branding Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BRAND_NAME` | string | `Communicator` | Product display name |
| `BRAND_COMPANY` | string | `Buildly` | Company name |
| `BRAND_LOGO_URL` | string | *(null)* | Logo URL |
| `BRAND_FAVICON_URL` | string | *(null)* | Favicon URL |
| `BRAND_SUPPORT_EMAIL` | string | `support@buildly.io` | Support email |
| `BRAND_PRIMARY_COLOR` | string | `#3b82f6` | Primary theme color |
| `BRAND_SECONDARY_COLOR` | string | `#0f172a` | Secondary color |
| `BRAND_ACCENT_COLOR` | string | `#a855f7` | Accent color |

### OAuth Providers

#### Google OAuth

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GOOGLE_CLIENT_ID` | string | *(null)* | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | string | *(null)* | Google OAuth secret |
| `GOOGLE_REDIRECT_URI` | string | *(null)* | OAuth callback URL |

#### Buildly Labs OAuth

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BUILDLY_CLIENT_ID` | string | *(null)* | Buildly Labs client ID |
| `BUILDLY_CLIENT_SECRET` | string | *(null)* | Buildly Labs secret |
| `BUILDLY_REDIRECT_URI` | string | *(null)* | OAuth callback URL |
| `LABS_API_URL` | string | `https://api.buildly.io` | Buildly Labs API base URL |

### Push Notifications (VAPID)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VAPID_PUBLIC_KEY` | string | *(null)* | VAPID public key |
| `VAPID_PRIVATE_KEY` | string | *(null)* | VAPID private key |
| `VAPID_CONTACT_EMAIL` | string | `mailto:admin@example.com` | Contact email for VAPID |

Generate VAPID keys:

```bash
python scripts/generate_vapid.py
```

### Session Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SESSION_EXPIRE_HOURS` | int | `168` | Session expiry (7 days) |

### Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | string | `INFO` | Logging level |
| `LOG_FORMAT` | string | `text` | `text` or `json` |

### CORS

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CORS_ORIGINS` | string | `*` | Comma-separated allowed origins |

## Configuration Files

### `.env` File

Create a `.env` file for local development:

```bash
# .env
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator
PLATFORM_ADMIN_EMAILS=admin@example.com

# OAuth (optional)
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
```

### `.env.example`

Template for environment setup:

```bash
# .env.example - Copy to .env and fill in values

# Application
DEBUG=false
SECRET_KEY=

# Database
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator

# Admin
PLATFORM_ADMIN_EMAILS=
REGISTRATION_MODE=open

# Branding
BRAND_NAME=Communicator
BRAND_COMPANY=Your Company

# OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
BUILDLY_CLIENT_ID=
BUILDLY_CLIENT_SECRET=

# Push Notifications (optional)
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
```

## Platform-Specific Configuration

### Docker

Set env vars in `docker-compose.yml`:

```yaml
services:
  app:
    environment:
      - DATABASE_URL=postgresql+asyncpg://forge:forge@db:5432/forge_communicator
      - SECRET_KEY=${SECRET_KEY}
      - PLATFORM_ADMIN_EMAILS=${PLATFORM_ADMIN_EMAILS}
```

### DigitalOcean App Platform

Set in App Spec (`do-app.yaml`):

```yaml
envs:
  - key: DATABASE_URL
    scope: RUN_TIME
    value: ${db.DATABASE_URL}
  - key: SECRET_KEY
    scope: RUN_TIME
    type: SECRET
```

### Heroku

```bash
heroku config:set SECRET_KEY=xxx
heroku config:set PLATFORM_ADMIN_EMAILS=admin@example.com
```

### Railway

Set in Railway dashboard or `railway.json`:

```json
{
  "build": {},
  "deploy": {
    "env": {
      "PORT": "8000"
    }
  }
}
```

## Security Recommendations

### Production Checklist

- [ ] Set unique `SECRET_KEY` (32+ characters)
- [ ] Set `DEBUG=false`
- [ ] Configure `CORS_ORIGINS` (not `*`)
- [ ] Set `REGISTRATION_MODE` appropriately
- [ ] Configure `PLATFORM_ADMIN_EMAILS`
- [ ] Enable HTTPS (via reverse proxy)
- [ ] Use managed database with SSL

### Generating Secret Key

```bash
# Python
python -c "import secrets; print(secrets.token_hex(32))"

# OpenSSL
openssl rand -hex 32
```

---

*For deployment guides, see [Deployment](./deployment.md).*
