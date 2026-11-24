"""Retention engine (Step 17): users.inactivity_warning_sent_at.

Revision ID: a1d6f2b8c4e0
Revises: f9c5e1a3b7d2
"""
from alembic import op
import sqlalchemy as sa

revision = "a1d6f2b8c4e0"
down_revision = "f9c5e1a3b7d2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("inactivity_warning_sent_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("users", "inactivity_warning_sent_at")
