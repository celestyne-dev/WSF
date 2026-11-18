"""WSF Circle: snapshot Founding Lifetime status on subscriptions.

Adds circle_subscriptions.founding_lifetime (NOT NULL, server default
false). Existing subscriptions are NOT retroactively marked Founding.
Downgrade drops only this column.

Revision ID: d7a0e3b8c5f2
Revises: c6f9d2a7b4e1
"""
from alembic import op
import sqlalchemy as sa

revision = "d7a0e3b8c5f2"
down_revision = "c6f9d2a7b4e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("circle_subscriptions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("founding_lifetime", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table("circle_subscriptions", schema=None) as batch_op:
        batch_op.drop_column("founding_lifetime")
