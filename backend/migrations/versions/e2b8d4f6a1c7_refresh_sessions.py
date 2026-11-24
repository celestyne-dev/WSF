"""Refresh sessions: revocable server records behind the HttpOnly refresh cookie.

- refresh_sessions: one row per signed-in browser session; stores only a
  SHA-256 hash of the opaque cookie token, the user's auth_version at
  sign-in, expiry, last use and revocation.

New table only. Existing JWT refresh tokens held in browsers' localStorage
are not migrated: the new frontend deletes them and members sign in once.
Downgrade drops the table (every cookie session ends).

Revision ID: e2b8d4f6a1c7
Revises: d1a7c3e9f5b2
"""
from alembic import op
import sqlalchemy as sa

revision = "e2b8d4f6a1c7"
down_revision = "d1a7c3e9f5b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(length=30)),
    )
    op.create_index("ix_refresh_sessions_user_active", "refresh_sessions", ["user_id", "revoked_at"])


def downgrade():
    op.drop_index("ix_refresh_sessions_user_active", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
