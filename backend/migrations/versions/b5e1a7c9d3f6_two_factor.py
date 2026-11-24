"""TOTP two-factor authentication.

- user_two_factor: encrypted TOTP secret (and a pending one during set-up),
  enabled time, last used time-step (replay protection).
- two_factor_recovery_codes: one-use recovery codes stored as keyed hashes.
- refresh_sessions.two_factor_verified: whether the sign-in that created the
  session passed a 2FA check (existing rows: false).

Downgrade drops the column and both tables: every enrolled user would have
to set up 2FA again after a re-upgrade.

Revision ID: b5e1a7c9d3f6
Revises: a4d0f6b8c3e5
"""
from alembic import op
import sqlalchemy as sa

revision = "b5e1a7c9d3f6"
down_revision = "a4d0f6b8c3e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_two_factor",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("secret_encrypted", sa.Text()),
        sa.Column("pending_secret_encrypted", sa.Text()),
        sa.Column("enabled_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_step", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "two_factor_recovery_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_two_factor_recovery_codes_user_id", "two_factor_recovery_codes", ["user_id"])
    op.add_column("refresh_sessions", sa.Column("two_factor_verified", sa.Boolean(), nullable=False,
                                                server_default=sa.false()))


def downgrade():
    op.drop_column("refresh_sessions", "two_factor_verified")
    op.drop_index("ix_two_factor_recovery_codes_user_id", table_name="two_factor_recovery_codes")
    op.drop_table("two_factor_recovery_codes")
    op.drop_table("user_two_factor")
