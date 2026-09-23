"""community / membership cms: members, member notes, interests,
community page

Revision ID: f1a4c7d2e8b3
Revises: e7f3b2a9c1d4
Create Date: 2026-09-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f1a4c7d2e8b3'
down_revision = 'e7f3b2a9c1d4'
branch_labels = None
depends_on = None

MEMBERSHIP_STATUSES = ("pending", "active", "paused", "inactive", "declined", "left", "archived")
MEMBERSHIP_TYPES = ("Community Member", "Founding Member", "Premium Member", "Partner Member")
MEMBERSHIP_SOURCES = ("Community page", "LinkedIn", "Newsletter", "Event", "Referral", "Organic", "Other")
COMMUNITY_PAGE_STATUSES = ("draft", "published")


def upgrade():
    op.create_table(
        'members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('professional_title', sa.String(length=200), nullable=True),
        sa.Column('organization_name', sa.String(length=200), nullable=True),
        sa.Column('short_bio', sa.Text(), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('profile_image_media_id', sa.Integer(), nullable=True),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('city', sa.String(length=120), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('membership_type', sa.String(length=30), nullable=False, server_default='Community Member'),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('referral_note', sa.String(length=300), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consent_given', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('newsletter_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('community_updates_opt_in', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('directory_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('admin_tags', sa.JSON(), nullable=True),
        sa.Column('acquisition', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.ForeignKeyConstraint(['person_id'], ['people.id']),
        sa.ForeignKeyConstraint(['profile_image_media_id'], ['media.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in MEMBERSHIP_STATUSES) + ")", name='ck_members_status'
        ),
        sa.CheckConstraint(
            "membership_type IN (" + ", ".join(f"'{t}'" for t in MEMBERSHIP_TYPES) + ")", name='ck_members_type'
        ),
        sa.CheckConstraint(
            "source IS NULL OR source IN (" + ", ".join(f"'{s}'" for s in MEMBERSHIP_SOURCES) + ")",
            name='ck_members_source',
        ),
    )
    op.create_index('ix_members_email', 'members', ['email'], unique=True)

    op.create_table(
        'member_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'member_topics',
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('member_id', 'topic_id'),
    )

    op.create_table(
        'community_page',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hero_heading', sa.String(length=200), nullable=True),
        sa.Column('hero_description', sa.Text(), nullable=True),
        sa.Column('hero_media_id', sa.Integer(), nullable=True),
        sa.Column('intro_content', sa.JSON(), nullable=False),
        sa.Column('benefits', sa.JSON(), nullable=False),
        sa.Column('who_for_text', sa.Text(), nullable=True),
        sa.Column('how_to_join_text', sa.Text(), nullable=True),
        sa.Column('cta_heading', sa.String(length=200), nullable=True),
        sa.Column('cta_description', sa.Text(), nullable=True),
        sa.Column('cta_button_label', sa.String(length=50), nullable=True),
        sa.Column('faq', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('seo', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['hero_media_id'], ['media.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in COMMUNITY_PAGE_STATUSES) + ")",
            name='ck_community_page_status',
        ),
    )

    community_page = sa.table(
        'community_page',
        sa.column('id', sa.Integer), sa.column('hero_heading', sa.String), sa.column('hero_description', sa.Text),
        sa.column('intro_content', sa.JSON), sa.column('benefits', sa.JSON), sa.column('who_for_text', sa.Text),
        sa.column('how_to_join_text', sa.Text), sa.column('cta_heading', sa.String),
        sa.column('cta_description', sa.Text), sa.column('cta_button_label', sa.String),
        sa.column('faq', sa.JSON), sa.column('status', sa.String),
    )
    op.bulk_insert(
        community_page,
        [
            {
                'id': 1,
                'hero_heading': 'The WSF Community',
                'hero_description': (
                    'A global home for ambitious, career-driven women — connect with members across industries, '
                    'career stages, and countries.'
                ),
                'intro_content': [],
                'benefits': [
                    {'title': 'Opportunities', 'description': 'Surface jobs, opportunities, and events curated for our community.'},
                    {'title': 'Insights', 'description': 'Leadership and business insights from across the WSF platform.'},
                    {'title': 'Connection', 'description': 'A global network of women shaping their industries and futures.'},
                ],
                'who_for_text': 'Women at any career stage — early career to executive leadership — across every industry and country.',
                'how_to_join_text': "Fill out the form below. It's free, takes two minutes, and membership is open to all.",
                'cta_heading': 'Join the community',
                'cta_description': 'Tell us a bit about yourself and we will be in touch.',
                'cta_button_label': 'Join WSF',
                'faq': [],
                'status': 'draft',
            }
        ],
    )


def downgrade():
    op.drop_table('community_page')
    op.drop_table('member_topics')
    op.drop_table('member_notes')
    op.drop_index('ix_members_email', table_name='members')
    op.drop_table('members')
