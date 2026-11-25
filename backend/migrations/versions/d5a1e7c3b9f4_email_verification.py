"""Email verification (Batch 4 corrections): users.email_verified_at,
users.email_verification_required, email_verification_tokens.

Existing accounts are NOT marked verified (users.is_verified was never proof
of ownership) and NOT required to verify (access preserved).

Revision ID: d5a1e7c3b9f4
Revises: c4f9d2e6a8b1
"""
from alembic import op
import sqlalchemy as sa

revision = "d5a1e7c3b9f4"
down_revision = "c4f9d2e6a8b1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("email_verification_required", sa.Boolean(), nullable=False,
                                     server_default=sa.false()))
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])
    op.create_index("ix_email_verification_tokens_token_hash", "email_verification_tokens", ["token_hash"], unique=True)


def downgrade():
    op.drop_index("ix_email_verification_tokens_token_hash", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verification_required")
    op.drop_column("users", "email_verified_at")
