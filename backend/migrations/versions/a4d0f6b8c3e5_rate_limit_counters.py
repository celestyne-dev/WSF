"""Rate-limit counters: database fallback store when Redis is unavailable.

- rate_limit_counters: fixed-window counters (limiter key, count, window
  end). Used only while Redis is down; Redis is the normal shared store.

New table only. Downgrade drops it (only transient counters are lost).

Revision ID: a4d0f6b8c3e5
Revises: f3c9e5a7b2d4
"""
from alembic import op
import sqlalchemy as sa

revision = "a4d0f6b8c3e5"
down_revision = "f3c9e5a7b2d4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rate_limit_counters",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_counters_expires_at", "rate_limit_counters", ["expires_at"])


def downgrade():
    op.drop_index("ix_rate_limit_counters_expires_at", table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
