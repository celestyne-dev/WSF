"""resource circle_only access type

Revision ID: 5f90a23d2e1a
Revises: 8997e4aeceae
Create Date: 2026-10-04 13:58:51.742191

Note: autogenerate against this schema always proposes the same spurious
circular fk_media_uploaded_by_id FK plus unrelated index/constraint churn
across articles, events, jobs, newsletter_subscribers, opportunities,
pages, partnership_notes, people, resource_leads, resources, and
sponsor_placements (same known drift documented in every migration since
950a29bb1ce9). Alembic's autogenerate also does not detect CHECK
constraint body changes at all here, so this migration's one real
operation (widening ck_resources_access_type to allow "circle_only") was
written by hand rather than generated — nothing in this file was
produced by `flask db migrate` as-is.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '5f90a23d2e1a'
down_revision = '8997e4aeceae'
branch_labels = None
depends_on = None

_OLD_ACCESS_TYPES = ("direct_download", "email_gate", "member_only", "premium", "external_link")
_NEW_ACCESS_TYPES = ("direct_download", "email_gate", "member_only", "circle_only", "premium", "external_link")


def upgrade():
    op.drop_constraint("ck_resources_access_type", "resources", type_="check")
    op.create_check_constraint(
        "ck_resources_access_type",
        "resources",
        "access_type IN (" + ", ".join(f"'{a}'" for a in _NEW_ACCESS_TYPES) + ")",
    )


def downgrade():
    op.drop_constraint("ck_resources_access_type", "resources", type_="check")
    op.create_check_constraint(
        "ck_resources_access_type",
        "resources",
        "access_type IN (" + ", ".join(f"'{a}'" for a in _OLD_ACCESS_TYPES) + ")",
    )
