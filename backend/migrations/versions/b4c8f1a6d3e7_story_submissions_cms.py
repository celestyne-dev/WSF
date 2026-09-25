"""story submissions cms: rebuild story_submissions, notes, media, article handoff

Revision ID: b4c8f1a6d3e7
Revises: a3b7e9c2f5d1
Create Date: 2026-09-25 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b4c8f1a6d3e7'
down_revision = 'a3b7e9c2f5d1'
branch_labels = None
depends_on = None

SUBMISSION_STATUSES = (
    "submitted", "reviewing", "needs_information", "shortlisted", "approved",
    "converted", "published", "declined", "withdrawn", "archived",
)
STORY_TYPES = (
    "personal_story", "career_journey", "leadership_story", "founder_story",
    "business_story", "community_impact", "starting_again", "overcoming_barriers",
    "women_doing_incredible_things", "women_leading_organizations", "workplace_story",
    "opportunity_achievement", "other",
)
CONTENT_ORIGINS = ("first_person", "on_behalf_of", "previously_published", "adapted")
AI_INVOLVEMENT_VALUES = ("none", "ai_assisted", "ai_generated_reviewed")
VERIFICATION_STATUSES = ("unverified", "verification_needed", "verified")
SUBJECT_PERMISSION_STATUSES = ("not_applicable", "unknown", "needs_confirmation", "confirmed")


def upgrade():
    # The pre-existing story_submissions table was a minimal lead-capture
    # shape (name/email/title/excerpt/body/status) with no consent,
    # provenance, classification, or review fields, and no real production
    # data — replaced outright rather than column-by-column altered.
    op.drop_table('story_submissions')

    op.create_table(
        'story_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(length=30), nullable=True),

        sa.Column('first_name', sa.String(length=120), nullable=False),
        sa.Column('last_name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('city', sa.String(length=120), nullable=True),
        sa.Column('professional_title', sa.String(length=200), nullable=True),
        sa.Column('organization_name', sa.String(length=200), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),

        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('why_it_matters', sa.Text(), nullable=True),
        sa.Column('key_lessons', sa.Text(), nullable=True),
        sa.Column('story_type', sa.String(length=40), nullable=True),

        sa.Column('subject_is_submitter', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('subject_name', sa.String(length=200), nullable=True),
        sa.Column('subject_relationship', sa.String(length=200), nullable=True),
        sa.Column('subject_permission_status', sa.String(length=20), nullable=False, server_default='not_applicable'),

        sa.Column('content_origin', sa.String(length=20), nullable=True),
        sa.Column('previous_publication_url', sa.String(length=500), nullable=True),
        sa.Column('ai_involvement', sa.String(length=30), nullable=False, server_default='none'),
        sa.Column('ai_provenance_note', sa.Text(), nullable=True),

        sa.Column('consent_review_given', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_contact_given', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_accuracy_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_media_rights_confirmed', sa.Boolean(), nullable=True),
        sa.Column('consent_recorded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('newsletter_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()),

        sa.Column('series_id', sa.Integer(), nullable=True),
        sa.Column('recommended_format', sa.String(length=120), nullable=True),
        sa.Column('verification_status', sa.String(length=20), nullable=False, server_default='unverified'),
        sa.Column('permission_followup_required', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('media_followup_required', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('information_requested_note', sa.Text(), nullable=True),

        sa.Column('status', sa.String(length=20), nullable=False, server_default='submitted'),
        sa.Column('editorial_assessment', sa.Text(), nullable=True),
        sa.Column('assigned_editor_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),

        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),

        sa.Column('acquisition', sa.JSON(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.ForeignKeyConstraint(['series_id'], ['series.id']),
        sa.ForeignKeyConstraint(['assigned_editor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['person_id'], ['people.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in SUBMISSION_STATUSES) + ")",
            name='ck_story_submissions_status',
        ),
        sa.CheckConstraint(
            "story_type IS NULL OR story_type IN (" + ", ".join(f"'{t}'" for t in STORY_TYPES) + ")",
            name='ck_story_submissions_story_type',
        ),
        sa.CheckConstraint(
            "content_origin IS NULL OR content_origin IN (" + ", ".join(f"'{o}'" for o in CONTENT_ORIGINS) + ")",
            name='ck_story_submissions_content_origin',
        ),
        sa.CheckConstraint(
            "ai_involvement IN (" + ", ".join(f"'{v}'" for v in AI_INVOLVEMENT_VALUES) + ")",
            name='ck_story_submissions_ai_involvement',
        ),
        sa.CheckConstraint(
            "verification_status IN (" + ", ".join(f"'{v}'" for v in VERIFICATION_STATUSES) + ")",
            name='ck_story_submissions_verification_status',
        ),
        sa.CheckConstraint(
            "subject_permission_status IN (" + ", ".join(f"'{s}'" for s in SUBJECT_PERMISSION_STATUSES) + ")",
            name='ck_story_submissions_subject_permission',
        ),
    )
    op.create_index('ix_story_submissions_reference', 'story_submissions', ['reference'], unique=True)
    op.create_index('ix_story_submissions_email', 'story_submissions', ['email'])

    op.create_table(
        'submission_topics',
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['story_submissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('submission_id', 'topic_id'),
    )

    op.create_table(
        'submission_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['story_submissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'submission_media',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('media_id', sa.Integer(), nullable=False),
        sa.Column('caption', sa.String(length=500), nullable=True),
        sa.Column('credit', sa.String(length=255), nullable=True),
        sa.Column('rights_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['story_submissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['media_id'], ['media.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('articles', sa.Column('source_submission_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_articles_source_submission_id', 'articles', 'story_submissions', ['source_submission_id'], ['id']
    )


def downgrade():
    op.drop_constraint('fk_articles_source_submission_id', 'articles', type_='foreignkey')
    op.drop_column('articles', 'source_submission_id')

    op.drop_table('submission_media')
    op.drop_table('submission_notes')
    op.drop_table('submission_topics')
    op.drop_index('ix_story_submissions_email', table_name='story_submissions')
    op.drop_index('ix_story_submissions_reference', table_name='story_submissions')
    op.drop_table('story_submissions')

    op.create_table(
        'story_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('excerpt', sa.Text(), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='new'),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('acquisition', sa.JSON(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
