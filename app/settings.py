"""
Application settings using Pydantic BaseSettings.
All secrets and configuration via environment variables.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Forge Communicator"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production-use-openssl-rand-hex-32")
    
    # Server
    host: str = "0.0.0.0"
    port: int = Field(default=8000, alias="PORT")
    
    # Build info (set by CI/CD)
    build_sha: str = Field(default="dev", alias="BUILD_SHA")
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator",
        alias="DATABASE_URL",
    )
    database_pool_size: int = 5
    database_max_overflow: int = 10
    
    @field_validator("database_url", mode="before")
    @classmethod
    def transform_database_url(cls, v: str) -> str:
        """Transform database URL to use asyncpg driver.
        
        Many deployment platforms provide postgres:// URLs that need
        to be converted to postgresql+asyncpg:// for SQLAlchemy async.
        Also removes sslmode parameter since asyncpg handles SSL differently.
        """
        import sys
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
        
        if not v:
            return "postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator"
        
        # Strip whitespace
        v = v.strip()
        
        # Handle ${...} variable substitution syntax (not yet resolved)
        if v.startswith("${") or not v:
            return "postgresql+asyncpg://forge:forge@localhost:5432/forge_communicator"
        
        # Log what we got for debugging
        print(f"DATABASE_URL received: {v[:60]}...", file=sys.stderr)
        
        # Handle postgres:// -> postgresql+asyncpg://
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        # Handle postgresql:// without driver -> postgresql+asyncpg://
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Remove sslmode from query string (asyncpg doesn't support it as URL param)
        # We handle SSL via connect_args instead
        try:
            parsed = urlparse(v)
            if parsed.query:
                query_params = parse_qs(parsed.query)
                # Remove sslmode - we'll handle it in connect_args
                query_params.pop("sslmode", None)
                # Rebuild URL without sslmode
                new_query = urlencode(query_params, doseq=True)
                v = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                ))
        except Exception as e:
            print(f"Warning: Could not parse DATABASE_URL query params: {e}", file=sys.stderr)
        
        print(f"DATABASE_URL transformed: {v[:60]}...", file=sys.stderr)
        return v
    
    # For sync operations (Alembic)
    @computed_field
    @property
    def database_url_sync(self) -> str:
        """Convert async URL to sync for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "").replace("+aiopg", "")
    
    # Realtime mode
    realtime_mode: Literal["ws", "poll"] = "ws"
    poll_interval_seconds: int = 3
    
    # Auth - Local
    password_min_length: int = 8
    session_expire_hours: int = 24
    
    # Auth - Google OAuth
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    google_allowed_domain: str | None = None  # Restrict to this Google Workspace domain
    
    # Auth - Buildly Labs OAuth
    buildly_client_id: str | None = None
    buildly_client_secret: str | None = None
    buildly_redirect_uri: str | None = None
    buildly_api_url: str = "https://api.buildly.io"
    buildly_auth_url: str = "https://auth.buildly.io"
    
    # Buildly Labs API (for syncing)
    labs_api_key: str | None = None
    labs_api_url: str = "http://labs.buildly.io/api/v1"
    
    # Rate limiting
    rate_limit_auth_per_minute: int = 10
    rate_limit_api_per_minute: int = 60
    
    # Push notifications (VAPID)
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_contact_email: str = "admin@buildly.io"
    
    # CORS (for API access if needed)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    
    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)
    
    @property
    def buildly_oauth_enabled(self) -> bool:
        return bool(self.buildly_client_id and self.buildly_client_secret)
    
    @property
    def push_enabled(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
