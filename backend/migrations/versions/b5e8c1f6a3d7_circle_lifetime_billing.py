"""WSF Circle: allow billing_interval 'lifetime'.

Constraint-only. billing_interval is guarded on circle_plans
(ck_circle_plans_billing_interval) and snapshotted on circle_payments
(ck_circle_payments_billing_interval); both are widened from
('monthly', 'yearly') to ('monthly', 'yearly', 'lifetime'). No columns
change and no rows are rewritten. Downgrade restores the previous pair and
refuses while any plan or payment uses 'lifetime'.

Revision ID: b5e8c1f6a3d7
Revises: a4d7b0e5f2c6
"""
from alembic import op
import sqlalchemy as sa

revision = "b5e8c1f6a3d7"
down_revision = "a4d7b0e5f2c6"
branch_labels = None
depends_on = None

_PREVIOUS = ("monthly", "yearly")
_NEW = ("lifetime",)
_TABLES = (("circle_plans", "ck_circle_plans_billing_interval"), ("circle_payments", "ck_circle_payments_billing_interval"))


def _check(values):
    return "billing_interval IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade():
    for table, name in _TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(name, type_="check")
            batch_op.create_check_constraint(name, _check(_PREVIOUS + _NEW))


def downgrade():
    bind = op.get_bind()
    for table, _name in _TABLES:
        if bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE billing_interval = 'lifetime'")).scalar():
            raise RuntimeError(f"Cannot downgrade: {table} still has lifetime rows.")
    for table, name in _TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(name, type_="check")
            batch_op.create_check_constraint(name, _check(_PREVIOUS))
