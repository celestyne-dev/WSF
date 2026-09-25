"""homepage builder upgrade: controlled module types, CTA/media columns

Extends the existing `homepage_modules` table (Phase 4) rather than
creating a new one — see app/models/cms.py's HomepageModule docstring.
Adds a CHECK constraint restricting `type` to the controlled module
registry, plus dedicated media/CTA columns so Hero and the new CTA-style
modules (community_cta, mentorship_cta, editorial_callout) don't have to
bury a hero image or button behind an untyped JSON key. Widens
`subheading` from String(400) to Text so editorial_callout/CTA
descriptions aren't cramped. Purely additive/widening — no data loss for
existing rows (new columns are nullable; the type CHECK only takes effect
going forward and matches every type already seeded).

Revision ID: a3c8e1f5b7d2
Revises: e7f2a4c9d1b6
Create Date: 2026-09-25 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a3c8e1f5b7d2'
down_revision = 'e7f2a4c9d1b6'
branch_labels = None
depends_on = None

HOMEPAGE_MODULE_TYPES = (
    "hero",
    "featured_stories",
    "latest_stories",
    "featured_woman",
    "series_feature",
    "topic_collection",
    "opportunities",
    "jobs",
    "events",
    "resources",
    "newsletter",
    "partners",
    "community_cta",
    "mentorship_cta",
    "editorial_callout",
    "sponsor_placement",
)
_TYPE_CHECK = "type IN (" + ", ".join(f"'{t}'" for t in HOMEPAGE_MODULE_TYPES) + ")"


def upgrade():
    with op.batch_alter_table('homepage_modules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('media_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cta_label', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('cta_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('secondary_cta_label', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('secondary_cta_url', sa.String(length=500), nullable=True))
        batch_op.alter_column('subheading', existing_type=sa.String(length=400), type_=sa.Text(), nullable=True)
        batch_op.create_foreign_key(
            'fk_homepage_modules_media_id_media', 'media', ['media_id'], ['id']
        )
        batch_op.create_check_constraint('ck_homepage_modules_type', _TYPE_CHECK)


def downgrade():
    with op.batch_alter_table('homepage_modules', schema=None) as batch_op:
        batch_op.drop_constraint('ck_homepage_modules_type', type_='check')
        batch_op.drop_constraint('fk_homepage_modules_media_id_media', type_='foreignkey')
        batch_op.alter_column('subheading', existing_type=sa.Text(), type_=sa.String(length=400), nullable=True)
        batch_op.drop_column('secondary_cta_url')
        batch_op.drop_column('secondary_cta_label')
        batch_op.drop_column('cta_url')
        batch_op.drop_column('cta_label')
        batch_op.drop_column('media_id')
