# Getting Started

This guide walks you through setting up a local development environment for Forge Communicator.

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **PostgreSQL 14+** (or Docker)
- **Node.js 18+** (optional, for frontend tooling)
- **Git**

## Quick Setup

### 1. Clone the Repository

```bash
git clone https://github.com/buildly/ForgeCommunicator.git
cd ForgeCommunicator
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start PostgreSQL

**Using Docker (recommended):**

```bash
docker run -d --name forge-db \
  -e POSTGRES_USER=forge \
  -e POSTGRES_PASSWORD=forge \
  -e POSTGRES_DB=forge_communicator \
  -p 5432:5432 \
  postgres:14
```

**Or using Docker Compose:**

```bash
docker-compose up -d db
```

### 5. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Database
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator

# Security
SECRET_KEY=your-development-secret-key-32-chars-min

# Admin setup
PLATFORM_ADMIN_EMAILS=youremail@example.com

# Optional: OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### 6. Run Database Migrations

```bash
alembic upgrade head
```

### 7. Seed Demo Data (Optional)

```bash
python scripts/seed.py
```

This creates demo users: `alice`, `bob`, `carol` (password: `password123`)

### 8. Start the Server

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_slash_commands.py

# Run specific test
pytest tests/test_slash_commands.py::TestParseSlashCommand::test_decision_command
```

### Code Formatting

```bash
# Format with ruff
ruff format .

# Check linting
ruff check .

# Auto-fix lint issues
ruff check --fix .
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "add_new_column"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current
```

### Running with Hot Reload

```bash
uvicorn app.main:app --reload --port 8000
```

Changes to Python files will automatically reload the server.

## Project Structure

```
forgecommunicator/
├── app/                    # Main application package
│   ├── main.py            # FastAPI app entry point
│   ├── settings.py        # Configuration (env vars)
│   ├── db.py              # Database setup
│   ├── models/            # SQLAlchemy models
│   ├── routers/           # API endpoints
│   ├── services/          # Business logic
│   ├── templates/         # Jinja2 templates
│   └── static/            # Static files
├── alembic/               # Database migrations
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── ops/                   # Operations scripts
├── devdocs/               # Developer documentation
└── forge/                 # Forge marketplace config
```

## IDE Setup

### VS Code

Recommended extensions:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Python Debugger (ms-python.debugpy)
- Ruff (charliermarsh.ruff)

Settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  }
}
```

### PyCharm

1. Set interpreter to `.venv/bin/python`
2. Mark `app/` as Sources Root
3. Enable pytest as test runner

## Common Issues

### Database Connection Errors

Check PostgreSQL is running:

```bash
docker ps | grep forge-db
```

Verify connection string in `.env`.

### Module Not Found

Ensure virtual environment is activated:

```bash
source .venv/bin/activate
which python  # Should show .venv path
```

### Alembic Errors

If migrations are out of sync:

```bash
alembic current
alembic heads
alembic upgrade head
```

### Port Already in Use

```bash
# Find process on port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

---

*For testing guidance, see [Testing Guide](./testing.md).*
