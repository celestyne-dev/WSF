"""Minimum age at signup (Step 18): confirmation timestamp, the age it was
confirmed against, and the Terms/Privacy versions accepted.

Revision ID: b3e8c1d5f7a2
Revises: a1d6f2b8c4e0
"""
from alembic import op
import sqlalchemy as sa

revision = "b3e8c1d5f7a2"
down_revision = "a1d6f2b8c4e0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("age_confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("age_confirmed_minimum", sa.SmallInteger()))
    op.add_column("users", sa.Column("terms_version_accepted", sa.String(120)))
    op.add_column("users", sa.Column("privacy_version_accepted", sa.String(120)))
    op.add_column("users", sa.Column("legal_accepted_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("users", "legal_accepted_at")
    op.drop_column("users", "privacy_version_accepted")
    op.drop_column("users", "terms_version_accepted")
    op.drop_column("users", "age_confirmed_minimum")
    op.drop_column("users", "age_confirmed_at")
