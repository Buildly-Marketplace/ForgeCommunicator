# Data Models

This document describes the SQLAlchemy ORM models used in Forge Communicator.

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      User       │       │    Workspace    │       │     Channel     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ email           │       │ name            │       │ name            │
│ display_name    │       │ slug            │       │ workspace_id(FK)│
│ bio             │       │ description     │       │ is_private      │
│ title           │       │ buildly_org_uuid│       │ topic           │
│ auth_provider   │       │ invite_code     │       └────────┬────────┘
│ is_platform_admin│      └────────┬────────┘                │
└────────┬────────┘                │                         │
         │                         │                         │
         │    ┌─────────────────┐  │    ┌──────────────────┐ │
         └────┤   Membership    ├──┘    │ChannelMembership ├─┘
              ├─────────────────┤       ├──────────────────┤
              │ user_id (FK)    │       │ user_id (FK)     │
              │ workspace_id(FK)│       │ channel_id (FK)  │
              │ role            │       │ role             │
              └─────────────────┘       └──────────────────┘

┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     Message     │       │    Artifact     │       │     Product     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ channel_id (FK) │       │ workspace_id(FK)│       │ workspace_id(FK)│
│ user_id (FK)    │       │ channel_id (FK) │       │ labs_product_id │
│ parent_id (FK)  │──┐    │ type            │       │ name            │
│ content         │  │    │ title           │       │ description     │
│ is_edited       │  │    │ status          │       └─────────────────┘
└─────────────────┘  │    └─────────────────┘
         ▲           │
         └───────────┘ (self-referential for threads)
```

## Core Models

### User

The primary identity model supporting multiple auth providers.

```python
class User(Base, TimestampMixin):
    __tablename__ = "users"
    
    id: Mapped[int]                    # Primary key
    email: Mapped[str]                 # Unique, indexed
    display_name: Mapped[str]          # Display name
    bio: Mapped[str | None]            # User biography
    title: Mapped[str | None]          # Job title
    phone: Mapped[str | None]          # Phone number
    timezone: Mapped[str | None]       # User timezone (default: UTC)
    status: Mapped[UserStatus]         # active, away, dnd, offline
    status_message: Mapped[str | None] # Custom status message
    
    # Authentication
    hashed_password: Mapped[str | None]     # For local auth
    auth_provider: Mapped[AuthProvider]     # local, google, buildly
    provider_sub: Mapped[str | None]        # OAuth subject ID
    
    # Buildly Labs SSO
    labs_user_id: Mapped[int | None]        # Labs numeric user ID
    labs_org_uuid: Mapped[str | None]       # Labs organization UUID
    labs_access_token: Mapped[str | None]
    labs_refresh_token: Mapped[str | None]
    labs_token_expires_at: Mapped[datetime | None]
    
    # Buildly CollabHub (community/profile sync)
    collabhub_user_uuid: Mapped[str | None]    # CollabHub user UUID
    collabhub_org_uuid: Mapped[str | None]     # CollabHub organization UUID
    collabhub_synced_at: Mapped[datetime | None]  # Last sync timestamp
    
    # Social Profiles (synced across Labs/CollabHub)
    github_url: Mapped[str | None]          # GitHub profile URL
    linkedin_url: Mapped[str | None]        # LinkedIn profile URL
    twitter_url: Mapped[str | None]         # Twitter/X profile URL
    website_url: Mapped[str | None]         # Personal website URL
    
    # Community Stats (from CollabHub)
    community_reputation: Mapped[int | None]    # Reputation score
    projects_count: Mapped[int | None]          # Number of projects
    contributions_count: Mapped[int | None]     # Number of contributions
    collabhub_roles: Mapped[dict | None]        # {"community": "member", "dev_team": true, "customer": false}
    
    # Google Integration
    google_sub: Mapped[str | None]
    google_access_token: Mapped[str | None]
    google_refresh_token: Mapped[str | None]
    google_token_expires_at: Mapped[datetime | None]
    google_calendar_status: Mapped[str | None]
    
    # Session
    session_token: Mapped[str | None]       # Unique, indexed
    session_expires_at: Mapped[datetime | None]
    
    # Flags
    is_active: Mapped[bool]                 # Account active
    is_platform_admin: Mapped[bool]         # Platform-wide admin
    last_seen_at: Mapped[datetime | None]
    avatar_url: Mapped[str | None]
```

**Enums:**
- `AuthProvider`: `local`, `google`, `buildly`
- `UserStatus`: `active`, `away`, `dnd`, `offline`

### Workspace

Multi-tenant organization container.

```python
class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    
    id: Mapped[int]                    # Primary key
    name: Mapped[str]                  # Workspace name
    slug: Mapped[str]                  # Unique URL slug
    description: Mapped[str | None]
    
    # Google Workspace integration
    google_domain: Mapped[str | None]
    google_auto_join: Mapped[bool]     # Auto-join users from domain
    
    # Buildly Labs integration
    buildly_org_uuid: Mapped[str | None]
    labs_api_token: Mapped[str | None]
    labs_access_token: Mapped[str | None]
    labs_refresh_token: Mapped[str | None]
    labs_token_expires_at: Mapped[datetime | None]
    labs_connected_by_id: Mapped[int | None]
    
    # Invite system
    invite_code: Mapped[str | None]         # Unique
    invite_expires_at: Mapped[datetime | None]
    
    icon_url: Mapped[str | None]
```

### Membership

Links users to workspaces with roles.

```python
class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    
    id: Mapped[int]
    user_id: Mapped[int]               # FK → users
    workspace_id: Mapped[int]          # FK → workspaces
    role: Mapped[MembershipRole]       # owner, admin, member
    
    # Relationships
    user: User
    workspace: Workspace
```

**Roles:**
- `owner`: Full workspace control, can delete workspace
- `admin`: Can manage members, channels, settings
- `member`: Standard access

### Channel

Communication channels within a workspace.

```python
class Channel(Base, TimestampMixin):
    __tablename__ = "channels"
    
    id: Mapped[int]
    workspace_id: Mapped[int]          # FK → workspaces
    name: Mapped[str]
    topic: Mapped[str | None]
    is_private: Mapped[bool]           # Private channels
    is_default: Mapped[bool]           # Auto-join on workspace join
    created_by_id: Mapped[int | None]  # FK → users
```

### Message

Messages with threading support.

```python
class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    
    id: Mapped[int]
    channel_id: Mapped[int]            # FK → channels
    user_id: Mapped[int]               # FK → users (author)
    parent_id: Mapped[int | None]      # FK → messages (thread parent)
    content: Mapped[str]               # Message text (Markdown)
    is_edited: Mapped[bool]
    edited_at: Mapped[datetime | None]
    
    # Relationships
    replies: list[Message]             # Thread replies
```

### Artifact

Project artifacts created from slash commands.

```python
class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"
    
    id: Mapped[int]
    workspace_id: Mapped[int]          # FK → workspaces
    channel_id: Mapped[int | None]     # FK → channels (origin)
    message_id: Mapped[int | None]     # FK → messages (origin)
    created_by_id: Mapped[int | None]  # FK → users
    
    type: Mapped[ArtifactType]         # decision, feature, issue, task
    title: Mapped[str]
    body: Mapped[str | None]
    status: Mapped[ArtifactStatus]     # open, in_progress, resolved, closed
    
    # Task-specific
    assignee_id: Mapped[int | None]    # FK → users
    due_date: Mapped[date | None]
    
    # Labs sync
    labs_artifact_id: Mapped[int | None]
    labs_synced_at: Mapped[datetime | None]
```

**Enums:**
- `ArtifactType`: `decision`, `feature`, `issue`, `task`
- `ArtifactStatus`: `open`, `in_progress`, `resolved`, `closed`

### PushSubscription

Web push notification subscriptions.

```python
class PushSubscription(Base, TimestampMixin):
    __tablename__ = "push_subscriptions"
    
    id: Mapped[int]
    user_id: Mapped[int]               # FK → users
    endpoint: Mapped[str]              # Push service endpoint
    p256dh_key: Mapped[str]            # Encryption key
    auth_key: Mapped[str]              # Auth key
```

## Mixins

### TimestampMixin

Provides automatic `created_at` and `updated_at` timestamps:

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
```

## Indexes

Key indexes for performance:

| Table | Column(s) | Type |
|-------|-----------|------|
| users | email | Unique |
| users | session_token | Unique |
| workspaces | slug | Unique |
| memberships | (user_id, workspace_id) | Unique |
| channels | (workspace_id, name) | Composite |
| messages | channel_id | Index |
| messages | parent_id | Index |

## Cascade Behavior

- **Workspace deletion**: Cascades to memberships, channels, messages, artifacts
- **User deletion**: Soft delete (is_active = false) to preserve message history
- **Channel deletion**: Cascades to messages and channel memberships

---

*For migration details, see [Database Migrations](../guides/migrations.md).*
