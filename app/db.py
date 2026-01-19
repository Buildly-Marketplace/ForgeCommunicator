"""
Database configuration with SQLAlchemy 2.0 async support.
"""

import asyncio
import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.settings import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def _get_connect_args() -> dict:
    """Get connection arguments, including SSL for managed databases."""
    connect_args = {}
    
    # DigitalOcean and other managed databases require SSL
    # Check if the URL contains sslmode or if we should enable SSL by default
    db_url = settings.database_url
    if "sslmode=" not in db_url and "localhost" not in db_url and "127.0.0.1" not in db_url:
        # Create SSL context for managed databases
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE  # DO managed DBs use self-signed certs
        connect_args["ssl"] = ssl_context
    
    return connect_args


# Create async engine
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.debug,
    connect_args=_get_connect_args(),
    pool_pre_ping=True,  # Verify connections before using
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions (for use outside of FastAPI)."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database (create tables if needed) with retry logic."""
    import sys
    
    max_retries = 5
    retry_delay = 3  # seconds
    
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                # Import all models to ensure they're registered
                from app.models import (  # noqa: F401
                    artifact,
                    channel,
                    membership,
                    message,
                    product,
                    push_subscription,
                    user,
                    workspace,
                )
                await conn.run_sync(Base.metadata.create_all)
                print(f"Database initialized successfully", file=sys.stderr)
                return
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}", file=sys.stderr)
                print(f"Retrying in {retry_delay} seconds...", file=sys.stderr)
                await asyncio.sleep(retry_delay)
            else:
                print(f"Database connection failed after {max_retries} attempts", file=sys.stderr)
                raise


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
