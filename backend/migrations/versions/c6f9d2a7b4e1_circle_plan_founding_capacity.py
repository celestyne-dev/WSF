"""WSF Circle: optional plan capacity and Founding designation.

Adds circle_plans.max_members (nullable, > 0 when set; NULL = unlimited)
and circle_plans.is_founding (NOT NULL, server default false). Existing
plans become unlimited, non-founding — no row values change. Downgrade
drops only these two columns and the constraint.

Revision ID: c6f9d2a7b4e1
Revises: b5e8c1f6a3d7
"""
from alembic import op
import sqlalchemy as sa

revision = "c6f9d2a7b4e1"
down_revision = "b5e8c1f6a3d7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("circle_plans", schema=None) as batch_op:
        batch_op.add_column(sa.Column("max_members", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("is_founding", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_check_constraint("ck_circle_plans_max_members_positive", "max_members IS NULL OR max_members > 0")


def downgrade():
    with op.batch_alter_table("circle_plans", schema=None) as batch_op:
        batch_op.drop_constraint("ck_circle_plans_max_members_positive", type_="check")
        batch_op.drop_column("is_founding")
        batch_op.drop_column("max_members")
