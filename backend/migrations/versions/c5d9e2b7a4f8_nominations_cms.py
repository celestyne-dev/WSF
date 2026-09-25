"""nominations cms: rebuild nominations, notes, article handoff

Revision ID: c5d9e2b7a4f8
Revises: b4c8f1a6d3e7
Create Date: 2026-09-25 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c5d9e2b7a4f8'
down_revision = 'b4c8f1a6d3e7'
branch_labels = None
depends_on = None

NOMINATION_STATUSES = (
    "submitted", "reviewing", "verification_needed", "shortlisted", "approved",
    "in_editorial", "published", "declined", "withdrawn", "archived",
)
NOMINEE_AWARENESS_VALUES = ("aware", "not_aware", "unknown")
VERIFICATION_STATES = ("not_started", "in_progress", "complete")


def upgrade():
    # The pre-existing nominations table was a minimal lead-capture shape
    # (nominee_name/profession/organization/achievements/nominator_name/
    # nominator_email/category/status) with no consent, provenance,
    # classification, verification, or review fields, and no real
    # production data — replaced outright rather than column-by-column
    # altered.
    op.drop_table('nominations')

    op.create_table(
        'nominations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(length=30), nullable=True),

        sa.Column('nominee_name', sa.String(length=200), nullable=False),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('city', sa.String(length=120), nullable=True),
        sa.Column('professional_title', sa.String(length=200), nullable=True),
        sa.Column('organization_name', sa.String(length=200), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('short_bio', sa.Text(), nullable=True),
        sa.Column('nominee_email', sa.String(length=255), nullable=True),

        sa.Column('nomination_summary', sa.String(length=300), nullable=True),
        sa.Column('achievements', sa.Text(), nullable=False),
        sa.Column('why_significant', sa.Text(), nullable=True),
        sa.Column('who_impacted', sa.Text(), nullable=True),
        sa.Column('supporting_links', sa.JSON(), nullable=True),
        sa.Column('series_id', sa.Integer(), nullable=True),

        sa.Column('is_self_nomination', sa.Boolean(), nullable=False, server_default=sa.false()),

        sa.Column('nominator_name', sa.String(length=200), nullable=False),
        sa.Column('nominator_email', sa.String(length=255), nullable=False),
        sa.Column('nominator_organization', sa.String(length=200), nullable=True),
        sa.Column('relationship_to_nominee', sa.String(length=200), nullable=True),
        sa.Column('nominee_awareness', sa.String(length=20), nullable=False, server_default='unknown'),

        sa.Column('consent_accuracy_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_review_given', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_contact_given', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_recorded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('newsletter_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()),

        sa.Column('possible_duplicate', sa.Boolean(), nullable=False, server_default=sa.false()),

        sa.Column('status', sa.String(length=20), nullable=False, server_default='submitted'),
        sa.Column('editorial_assessment', sa.Text(), nullable=True),
        sa.Column('assigned_reviewer_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),

        sa.Column('verification_state', sa.String(length=20), nullable=False, server_default='not_started'),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('contact_nominee_before_publication', sa.Boolean(), nullable=False, server_default=sa.false()),

        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('person_profile_needed', sa.Boolean(), nullable=False, server_default=sa.false()),

        sa.Column('acquisition', sa.JSON(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.ForeignKeyConstraint(['series_id'], ['series.id']),
        sa.ForeignKeyConstraint(['assigned_reviewer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['person_id'], ['people.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in NOMINATION_STATUSES) + ")",
            name='ck_nominations_status',
        ),
        sa.CheckConstraint(
            "nominee_awareness IN (" + ", ".join(f"'{v}'" for v in NOMINEE_AWARENESS_VALUES) + ")",
            name='ck_nominations_nominee_awareness',
        ),
        sa.CheckConstraint(
            "verification_state IN (" + ", ".join(f"'{v}'" for v in VERIFICATION_STATES) + ")",
            name='ck_nominations_verification_state',
        ),
    )
    op.create_index('ix_nominations_reference', 'nominations', ['reference'], unique=True)

    op.create_table(
        'nomination_topics',
        sa.Column('nomination_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['nomination_id'], ['nominations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('nomination_id', 'topic_id'),
    )

    op.create_table(
        'nomination_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nomination_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['nomination_id'], ['nominations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('articles', sa.Column('source_nomination_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_articles_source_nomination_id', 'articles', 'nominations', ['source_nomination_id'], ['id']
    )


def downgrade():
    op.drop_constraint('fk_articles_source_nomination_id', 'articles', type_='foreignkey')
    op.drop_column('articles', 'source_nomination_id')

    op.drop_table('nomination_notes')
    op.drop_table('nomination_topics')
    op.drop_index('ix_nominations_reference', table_name='nominations')
    op.drop_table('nominations')

    op.create_table(
        'nominations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nominee_name', sa.String(length=200), nullable=False),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('profession', sa.String(length=200), nullable=True),
        sa.Column('organization', sa.String(length=200), nullable=True),
        sa.Column('achievements', sa.Text(), nullable=True),
        sa.Column('nominator_name', sa.String(length=200), nullable=False),
        sa.Column('nominator_email', sa.String(length=255), nullable=False),
        sa.Column('relationship_to_nominee', sa.String(length=200), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='new'),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('acquisition', sa.JSON(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
