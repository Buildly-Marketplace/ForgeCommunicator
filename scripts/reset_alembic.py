"""
Reset alembic_version table and stamp to new single migration.

Run on the server:

    python -m scripts.reset_alembic

Uses the app's own database engine so SSL/connection config is identical
to the running application.
"""

import asyncio

from sqlalchemy import text

from app.db import engine


async def main():
    print("Connecting to database...")
    async with engine.begin() as conn:
        rows = (await conn.execute(text("SELECT version_num FROM alembic_version"))).fetchall()
        print(f"Current alembic_version rows: {[r[0] for r in rows]}")

        await conn.execute(text("DELETE FROM alembic_version"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('001')"))

        rows = (await conn.execute(text("SELECT version_num FROM alembic_version"))).fetchall()
        print(f"After reset: {[r[0] for r in rows]}")
        print("SUCCESS - alembic_version reset to '001'")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
