# Data Management Guidelines

This document covers database and data handling standards for Forge Communicator following Buildly Forge best practices.

## Database Architecture

### Technology Stack

- **Database**: PostgreSQL 14+
- **ORM**: SQLAlchemy 2.0 with async support
- **Driver**: asyncpg
- **Migrations**: Alembic

### Connection Management

The application uses connection pooling:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=5,           # Base pool size
    max_overflow=10,       # Additional connections when needed
    pool_pre_ping=True,    # Validate connections before use
)
```

## Working with Models

### Creating New Models

When adding a new model:

1. **Create model file** in `app/models/`
2. **Include TimestampMixin** for audit fields
3. **Export from `__init__.py`**
4. **Create migration**

```python
# app/models/new_model.py

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class NewModel(Base, TimestampMixin):
    """Description of the model.
    
    Attributes:
        id: Primary key.
        name: The name field.
        workspace_id: Foreign key to workspace.
    """
    
    __tablename__ = "new_models"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="new_models")
```

### Adding Model Fields

When adding fields to existing models:

1. **Update the model class**
2. **Create an Alembic migration**
3. **Update any affected services/routers**

```python
# Add to model
class User(Base, TimestampMixin):
    ...
    new_field: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

```bash
# Create migration
alembic revision --autogenerate -m "add_new_field_to_users"

# Review and apply
alembic upgrade head
```

### Model Relationships

Use appropriate relationship loading strategies:

```python
class User(Base):
    # selectin: Load when parent is loaded (good for small collections)
    memberships = relationship("Membership", back_populates="user", lazy="selectin")
    
    # noload: Don't auto-load (explicit query required)
    messages = relationship("Message", back_populates="user", lazy="noload")
```

When querying with relationships:

```python
from sqlalchemy.orm import selectinload, joinedload

# Eager load relationships
result = await db.execute(
    select(User)
    .options(selectinload(User.memberships))
    .where(User.id == user_id)
)
```

## Database Queries

### Query Patterns

Always use async SQLAlchemy:

```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Get single record
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()  # Returns None if not found

# Get single record (raise if not found)
user = result.scalar_one()  # Raises NoResultFound

# Get list of records
result = await db.execute(
    select(Message)
    .where(Message.channel_id == channel_id)
    .order_by(Message.created_at.desc())
    .limit(50)
)
messages = result.scalars().all()

# Count records
result = await db.execute(
    select(func.count()).select_from(Message).where(Message.channel_id == channel_id)
)
count = result.scalar()
```

### Multi-Tenant Queries

Always filter by workspace context:

```python
# ✅ Good - scoped to workspace
result = await db.execute(
    select(Channel)
    .where(Channel.workspace_id == workspace.id)
    .where(Channel.name == channel_name)
)

# ❌ Bad - no tenant isolation
result = await db.execute(
    select(Channel).where(Channel.name == channel_name)
)
```

### Pagination

Use limit/offset for pagination:

```python
async def get_messages(
    db: AsyncSession,
    channel_id: int,
    page: int = 1,
    per_page: int = 50
) -> list[Message]:
    offset = (page - 1) * per_page
    
    result = await db.execute(
        select(Message)
        .where(Message.channel_id == channel_id)
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    return result.scalars().all()
```

## Migrations

### Creating Migrations

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "description_of_change"

# Create empty migration (for data migrations)
alembic revision -m "description_of_change"
```

### Migration Best Practices

1. **Use IF NOT EXISTS** for safety:

```python
def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS new_col TEXT")
```

2. **Always implement downgrade**:

```python
def downgrade() -> None:
    op.drop_column("users", "new_col")
```

3. **Handle data migrations carefully**:

```python
def upgrade() -> None:
    # Add new column
    op.add_column('users', sa.Column('status', sa.String(20)))
    
    # Migrate existing data
    op.execute("UPDATE users SET status = 'active' WHERE is_active = true")
    op.execute("UPDATE users SET status = 'inactive' WHERE is_active = false")
```

### Sequential Naming

Use sequential numbered names:

```
001_initial.py
002_add_feature.py
003_add_another_feature.py
```

## Data Validation

### At the Model Level

Use SQLAlchemy constraints:

```python
class User(Base):
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,      # Database constraint
        nullable=False,
        index=True
    )
```

### At the API Level

Use Pydantic models for request validation:

```python
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
```

### At the Service Level

Add business logic validation:

```python
async def create_user(db: AsyncSession, email: str, display_name: str) -> User:
    # Check for existing user
    existing = await get_by_email(db, email)
    if existing:
        raise ValueError("Email already registered")
    
    # Create user
    user = User(email=email.lower(), display_name=display_name)
    db.add(user)
    await db.flush()
    return user
```

## Transaction Management

### Default Behavior

The `get_db` dependency auto-commits on success, rolls back on error:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Manual Transaction Control

For complex operations:

```python
async def complex_operation(db: AsyncSession):
    try:
        # Create user
        user = User(email="test@example.com")
        db.add(user)
        await db.flush()  # Get user.id without committing
        
        # Create related records
        membership = Membership(user_id=user.id, workspace_id=1)
        db.add(membership)
        
        # Commit everything
        await db.commit()
    except Exception:
        await db.rollback()
        raise
```

## Soft Deletes

For important data, use soft deletes:

```python
class User(Base):
    is_active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

# "Delete" user
user.is_active = False
user.deleted_at = datetime.utcnow()

# Query only active users
select(User).where(User.is_active == True)
```

## Data Security

### Sensitive Data

Never log or expose:

- Passwords (even hashed)
- OAuth tokens
- API keys
- Session tokens

```python
# ✅ Good
logger.info("User %s logged in", user.email)

# ❌ Bad
logger.info("User logged in with token %s", session_token)
```

### Query Safety

Always use parameterized queries (SQLAlchemy does this automatically):

```python
# ✅ Safe - parameterized
result = await db.execute(
    select(User).where(User.email == user_input)
)

# ❌ Dangerous - string interpolation
result = await db.execute(f"SELECT * FROM users WHERE email = '{user_input}'")
```

## Checklist for AI

When working with data:

- [ ] Use async SQLAlchemy patterns
- [ ] Filter by workspace for multi-tenant queries
- [ ] Create migrations for schema changes
- [ ] Include both upgrade and downgrade in migrations
- [ ] Use parameterized queries (never interpolate)
- [ ] Validate data at API and service layers
- [ ] Consider soft deletes for important data
- [ ] Never log sensitive data

---

*See [security.md](./security.md) for additional security guidelines.*
