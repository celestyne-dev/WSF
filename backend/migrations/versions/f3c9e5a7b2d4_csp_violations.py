"""CSP violation reports: aggregated, non-identifying.

- csp_violations: one row per (directive, blocked origin, page path) with a
  count and first/last seen. No IP, user agent or query strings.

New table only. Downgrade drops it (only diagnostic data is lost).

Revision ID: f3c9e5a7b2d4
Revises: e2b8d4f6a1c7
"""
from alembic import op
import sqlalchemy as sa

revision = "f3c9e5a7b2d4"
down_revision = "e2b8d4f6a1c7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "csp_violations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("directive", sa.String(length=60), nullable=False),
        sa.Column("blocked", sa.String(length=200), nullable=False),
        sa.Column("page_path", sa.String(length=300), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("directive", "blocked", "page_path", name="uq_csp_violations_key"),
    )


def downgrade():
    op.drop_table("csp_violations")
