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


async def _connect(db_url):
    """Connect to the database, handling SSL automatically."""
    import asyncpg

    # First try connecting with the URL as-is (sslmode may already be in the URL)
    try:
        return await asyncpg.connect(db_url)
    except Exception:
        pass

    # Fall back to explicit SSL context (for managed DBs without sslmode in URL)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(db_url, ssl=ssl_ctx)


async def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        return

    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    db_url = db_url.replace("postgres://", "postgresql://")

    print("Connecting to database...")
    conn = await _connect(db_url)

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
