"""advertise / media kit cms: page content, audience metrics, offerings,
advertising partnership-type value

Revision ID: e7f3b2a9c1d4
Revises: d5e8a1c3f9b2
Create Date: 2026-09-24 15:00:00.000000

"""
from datetime import date

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e7f3b2a9c1d4'
down_revision = 'd5e8a1c3f9b2'
branch_labels = None
depends_on = None

PARTNERSHIP_TYPES = (
    "Brand Partnership", "Content Partnership", "Employer Partnership", "Event Partnership",
    "Community Partnership", "Education Partnership", "Resource Partnership", "Recruitment Partnership",
    "Strategic Partnership", "Affiliate Partnership", "Research Partnership", "Advertising", "Other",
)
ADVERTISE_PAGE_STATUSES = ("draft", "published")
ADVERTISE_OFFERING_STATUSES = ("active", "unavailable", "hidden")
ADVERTISE_PRICING_MODES = ("hidden", "contact", "starting_from", "fixed")


def upgrade():
    op.create_table(
        'advertise_page',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hero_heading', sa.String(length=200), nullable=True),
        sa.Column('hero_description', sa.Text(), nullable=True),
        sa.Column('hero_media_id', sa.Integer(), nullable=True),
        sa.Column('intro_content', sa.JSON(), nullable=False),
        sa.Column('audience_overview', sa.Text(), nullable=True),
        sa.Column('why_content', sa.JSON(), nullable=False),
        sa.Column('cta_heading', sa.String(length=200), nullable=True),
        sa.Column('cta_description', sa.Text(), nullable=True),
        sa.Column('cta_button_label', sa.String(length=50), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_note', sa.Text(), nullable=True),
        sa.Column('media_kit_title', sa.String(length=200), nullable=True),
        sa.Column('media_kit_url', sa.String(length=500), nullable=True),
        sa.Column('media_kit_updated_at', sa.Date(), nullable=True),
        sa.Column('faq', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('seo', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['hero_media_id'], ['media.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in ADVERTISE_PAGE_STATUSES) + ")",
            name='ck_advertise_page_status',
        ),
    )

    op.create_table(
        'advertise_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=100), nullable=False),
        sa.Column('unit', sa.String(length=30), nullable=True),
        sa.Column('source_note', sa.Text(), nullable=True),
        sa.Column('as_of_date', sa.Date(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('public_visible', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'advertise_offerings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('short_description', sa.Text(), nullable=True),
        sa.Column('full_description', sa.Text(), nullable=True),
        sa.Column('features', sa.JSON(), nullable=False),
        sa.Column('cta_label', sa.String(length=50), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('featured', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('pricing_mode', sa.String(length=20), nullable=False, server_default='contact'),
        sa.Column('price_amount', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('pricing_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in ADVERTISE_OFFERING_STATUSES) + ")",
            name='ck_advertise_offerings_status',
        ),
        sa.CheckConstraint(
            "pricing_mode IN (" + ", ".join(f"'{p}'" for p in ADVERTISE_PRICING_MODES) + ")",
            name='ck_advertise_offerings_pricing_mode',
        ),
        sa.CheckConstraint(
            'price_amount IS NULL OR price_amount >= 0', name='ck_advertise_offerings_price_nonnegative'
        ),
    )

    # Widen the existing partnership_inquiries type CHECK to also allow
    # "Advertising" — the public Advertise inquiry form reuses
    # PartnershipInquiry rather than a second lead model.
    with op.batch_alter_table('partnership_inquiries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_partnership_inquiries_type', type_='check')
        batch_op.create_check_constraint(
            'ck_partnership_inquiries_type',
            "partnership_type IS NULL OR partnership_type IN (" + ", ".join(f"'{t}'" for t in PARTNERSHIP_TYPES) + ")",
        )

    # Seed one draft page row (id=1) so the public route has something to
    # 404-vs-serve sensibly from the start, and seed a handful of real
    # metrics sourced from the audience_stats SiteSetting this app
    # already maintains for the Partnerships page — not invented figures.
    advertise_page = sa.table(
        'advertise_page',
        sa.column('id', sa.Integer), sa.column('hero_heading', sa.String), sa.column('hero_description', sa.Text),
        sa.column('intro_content', sa.JSON), sa.column('why_content', sa.JSON), sa.column('faq', sa.JSON),
        sa.column('cta_heading', sa.String), sa.column('cta_description', sa.Text),
        sa.column('cta_button_label', sa.String), sa.column('status', sa.String),
    )
    op.bulk_insert(
        advertise_page,
        [
            {
                'id': 1,
                'hero_heading': 'Advertise With Women Shaping Futures',
                'hero_description': (
                    'Reach ambitious, career-driven women across media, leadership, careers, business, '
                    'and community — through a trusted global editorial platform.'
                ),
                'intro_content': [],
                'why_content': [],
                'faq': [],
                'cta_heading': "Let's talk",
                'cta_description': 'Tell us about your goals and our team will follow up.',
                'cta_button_label': 'Get in touch',
                'status': 'draft',
            }
        ],
    )

    advertise_metrics = sa.table(
        'advertise_metrics',
        sa.column('label', sa.String), sa.column('value', sa.String), sa.column('unit', sa.String),
        sa.column('as_of_date', sa.Date), sa.column('display_order', sa.Integer),
        sa.column('public_visible', sa.Boolean),
    )
    today = date.today().isoformat()
    op.bulk_insert(
        advertise_metrics,
        [
            {'label': 'LinkedIn followers', 'value': '132,000+', 'unit': None, 'as_of_date': today, 'display_order': 0, 'public_visible': True},
            {'label': 'Newsletter subscribers', 'value': '34,210+', 'unit': None, 'as_of_date': today, 'display_order': 1, 'public_visible': True},
            {'label': 'Monthly website visitors', 'value': '210,000+', 'unit': None, 'as_of_date': today, 'display_order': 2, 'public_visible': True},
            {'label': 'Countries reached', 'value': '42', 'unit': 'countries', 'as_of_date': today, 'display_order': 3, 'public_visible': True},
        ],
    )


def downgrade():
    with op.batch_alter_table('partnership_inquiries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_partnership_inquiries_type', type_='check')
        batch_op.create_check_constraint(
            'ck_partnership_inquiries_type',
            "partnership_type IS NULL OR partnership_type IN ("
            + ", ".join(f"'{t}'" for t in PARTNERSHIP_TYPES if t != "Advertising")
            + ")",
        )

    op.drop_table('advertise_offerings')
    op.drop_table('advertise_metrics')
    op.drop_table('advertise_page')
