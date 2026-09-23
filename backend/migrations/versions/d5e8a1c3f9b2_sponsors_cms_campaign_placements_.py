"""sponsors cms: campaign fields, controlled type/status, disclosure,
placements, commercial metadata, article sponsor linkage

Revision ID: d5e8a1c3f9b2
Revises: c4d9f2a8e1b6
Create Date: 2026-09-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd5e8a1c3f9b2'
down_revision = 'c4d9f2a8e1b6'
branch_labels = None
depends_on = None

SPONSORSHIP_TYPES = (
    "Brand Sponsor", "Newsletter Sponsor", "Event Sponsor", "Content Sponsor", "Series Sponsor",
    "Resource Sponsor", "Employer Sponsor", "Community Sponsor", "Supporting Partner",
    "Presenting Sponsor", "Other",
)
SPONSOR_STATUSES = ("draft", "scheduled", "active", "paused", "completed", "archived")
SPONSOR_DISCLOSURE_LABELS = ("Sponsored", "Sponsored by", "Presented by", "In partnership with")
SPONSOR_PLACEMENT_KEYS = ("homepage_featured", "homepage_footer", "article_sidebar", "article_inline")


def upgrade():
    with op.batch_alter_table('sponsors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('campaign_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('partnership_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('internal_reference', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('public_name_override', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('public_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('sponsorship_type', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('logo_media_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('creative_media_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sponsor_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('cta_label', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('disclosure_label', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('public_visible', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('is_exclusive', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('exclusivity_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('estimated_value', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('currency', sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column('commercial_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('internal_notes', sa.Text(), nullable=True))

    # Backfill existing rows conservatively — never auto-publish a
    # pre-existing record just because it used to have active=True.
    op.execute("UPDATE sponsors SET campaign_name = COALESCE(campaign_name, 'Sponsorship')")
    op.execute("UPDATE sponsors SET disclosure_label = COALESCE(disclosure_label, 'Sponsored by')")
    op.execute("UPDATE sponsors SET status = 'active' WHERE status IS NULL AND active = TRUE")
    op.execute("UPDATE sponsors SET status = 'draft' WHERE status IS NULL")
    op.execute("UPDATE sponsors SET public_visible = FALSE WHERE public_visible IS NULL")
    op.execute("UPDATE sponsors SET is_exclusive = FALSE WHERE is_exclusive IS NULL")

    with op.batch_alter_table('sponsors', schema=None) as batch_op:
        batch_op.alter_column('campaign_name', existing_type=sa.String(length=200), nullable=False)
        batch_op.alter_column('disclosure_label', existing_type=sa.String(length=30), nullable=False)
        batch_op.alter_column('status', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('public_visible', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('is_exclusive', existing_type=sa.Boolean(), nullable=False)
        batch_op.drop_column('active')
        batch_op.create_foreign_key('fk_sponsors_partnership_id', 'partnership_inquiries', ['partnership_id'], ['id'])
        batch_op.create_foreign_key('fk_sponsors_logo_media_id', 'media', ['logo_media_id'], ['id'])
        batch_op.create_foreign_key('fk_sponsors_creative_media_id', 'media', ['creative_media_id'], ['id'])
        batch_op.create_check_constraint(
            'ck_sponsors_type',
            "sponsorship_type IS NULL OR sponsorship_type IN (" + ", ".join(f"'{t}'" for t in SPONSORSHIP_TYPES) + ")",
        )
        batch_op.create_check_constraint(
            'ck_sponsors_status', "status IN (" + ", ".join(f"'{s}'" for s in SPONSOR_STATUSES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_sponsors_disclosure_label',
            "disclosure_label IN (" + ", ".join(f"'{d}'" for d in SPONSOR_DISCLOSURE_LABELS) + ")",
        )
        batch_op.create_check_constraint(
            'ck_sponsors_value_nonnegative', 'estimated_value IS NULL OR estimated_value >= 0'
        )
        batch_op.create_check_constraint(
            'ck_sponsors_dates', 'ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at'
        )

    op.create_table(
        'sponsor_placements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sponsor_id', sa.Integer(), nullable=False),
        sa.Column('placement_key', sa.String(length=30), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('starts_at', sa.Date(), nullable=True),
        sa.Column('ends_at', sa.Date(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['sponsor_id'], ['sponsors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "placement_key IN (" + ", ".join(f"'{p}'" for p in SPONSOR_PLACEMENT_KEYS) + ")",
            name='ck_sponsor_placements_key',
        ),
        sa.CheckConstraint(
            'ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at', name='ck_sponsor_placements_dates'
        ),
    )
    op.create_index('ix_sponsor_placements_sponsor_id', 'sponsor_placements', ['sponsor_id'])

    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sponsor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_articles_sponsor_id', 'sponsors', ['sponsor_id'], ['id'])


def downgrade():
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_constraint('fk_articles_sponsor_id', type_='foreignkey')
        batch_op.drop_column('sponsor_id')

    op.drop_index('ix_sponsor_placements_sponsor_id', table_name='sponsor_placements')
    op.drop_table('sponsor_placements')

    with op.batch_alter_table('sponsors', schema=None) as batch_op:
        batch_op.drop_constraint('ck_sponsors_dates', type_='check')
        batch_op.drop_constraint('ck_sponsors_value_nonnegative', type_='check')
        batch_op.drop_constraint('ck_sponsors_disclosure_label', type_='check')
        batch_op.drop_constraint('ck_sponsors_status', type_='check')
        batch_op.drop_constraint('ck_sponsors_type', type_='check')
        batch_op.drop_constraint('fk_sponsors_creative_media_id', type_='foreignkey')
        batch_op.drop_constraint('fk_sponsors_logo_media_id', type_='foreignkey')
        batch_op.drop_constraint('fk_sponsors_partnership_id', type_='foreignkey')
        batch_op.add_column(sa.Column('active', sa.Boolean(), nullable=True))

    op.execute("UPDATE sponsors SET active = (status IN ('active', 'scheduled', 'paused'))")

    with op.batch_alter_table('sponsors', schema=None) as batch_op:
        batch_op.alter_column('active', existing_type=sa.Boolean(), nullable=False)
        batch_op.drop_column('internal_notes')
        batch_op.drop_column('commercial_notes')
        batch_op.drop_column('currency')
        batch_op.drop_column('estimated_value')
        batch_op.drop_column('exclusivity_notes')
        batch_op.drop_column('is_exclusive')
        batch_op.drop_column('public_visible')
        batch_op.drop_column('status')
        batch_op.drop_column('disclosure_label')
        batch_op.drop_column('cta_label')
        batch_op.drop_column('sponsor_url')
        batch_op.drop_column('creative_media_id')
        batch_op.drop_column('logo_media_id')
        batch_op.drop_column('sponsorship_type')
        batch_op.drop_column('public_description')
        batch_op.drop_column('public_name_override')
        batch_op.drop_column('internal_reference')
        batch_op.drop_column('partnership_id')
        batch_op.drop_column('campaign_name')
