"""WSF Career Hub: allow the new Resource formats on resources.type.

Constraint-only. resources.type is guarded by ck_resources_type; this
widens it with Playbook, Scripts, Challenge, Assessment, Research and
Other. Existing rows and values are untouched. Downgrade restores the
previous set and refuses while any row uses one of the new values.

Revision ID: d1a4e7b2c9f3
Revises: c5e2a9d4f1b8
"""
from alembic import op
import sqlalchemy as sa

revision = "d1a4e7b2c9f3"
down_revision = "c5e2a9d4f1b8"
branch_labels = None
depends_on = None

# Frozen copies — never import live model constants into a migration.
_PREVIOUS = (
    "Guide", "Workbook", "Template", "Checklist", "Planner", "Toolkit", "Ebook", "Worksheet", "Report",
    "Download", "Video Resource", "External Resource",
)
_NEW = ("Playbook", "Scripts", "Challenge", "Assessment", "Research", "Other")


def _check(values):
    return "type IS NULL OR type IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade():
    with op.batch_alter_table("resources", schema=None) as batch_op:
        batch_op.drop_constraint("ck_resources_type", type_="check")
        batch_op.create_check_constraint("ck_resources_type", _check(_PREVIOUS + _NEW))


def downgrade():
    in_use = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM resources WHERE type IN (" + ", ".join(f"'{v}'" for v in _NEW) + ")")
    ).scalar()
    if in_use:
        raise RuntimeError("Cannot downgrade: resources still use the Career Hub formats added by d1a4e7b2c9f3.")
    with op.batch_alter_table("resources", schema=None) as batch_op:
        batch_op.drop_constraint("ck_resources_type", type_="check")
        batch_op.create_check_constraint("ck_resources_type", _check(_PREVIOUS))
