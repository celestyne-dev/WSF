"""Schema drift fixes (Batch 4 corrections, Fix 7).

1. media.uploaded_by_id -> users.id: declared by the model and by
   a04424f9686f (with use_alter inside create_table, which Alembic never
   emitted), so the constraint is missing from migrated databases. Added
   here if absent, after clearing references to accounts that no longer
   exist (they could not satisfy the constraint).
2. newsletter_subscribers.unsubscribe_token: b2c8e1f4a6d7 created a unique
   constraint (uq_...) AND a separate non-unique index (ix_...) on the same
   column. The constraint's own index already serves lookups; the redundant
   ix_ index is dropped (if present). Nothing is added twice.

Revision ID: f7c3a9e5b1d6
Revises: e6b2f8d4a0c5
"""
from alembic import op
import sqlalchemy as sa

revision = "f7c3a9e5b1d6"
down_revision = "e6b2f8d4a0c5"
branch_labels = None
depends_on = None

FK = "fk_media_uploaded_by_id"
IX = "ix_newsletter_subscribers_unsubscribe_token"
UQ = "uq_newsletter_subscribers_unsubscribe_token"


def _fk_exists(bind):
    return any(fk.get("name") == FK for fk in sa.inspect(bind).get_foreign_keys("media"))


def upgrade():
    bind = op.get_bind()
    if not _fk_exists(bind):
        op.execute("UPDATE media SET uploaded_by_id = NULL WHERE uploaded_by_id IS NOT NULL "
                   "AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = media.uploaded_by_id)")
        op.create_foreign_key(FK, "media", "users", ["uploaded_by_id"], ["id"])
    inspector = sa.inspect(bind)
    unique_names = {c["name"] for c in inspector.get_unique_constraints("newsletter_subscribers")}
    indexes = {i["name"]: i for i in inspector.get_indexes("newsletter_subscribers")}
    if UQ not in unique_names:
        # A database built from the models (unique ix_ index, no constraint):
        # replace the unique index with the named constraint the model declares.
        if IX in indexes:
            op.drop_index(IX, table_name="newsletter_subscribers")
        op.create_unique_constraint(UQ, "newsletter_subscribers", ["unsubscribe_token"])
    elif IX in indexes and not indexes[IX].get("unique"):
        op.drop_index(IX, table_name="newsletter_subscribers")


def downgrade():
    bind = op.get_bind()
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("newsletter_subscribers")}
    if IX not in indexes:
        op.create_index(IX, "newsletter_subscribers", ["unsubscribe_token"])
    if _fk_exists(bind):
        op.drop_constraint(FK, "media", type_="foreignkey")
