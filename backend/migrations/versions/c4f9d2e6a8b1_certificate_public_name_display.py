"""Certificate privacy (Step 20): users.certificate_public_name — "full" or
"initials" on public certificate verification. Existing learners keep the
full name (the behaviour so far) until they choose initials.

Revision ID: c4f9d2e6a8b1
Revises: b3e8c1d5f7a2
"""
from alembic import op
import sqlalchemy as sa

revision = "c4f9d2e6a8b1"
down_revision = "b3e8c1d5f7a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("certificate_public_name", sa.String(10), nullable=False, server_default="full"))


def downgrade():
    op.drop_column("users", "certificate_public_name")
