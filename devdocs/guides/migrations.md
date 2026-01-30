# Database Migrations

Forge Communicator uses Alembic for database schema migrations.

## Overview

Migrations are stored in `alembic/versions/` and follow a sequential numbering convention:

```
alembic/versions/
├── 001_initial.py
├── 002_add_labs_sso_columns.py
├── 003_add_team_invites.py
├── 004_add_google_calendar_integration.py
├── 005_extend_avatar_url_column.py
├── 006_add_push_subscriptions.py
├── 007_add_user_bio.py
└── 008_add_user_title.py
```

## Common Commands

### Check Current State

```bash
# Show current migration revision
alembic current

# Show latest available revision (head)
alembic heads

# Show migration history
alembic history
```

### Apply Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply next N migrations
alembic upgrade +1

# Apply specific revision
alembic upgrade 003_add_team_invites
```

### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 002_add_labs_sso_columns

# Rollback all (DANGEROUS - use with caution)
alembic downgrade base
```

### Create New Migration

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "description_of_change"

# Create empty migration
alembic revision -m "description_of_change"
```

## Migration File Structure

```python
"""add_user_bio

Revision ID: 007_add_user_bio
Revises: 006_add_push_subscriptions
Create Date: 2026-01-20 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '007_add_user_bio'
down_revision = '006_add_push_subscriptions'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Apply migration."""
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))

def downgrade() -> None:
    """Reverse migration."""
    op.drop_column('users', 'bio')
```

## Writing Safe Migrations

### 1. Always Use IF NOT EXISTS

For additive changes, use PostgreSQL's `IF NOT EXISTS`:

```python
def upgrade() -> None:
    # Safe to run multiple times
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT")
```

### 2. Handle Both Directions

Always implement `downgrade()`:

```python
def downgrade() -> None:
    op.drop_column('users', 'bio')
```

### 3. Consider Data Migration

If changing column types or constraints:

```python
def upgrade() -> None:
    # Add new column
    op.add_column('users', sa.Column('status_new', sa.String(20)))
    
    # Migrate data
    op.execute("UPDATE users SET status_new = status::varchar")
    
    # Drop old column
    op.drop_column('users', 'status')
    
    # Rename new column
    op.alter_column('users', 'status_new', new_column_name='status')
```

### 4. Index Considerations

Create indexes concurrently for large tables:

```python
def upgrade() -> None:
    # Create index without locking table
    op.execute("CREATE INDEX CONCURRENTLY idx_messages_channel ON messages(channel_id)")
```

## Environment Configuration

Alembic configuration is in `alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

# Database URL (overridden by env.py)
sqlalchemy.url = postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator
```

The `alembic/env.py` reads the database URL from settings:

```python
from app.settings import settings

config.set_main_option("sqlalchemy.url", settings.database_url)
```

## Runtime Safe Migrations

The application also runs "safe migrations" on startup for columns that may be missing:

```python
# app/db.py - init_db()
migrations = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS labs_user_id INTEGER",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS labs_org_uuid VARCHAR(36)",
    # ...
]
```

This ensures the application can start even if migrations haven't been run explicitly.

## Best Practices

### Naming Conventions

Use descriptive, sequential names:

```
{number}_{description}.py

001_initial.py
002_add_user_profile_fields.py
003_add_workspace_settings.py
```

### Testing Migrations

Before deploying:

```bash
# Backup database
pg_dump -U forge forge_communicator > backup.sql

# Apply migrations
alembic upgrade head

# Run tests
pytest

# If issues, rollback
alembic downgrade -1
```

### Production Deployments

1. **Backup first**: Always backup before running migrations
2. **Apply during low traffic**: Schedule migration windows
3. **Monitor**: Watch for performance issues
4. **Have rollback plan**: Test downgrade path

### Handling Large Tables

For tables with millions of rows:

```python
def upgrade() -> None:
    # Add column with default value (PostgreSQL 11+ is fast)
    op.add_column('messages', 
        sa.Column('is_pinned', sa.Boolean(), 
                  server_default='false', nullable=False))
    
    # Or do in batches for very large tables
    connection = op.get_bind()
    while True:
        result = connection.execute(
            "UPDATE messages SET is_pinned = false "
            "WHERE is_pinned IS NULL LIMIT 10000"
        )
        if result.rowcount == 0:
            break
```

## Troubleshooting

### "No such revision"

```bash
# Check current state
alembic current
alembic heads

# Stamp to specific revision
alembic stamp head
```

### "Column already exists"

Use `IF NOT EXISTS` in SQL:

```python
op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS new_col TEXT")
```

### Multiple Heads

```bash
# Show all heads
alembic heads

# Merge heads
alembic merge heads -m "merge"
```

### Sync with Models

If models and database are out of sync:

```bash
# Generate migration from model diff
alembic revision --autogenerate -m "sync_models"

# Review generated migration
cat alembic/versions/XXX_sync_models.py

# Apply
alembic upgrade head
```

---

*For model documentation, see [Data Models](../architecture/data-models.md).*
