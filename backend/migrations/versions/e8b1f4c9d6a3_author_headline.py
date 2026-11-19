"""Authors: optional professional headline.

Adds authors.headline (nullable VARCHAR(160)). Existing authors get NULL.
Downgrade drops only this column.

Revision ID: e8b1f4c9d6a3
Revises: d7a0e3b8c5f2
"""
from alembic import op
import sqlalchemy as sa

revision = "e8b1f4c9d6a3"
down_revision = "d7a0e3b8c5f2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("authors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("headline", sa.String(length=160), nullable=True))


def downgrade():
    with op.batch_alter_table("authors", schema=None) as batch_op:
        batch_op.drop_column("headline")
