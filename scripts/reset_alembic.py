"""
Reset alembic_version table and stamp to new single migration.

Run on the server BEFORE deploying the new migration:

    python scripts/reset_alembic.py

This will:
1. Delete all rows from alembic_version
2. Insert '001' so alembic thinks the single migration has already run
   (since the tables already exist in production)
"""

import asyncio
import os
import ssl
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def prepare_db_url(raw_url):
    """Prepare DATABASE_URL for asyncpg: fix scheme and strip sslmode."""
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgres://", "postgresql://")
    # Strip sslmode from query params (asyncpg can't handle it as a URL param)
    parsed = urlparse(url)
    if parsed.query:
        params = parse_qs(parsed.query)
        params.pop("sslmode", None)
        url = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, urlencode(params, doseq=True), parsed.fragment,
        ))
    return url


def needs_ssl(url):
    """Check if the database host requires SSL."""
    local_hosts = ["localhost", "127.0.0.1", "@db:", "@db/", "@postgres:", "@postgres/"]
    return not any(h in url for h in local_hosts)


async def main():
    import asyncpg

    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url:
        print("ERROR: DATABASE_URL not set")
        return

    db_url = prepare_db_url(raw_url)

    connect_kwargs = {}
    if needs_ssl(db_url):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_kwargs["ssl"] = ssl_ctx

    print("Connecting to database...")
    conn = await asyncpg.connect(db_url, **connect_kwargs)

    try:
        # Check current state
        rows = await conn.fetch("SELECT version_num FROM alembic_version")
        print(f"Current alembic_version rows: {[r['version_num'] for r in rows]}")

        # Clear and stamp
        await conn.execute("DELETE FROM alembic_version")
        await conn.execute("INSERT INTO alembic_version (version_num) VALUES ($1)", "001")

        # Verify
        rows = await conn.fetch("SELECT version_num FROM alembic_version")
        print(f"After reset: {[r['version_num'] for r in rows]}")
        print("SUCCESS - alembic_version reset to '001'")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
