"""Homepage Builder: allow career_pathways and content_collection modules.

Constraint-only migration. homepage_modules.type is guarded by the
ck_homepage_modules_type CHECK constraint (created from a frozen type list
in a3c8e1f5b7d2), so two new module types cannot be stored without
widening it. No columns, no data changes: both new types keep their
settings in the existing JSON `config`, `selection_mode` and CTA columns.

Downgrade restores the original 16-type constraint; it refuses to run
while any row still uses one of the new types (delete or retype those
modules first) rather than silently dropping editor content.

Revision ID: c5e2a9d4f1b8
Revises: a8d3f1c7e2b5
"""
from alembic import op
import sqlalchemy as sa

revision = "c5e2a9d4f1b8"
down_revision = "a8d3f1c7e2b5"
branch_labels = None
depends_on = None

# Frozen copies — never import the live model tuple into a migration.
_PREVIOUS_TYPES = (
    "hero", "featured_stories", "latest_stories", "featured_woman", "series_feature", "topic_collection",
    "opportunities", "jobs", "events", "resources", "newsletter", "partners", "community_cta",
    "mentorship_cta", "editorial_callout", "sponsor_placement",
)
_NEW_TYPES = ("career_pathways", "content_collection")


def _check(types):
    return "type IN (" + ", ".join(f"'{t}'" for t in types) + ")"


def upgrade():
    with op.batch_alter_table("homepage_modules", schema=None) as batch_op:
        batch_op.drop_constraint("ck_homepage_modules_type", type_="check")
        batch_op.create_check_constraint("ck_homepage_modules_type", _check(_PREVIOUS_TYPES + _NEW_TYPES))


def downgrade():
    bind = op.get_bind()
    in_use = bind.execute(
        sa.text("SELECT COUNT(*) FROM homepage_modules WHERE type IN ('career_pathways', 'content_collection')")
    ).scalar()
    if in_use:
        raise RuntimeError(
            "Cannot downgrade: homepage_modules still contains career_pathways/content_collection rows."
        )
    with op.batch_alter_table("homepage_modules", schema=None) as batch_op:
        batch_op.drop_constraint("ck_homepage_modules_type", type_="check")
        batch_op.create_check_constraint("ck_homepage_modules_type", _check(_PREVIOUS_TYPES))
