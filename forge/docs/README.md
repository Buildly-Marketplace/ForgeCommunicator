# Forge Communicator

Lightweight Slack-style chat for product teams with built-in artifact tracking.

## Features

- **Multi-tenant Workspaces** - Create isolated spaces for different teams or projects
- **Channels** - Organize conversations with public, private, and product-linked channels
- **Real-time Messaging** - WebSocket support with HTTP polling fallback
- **Slash Commands** - Create artifacts directly from chat
  - `/decision` - Record architectural decisions
  - `/feature` - Track feature requests
  - `/issue` - Report bugs and issues
  - `/task` - Create todo items
- **Artifact Tracking** - Built-in tracking with status workflows per artifact type
- **OAuth Support** - Sign in with Google or Buildly Labs
- **Buildly Integration** - Sync products and artifacts with Buildly Labs

## Quick Start

### Using Forge Marketplace

1. Install from Forge Marketplace
2. Configure environment variables
3. Access at your assigned URL

### Using Docker Compose (Local Development)

```bash
# Clone the repository
git clone https://github.com/buildly-release-management/forge-communicator.git
cd forge-communicator

# Copy environment file
cp .env.example .env

# Start services
docker-compose up -d

# Access at http://localhost:8000
```

### Manual Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL database
createdb forge_communicator

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8000` |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `SECRET_KEY` | JWT signing key | Required |
| `REALTIME_MODE` | `ws` (WebSocket) or `poll` | `ws` |
| `POLL_INTERVAL_MS` | Polling interval in milliseconds | `3000` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Optional |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Optional |
| `BUILDLY_CLIENT_ID` | Buildly OAuth client ID | Optional |
| `BUILDLY_CLIENT_SECRET` | Buildly OAuth client secret | Optional |
| `BUILDLY_API_URL` | Buildly API URL | `https://api.buildly.io` |

## Slash Commands

### Artifact Creation

```
/decision [title]   - Create a decision record
/feature [title]    - Create a feature request
/issue [title]      - Create a bug/issue report
/task [title]       - Create a task
```

### Channel Management

```
/join #channel-name - Join a channel
/leave              - Leave current channel
/topic [new topic]  - Set channel topic
/rename [new name]  - Rename the channel (admins only)
```

## API Endpoints

### Authentication
- `POST /auth/login` - Login with email/password
- `POST /auth/register` - Create new account
- `GET /auth/logout` - Logout
- `GET /auth/google` - Google OAuth flow
- `GET /auth/buildly` - Buildly OAuth flow

### Workspaces
- `GET /workspaces` - List user's workspaces
- `POST /workspaces` - Create workspace
- `POST /workspaces/join` - Join via invite code
- `GET /workspaces/{id}/settings` - Workspace settings

### Channels
- `GET /workspaces/{id}/channels` - List channels
- `POST /workspaces/{id}/channels` - Create channel
- `GET /workspaces/{id}/channels/{id}` - View channel
- `POST /workspaces/{id}/channels/{id}/join` - Join channel
- `POST /workspaces/{id}/channels/{id}/leave` - Leave channel

### Messages
- `POST /workspaces/{id}/channels/{id}/messages` - Send message
- `POST /.../messages/{id}/edit` - Edit message
- `POST /.../messages/{id}/delete` - Delete message

### Real-time
- `WS /workspaces/{id}/channels/{id}/ws` - WebSocket connection
- `GET /.../messages/poll?after={timestamp}` - Polling endpoint

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL with asyncpg
- **Frontend**: Jinja2 templates, HTMX, Tailwind CSS
- **Real-time**: WebSockets with HTMX polling fallback
- **Auth**: JWT tokens, bcrypt passwords, OAuth 2.0

## Deployment

### Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/forge-communicator

# Deploy
gcloud run deploy forge-communicator \
  --image gcr.io/PROJECT_ID/forge-communicator \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=..." \
  --set-secrets "SECRET_KEY=secret-key:latest"
```

### DigitalOcean App Platform

Use the included `do-app.yaml` spec file:

```bash
doctl apps create --spec do-app.yaml
```

## Development

```bash
# Run tests
pytest

# Run with hot reload
uvicorn app.main:app --reload

# Generate new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## License

MIT License - see LICENSE file for details.

## Support

- Issues: https://github.com/buildly-release-management/forge-communicator/issues
- Documentation: https://forge.buildly.io/apps/forge-communicator
- Email: hello@buildly.io
