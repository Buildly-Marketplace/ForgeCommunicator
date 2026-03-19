"""
Fix missing columns on production database.

Migrations 020-024 were stamped but never executed, so certain columns
and tables are missing. This script adds them idempotently.

Run on the server:

    python -m scripts.fix_missing_schema

Uses the app's own database engine so SSL/connection config is identical
to the running application.
"""

import asyncio

from sqlalchemy import text

from app.db import engine


async def main():
    print("Connecting to database...")
    async with engine.begin() as conn:
        # Helper: add column if not exists
        async def add_column(table, column, col_type, default=None):
            result = await conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name=:t AND column_name=:c)"
            ), {"t": table, "c": column})
            exists = result.scalar()
            if exists:
                print(f"  ✓ {table}.{column} already exists")
                return
            sql = f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'
            if default is not None:
                sql += f" DEFAULT {default}"
            await conn.execute(text(sql))
            print(f"  + Added {table}.{column}")

        # Helper: check if table exists
        async def table_exists(table):
            result = await conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name=:t)"
            ), {"t": table})
            return result.scalar()

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
            await conn.execute(text("""
                CREATE TABLE thread_read_states (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    parent_message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    last_read_reply_id INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_thread_read_user_message UNIQUE (user_id, parent_message_id)
                )
            """))
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

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
