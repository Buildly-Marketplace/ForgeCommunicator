"""Add api_tokens table for external service authentication.

Revision ID: 002
Revises: 001
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS to handle the table already existing
    # (e.g. from create_all or a broken previous deploy)
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id SERIAL PRIMARY KEY,
            token VARCHAR(64) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            revoked_at TIMESTAMP WITH TIME ZONE,
            last_used_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_tokens_token ON api_tokens(token)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_tokens_user_id ON api_tokens(user_id)")


def downgrade() -> None:
    op.drop_table("api_tokens")
