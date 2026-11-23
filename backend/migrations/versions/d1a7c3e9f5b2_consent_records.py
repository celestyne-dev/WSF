"""Consent records: account-linked cookie-consent history.

- consent_records: one row per distinct consent decision made by a
  signed-in member (version, three optional categories, decision time).
  No IP address or device identifier is stored.

New table only; nothing existing changes. Downgrade drops the table.

Revision ID: d1a7c3e9f5b2
Revises: c9f1e3a5b7d2
"""
from alembic import op
import sqlalchemy as sa

revision = "d1a7c3e9f5b2"
down_revision = "c9f1e3a5b7d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("consent_version", sa.String(length=20), nullable=False),
        sa.Column("preferences", sa.Boolean(), nullable=False),
        sa.Column("analytics", sa.Boolean(), nullable=False),
        sa.Column("marketing", sa.Boolean(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "decided_at", "consent_version", name="uq_consent_records_user_decision"),
    )
    op.create_index("ix_consent_records_user_recorded", "consent_records", ["user_id", "recorded_at"])


def downgrade():
    op.drop_index("ix_consent_records_user_recorded", table_name="consent_records")
    op.drop_table("consent_records")
