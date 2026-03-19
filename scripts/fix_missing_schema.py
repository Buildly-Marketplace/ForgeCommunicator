"""
Fix missing columns on production database.

Migrations 020-024 were stamped but never executed, so certain columns
and tables are missing. This script adds them idempotently.

Run on the server AFTER reset_alembic.py and BEFORE deploying new code:

    python scripts/fix_missing_schema.py
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
        # Helper: add column if not exists
        async def add_column(table, column, col_type, default=None):
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name=$1 AND column_name=$2)",
                table, column,
            )
            if exists:
                print(f"  ✓ {table}.{column} already exists")
                return
            sql = f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'
            if default is not None:
                sql += f" DEFAULT {default}"
            await conn.execute(sql)
            print(f"  + Added {table}.{column}")

        # Helper: check if table exists
        async def table_exists(table):
            return await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name=$1)",
                table,
            )

        # ── From migration 020 (add_missing_columns) ──
        print("\n=== Checking columns from migration 020 ===")
        # channels
        await add_column("channels", "product_id", "INTEGER REFERENCES products(id) ON DELETE SET NULL")
        await add_column("channels", "is_default", "BOOLEAN NOT NULL", "false")
        await add_column("channels", "is_archived", "BOOLEAN NOT NULL", "false")
        # memberships
        await add_column("memberships", "notifications_enabled", "BOOLEAN NOT NULL", "true")
        await add_column("memberships", "created_at", "TIMESTAMPTZ NOT NULL", "now()")
        await add_column("memberships", "updated_at", "TIMESTAMPTZ NOT NULL", "now()")
        # channel_memberships
        await add_column("channel_memberships", "last_read_message_id", "INTEGER")
        await add_column("channel_memberships", "created_at", "TIMESTAMPTZ NOT NULL", "now()")
        await add_column("channel_memberships", "updated_at", "TIMESTAMPTZ NOT NULL", "now()")
        # messages
        await add_column("messages", "external_source", "VARCHAR(20)")
        await add_column("messages", "external_message_id", "VARCHAR(255)")
        await add_column("messages", "external_channel_id", "VARCHAR(255)")
        await add_column("messages", "external_thread_ts", "VARCHAR(255)")
        await add_column("messages", "external_author_name", "VARCHAR(255)")
        await add_column("messages", "external_author_avatar", "TEXT")

        # ── From migration 017 (notify_all_messages) ──
        print("\n=== Checking notify_all_messages ===")
        await add_column("memberships", "notify_all_messages", "BOOLEAN NOT NULL", "false")

        # ── From migration 023 (thread_read_states) ──
        print("\n=== Checking thread_read_states table ===")
        if not await table_exists("thread_read_states"):
            await conn.execute("""
                CREATE TABLE thread_read_states (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    parent_message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    last_read_reply_id INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_thread_read_user_message UNIQUE (user_id, parent_message_id)
                )
            """)
            print("  + Created thread_read_states table")
        else:
            print("  ✓ thread_read_states already exists")

        # ── From migration 024 (account approval) ──
        print("\n=== Checking account approval columns ===")
        await add_column("users", "is_approved", "BOOLEAN NOT NULL", "true")
        await add_column("users", "approved_at", "TIMESTAMPTZ")
        await add_column("users", "approved_by_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL")
        await add_column("users", "can_create_workspaces", "BOOLEAN NOT NULL", "true")

        print("\n=== All schema fixes applied successfully ===")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
