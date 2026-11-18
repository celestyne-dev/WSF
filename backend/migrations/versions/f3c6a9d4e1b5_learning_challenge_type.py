"""WSF Career Hub: allow program_type 'challenge' on learning programs.

Constraint-only widening of ck_learning_programs_type. Existing rows are
untouched. Downgrade restores the previous four types and refuses while
any program is a challenge.

Revision ID: f3c6a9d4e1b5
Revises: e2b5f8c3d0a4
"""
from alembic import op
import sqlalchemy as sa

revision = "f3c6a9d4e1b5"
down_revision = "e2b5f8c3d0a4"
branch_labels = None
depends_on = None

_PREVIOUS = ("course", "masterclass", "program", "learning_series")
_NEW = ("challenge",)


def _check(values):
    return "program_type IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade():
    with op.batch_alter_table("learning_programs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_learning_programs_type", type_="check")
        batch_op.create_check_constraint("ck_learning_programs_type", _check(_PREVIOUS + _NEW))


def downgrade():
    in_use = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM learning_programs WHERE program_type = 'challenge'")).scalar()
    if in_use:
        raise RuntimeError("Cannot downgrade: learning programs still use program_type 'challenge'.")
    with op.batch_alter_table("learning_programs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_learning_programs_type", type_="check")
        batch_op.create_check_constraint("ck_learning_programs_type", _check(_PREVIOUS))
