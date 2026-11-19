"""Organizations: workplace practices (employer workplace profile).

Adds nullable organizations.workplace_practices (JSON list of controlled
practices, each with its claim source). Existing organizations keep null
(no workplace section). Downgrade drops the column.

Revision ID: e5b8d0f2a4c6
Revises: d4a7c9e1f3b5
"""
from alembic import op
import sqlalchemy as sa

revision = "e5b8d0f2a4c6"
down_revision = "d4a7c9e1f3b5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("workplace_practices", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.drop_column("workplace_practices")
