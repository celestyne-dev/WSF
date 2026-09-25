"""mentorship cms: programs, applications, matches, sessions

Revision ID: a3b7e9c2f5d1
Revises: f1a4c7d2e8b3
Create Date: 2026-09-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a3b7e9c2f5d1'
down_revision = 'f1a4c7d2e8b3'
branch_labels = None
depends_on = None

PROGRAM_STATUSES = ("draft", "applications_open", "applications_closed", "matching", "active", "completed", "archived")
APPLICATION_ROLES = ("mentor", "mentee")
APPLICATION_STATUSES = ("submitted", "reviewing", "shortlisted", "approved", "waitlisted", "declined", "withdrawn", "archived")
MEETING_FREQUENCIES = ("Weekly", "Every two weeks", "Monthly", "Flexible")
MENTORSHIP_FORMATS = ("Virtual", "In person", "Hybrid", "Flexible")
MATCH_STATUSES = ("proposed", "confirmed", "active", "paused", "completed", "cancelled", "rematch_needed", "archived")
SESSION_STATUSES = ("scheduled", "completed", "missed", "cancelled")


def upgrade():
    op.create_table(
        'mentorship_programs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=160), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('short_description', sa.Text(), nullable=True),
        sa.Column('full_description', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='draft'),
        sa.Column('public_visible', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('application_opens_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('application_closes_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('program_starts_at', sa.Date(), nullable=True),
        sa.Column('program_ends_at', sa.Date(), nullable=True),
        sa.Column('mentor_capacity', sa.Integer(), nullable=True),
        sa.Column('mentee_capacity', sa.Integer(), nullable=True),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('eligibility_summary', sa.Text(), nullable=True),
        sa.Column('hero_media_id', sa.Integer(), nullable=True),
        sa.Column('seo', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.ForeignKeyConstraint(['hero_media_id'], ['media.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in PROGRAM_STATUSES) + ")", name='ck_mentorship_programs_status'
        ),
    )
    op.create_index('ix_mentorship_programs_slug', 'mentorship_programs', ['slug'], unique=True)

    op.create_table(
        'mentorship_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('professional_title', sa.String(length=200), nullable=True),
        sa.Column('organization_name', sa.String(length=200), nullable=True),
        sa.Column('industry', sa.String(length=140), nullable=True),
        sa.Column('years_experience', sa.Integer(), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('background_text', sa.Text(), nullable=True),
        sa.Column('goals_text', sa.Text(), nullable=True),
        sa.Column('support_offered_text', sa.Text(), nullable=True),
        sa.Column('career_stage', sa.String(length=30), nullable=True),
        sa.Column('career_stages_supported', sa.JSON(), nullable=True),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=True),
        sa.Column('meeting_frequency', sa.String(length=30), nullable=True),
        sa.Column('mentorship_format', sa.String(length=20), nullable=True),
        sa.Column('availability_note', sa.Text(), nullable=True),
        sa.Column('mentor_capacity', sa.Integer(), nullable=True),
        sa.Column('mentor_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='submitted'),
        sa.Column('consent_given', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('newsletter_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('member_id', sa.Integer(), nullable=True),
        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('acquisition', sa.JSON(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['mentorship_programs.id']),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.ForeignKeyConstraint(['member_id'], ['members.id']),
        sa.ForeignKeyConstraint(['person_id'], ['people.id']),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in APPLICATION_ROLES) + ")", name='ck_mentorship_applications_role'
        ),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in APPLICATION_STATUSES) + ")",
            name='ck_mentorship_applications_status',
        ),
        sa.CheckConstraint(
            "meeting_frequency IS NULL OR meeting_frequency IN ("
            + ", ".join(f"'{f}'" for f in MEETING_FREQUENCIES) + ")",
            name='ck_mentorship_applications_meeting_frequency',
        ),
        sa.CheckConstraint(
            "mentorship_format IS NULL OR mentorship_format IN (" + ", ".join(f"'{f}'" for f in MENTORSHIP_FORMATS) + ")",
            name='ck_mentorship_applications_format',
        ),
    )
    op.create_index('ix_mentorship_applications_email', 'mentorship_applications', ['email'])

    op.create_table(
        'mentorship_application_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['mentorship_applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'mentorship_program_topics',
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['mentorship_programs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('program_id', 'topic_id'),
    )

    op.create_table(
        'mentorship_application_topics',
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['mentorship_applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('application_id', 'topic_id'),
    )

    op.create_table(
        'mentorship_matches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('mentor_application_id', sa.Integer(), nullable=False),
        sa.Column('mentee_application_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='proposed'),
        sa.Column('matched_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('planned_start_date', sa.Date(), nullable=True),
        sa.Column('planned_end_date', sa.Date(), nullable=True),
        sa.Column('actual_completion_date', sa.Date(), nullable=True),
        sa.Column('matching_notes', sa.Text(), nullable=True),
        sa.Column('closure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['mentorship_programs.id']),
        sa.ForeignKeyConstraint(['mentor_application_id'], ['mentorship_applications.id']),
        sa.ForeignKeyConstraint(['mentee_application_id'], ['mentorship_applications.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in MATCH_STATUSES) + ")", name='ck_mentorship_matches_status'
        ),
        sa.CheckConstraint(
            'planned_end_date IS NULL OR planned_start_date IS NULL OR planned_end_date >= planned_start_date',
            name='ck_mentorship_matches_dates',
        ),
    )

    op.create_table(
        'mentorship_match_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['mentorship_matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'mentorship_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=False),
        sa.Column('session_date', sa.Date(), nullable=False),
        sa.Column('session_number', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='scheduled'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('next_step_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['mentorship_matches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in SESSION_STATUSES) + ")", name='ck_mentorship_sessions_status'
        ),
    )


def downgrade():
    op.drop_table('mentorship_sessions')
    op.drop_table('mentorship_match_notes')
    op.drop_table('mentorship_matches')
    op.drop_table('mentorship_application_topics')
    op.drop_table('mentorship_program_topics')
    op.drop_table('mentorship_application_notes')
    op.drop_index('ix_mentorship_applications_email', table_name='mentorship_applications')
    op.drop_table('mentorship_applications')
    op.drop_index('ix_mentorship_programs_slug', table_name='mentorship_programs')
    op.drop_table('mentorship_programs')
