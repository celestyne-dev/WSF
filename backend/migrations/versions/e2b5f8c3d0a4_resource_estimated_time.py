"""WSF Career Hub: optional estimated time on Resources.

Adds three nullable columns (estimated_time_value, estimated_time_max_value,
estimated_time_unit) and their consistency CHECK. Existing rows get NULLs,
which mean "no estimate" and satisfy the constraint. Downgrade drops only
these columns and the constraint.

Revision ID: e2b5f8c3d0a4
Revises: d1a4e7b2c9f3
"""
from alembic import op
import sqlalchemy as sa

revision = "e2b5f8c3d0a4"
down_revision = "d1a4e7b2c9f3"
branch_labels = None
depends_on = None

_CHECK = (
    "(estimated_time_unit IS NULL AND estimated_time_value IS NULL AND estimated_time_max_value IS NULL)"
    " OR (estimated_time_unit = 'self_paced' AND estimated_time_value IS NULL AND estimated_time_max_value IS NULL)"
    " OR (estimated_time_unit IN ('minutes', 'hours', 'days', 'weeks') AND estimated_time_value > 0"
    " AND (estimated_time_max_value IS NULL OR estimated_time_max_value > estimated_time_value))"
)


def upgrade():
    with op.batch_alter_table("resources", schema=None) as batch_op:
        batch_op.add_column(sa.Column("estimated_time_value", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("estimated_time_max_value", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("estimated_time_unit", sa.String(length=12), nullable=True))
        batch_op.create_check_constraint("ck_resources_estimated_time", _CHECK)


def downgrade():
    with op.batch_alter_table("resources", schema=None) as batch_op:
        batch_op.drop_constraint("ck_resources_estimated_time", type_="check")
        batch_op.drop_column("estimated_time_unit")
        batch_op.drop_column("estimated_time_max_value")
        batch_op.drop_column("estimated_time_value")
