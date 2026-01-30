# Security Guidelines

This document covers security best practices for Forge Communicator. AI assistants should follow these guidelines when generating or modifying code.

## Authentication

### Session Management

Sessions use secure, random tokens:

```python
import secrets

def generate_session_token() -> str:
    """Generate cryptographically secure session token."""
    return secrets.token_hex(32)  # 64 character hex string
```

Session tokens must:
- Be at least 256 bits (32 bytes)
- Be generated using `secrets` module
- Have expiration times
- Be stored securely (not in logs)

### Password Handling

**NEVER** store plaintext passwords:

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain, hashed)
```

Password requirements:
- Minimum 8 characters
- Hash with bcrypt (cost factor 12)
- Never log passwords (even hashed)

### OAuth Security

For OAuth flows:

```python
# ✅ Good - use state parameter to prevent CSRF
state = secrets.token_urlsafe(32)
session["oauth_state"] = state

# Verify state on callback
if request.args.get("state") != session.get("oauth_state"):
    raise HTTPException(status_code=400, detail="Invalid state")
```

## Authorization

### Role-Based Access Control

Check permissions before actions:

```python
async def require_workspace_admin(
    user: User,
    workspace: Workspace,
    db: AsyncSession
) -> None:
    """Verify user is workspace admin."""
    membership = await get_membership(db, user.id, workspace.id)
    
    if not membership or membership.role not in (MembershipRole.ADMIN, MembershipRole.OWNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
```

### Resource Access

Always verify user can access resource:

```python
@router.get("/channels/{channel_id}/messages")
async def get_messages(
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
):
    # ✅ Good - verify membership
    channel = await get_channel(db, channel_id)
    if not await user_can_access_channel(db, user.id, channel):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Now safe to fetch messages
    return await get_channel_messages(db, channel_id)
```

### Multi-Tenant Isolation

Always scope queries to workspace:

```python
# ✅ Good - scoped to workspace
messages = await db.execute(
    select(Message)
    .join(Channel)
    .where(Channel.workspace_id == workspace.id)
    .where(Channel.id == channel_id)
)

# ❌ Bad - no tenant isolation
messages = await db.execute(
    select(Message).where(Message.channel_id == channel_id)
)
```

## Input Validation

### SQL Injection Prevention

Always use parameterized queries:

```python
# ✅ Safe - SQLAlchemy parameterization
result = await db.execute(
    select(User).where(User.email == email_input)
)

# ✅ Safe - explicit parameters
result = await db.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": email_input}
)

# ❌ DANGEROUS - string interpolation
result = await db.execute(f"SELECT * FROM users WHERE email = '{email_input}'")
```

### XSS Prevention

Jinja2 auto-escapes by default. Be careful with:

```python
# ✅ Safe - auto-escaped
{{ user.display_name }}

# ⚠️ Dangerous - raw HTML (use only for trusted content)
{{ user_provided_html | safe }}
```

For user-generated content:

```python
import bleach

def sanitize_html(content: str) -> str:
    """Sanitize user HTML content."""
    allowed_tags = ['p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li']
    allowed_attrs = {'a': ['href']}
    return bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs)
```

### Request Validation

Validate all inputs with Pydantic:

```python
from pydantic import BaseModel, EmailStr, Field, validator

class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    
    @validator('display_name')
    def sanitize_display_name(cls, v):
        # Remove potentially dangerous characters
        return v.strip()
```

## Rate Limiting

Protect against brute force:

```python
from app.services.rate_limiter import auth_rate_limiter

@router.post("/login")
async def login(request: Request, ...):
    client_ip = get_client_ip(request)
    
    if not auth_rate_limiter.is_allowed(f"login:{client_ip}"):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again later."
        )
```

Rate limit recommendations:
- Login: 5 attempts/minute/IP
- Registration: 10/hour/IP
- Password reset: 3/hour/email
- API: 100 requests/minute/user

## Sensitive Data Handling

### Data Classification

| Level | Examples | Handling |
|-------|----------|----------|
| **Critical** | Passwords, OAuth tokens | Never log, encrypt at rest |
| **Sensitive** | Email, phone | Mask in logs, access control |
| **Internal** | User IDs, timestamps | Standard security |
| **Public** | Display names | No special handling |

### Logging Guidelines

```python
import logging

logger = logging.getLogger(__name__)

# ✅ Good - log action, not secrets
logger.info("User %s logged in from %s", user.id, client_ip)
logger.info("Password reset requested for user %s", user.id)

# ❌ Bad - exposes sensitive data
logger.info("User logged in with password %s", password)
logger.info("OAuth token: %s", access_token)
logger.debug("Session cookie: %s", session_token)
```

### Error Messages

Don't leak information in errors:

```python
# ✅ Good - generic message
raise HTTPException(status_code=401, detail="Invalid credentials")

# ❌ Bad - reveals if email exists
raise HTTPException(status_code=401, detail="Invalid password for user@example.com")
```

## HTTPS & Headers

### Security Headers

Configure in production:

```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Force HTTPS in production
if not settings.debug:
    app.add_middleware(HTTPSRedirectMiddleware)

# Secure session cookies
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=not settings.debug,
)
```

### CORS Configuration

Be specific about allowed origins:

```python
# ✅ Good - specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com", "https://admin.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ⚠️ Development only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Only in debug mode!
)
```

## Dependency Security

### Keep Dependencies Updated

```bash
# Check for vulnerabilities
pip-audit

# Update requirements
pip install --upgrade -r requirements.txt
```

### Pin Versions

In `requirements.txt`:

```
fastapi==0.109.0
sqlalchemy==2.0.25
pydantic==2.5.3
```

## Security Checklist for AI

When generating code, verify:

- [ ] No hardcoded secrets or credentials
- [ ] Passwords are hashed with bcrypt
- [ ] SQL uses parameterized queries
- [ ] User input is validated
- [ ] Authorization checks before data access
- [ ] Queries scoped to workspace (multi-tenant)
- [ ] Sensitive data not in logs
- [ ] Error messages don't leak information
- [ ] Rate limiting on auth endpoints

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do not** open a public issue
2. Email security@buildly.io
3. Include details and reproduction steps
4. Allow 90 days for fix before disclosure

---

*Security is everyone's responsibility. When in doubt, ask for review.*
