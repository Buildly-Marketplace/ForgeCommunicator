# AI Assistant Instructions for Forge Communicator

This folder contains instructions for AI assistants (GitHub Copilot, Claude, etc.) to help them understand and work effectively with the Forge Communicator codebase following Buildly Forge standards.

## Instruction Files

| File | Purpose |
|------|---------|
| [overview.md](./overview.md) | Project overview and architecture |
| [coding-standards.md](./coding-standards.md) | Code style and conventions |
| [testing-guidelines.md](./testing-guidelines.md) | Testing requirements and patterns |
| [data-management.md](./data-management.md) | Database and data handling rules |
| [documentation-standards.md](./documentation-standards.md) | Documentation requirements |
| [security.md](./security.md) | Security considerations |

## Quick Context for AI

**Project:** Forge Communicator - Real-time team communication platform  
**Stack:** FastAPI, PostgreSQL (async), HTMX, Jinja2, WebSockets  
**Python:** 3.11+  
**Formatter:** Ruff (line length 100)  
**Tests:** pytest with async support  

### Key Patterns

1. **Async-first**: All database operations use SQLAlchemy async
2. **Dependency injection**: Use FastAPI `Depends()` pattern
3. **Service layer**: Business logic in `app/services/`
4. **Multi-tenant**: Data isolated by Workspace

### Important Directories

- `app/models/` - SQLAlchemy ORM models
- `app/routers/` - FastAPI route handlers
- `app/services/` - Business logic services
- `app/templates/` - Jinja2 templates
- `tests/` - Test suite
- `alembic/versions/` - Database migrations

---

*Always read the relevant instruction file before making changes to ensure compliance with Buildly Forge standards.*
