from app.extensions import db

# draft: being configured, never public. applications_open: publicly listed
# and accepting mentor/mentee applications (subject to the application
# window dates below). applications_closed: still publicly listed but no
# longer accepting new applications. matching: applications closed, staff
# are pairing mentors and mentees. active: matches are running. completed:
# the program ran its course. archived: retired from active admin views,
# record kept for history.
PROGRAM_STATUSES = ("draft", "applications_open", "applications_closed", "matching", "active", "completed", "archived")
_PROGRAM_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in PROGRAM_STATUSES) + ")"

APPLICATION_ROLES = ("mentor", "mentee")
_APPLICATION_ROLE_CHECK_SQL = "role IN (" + ", ".join(f"'{r}'" for r in APPLICATION_ROLES) + ")"

# submitted: just received. reviewing: staff evaluating it. shortlisted:
# a strong candidate under active consideration. approved: eligible to be
# matched (an approved mentor/mentee application IS the mentor/mentee
# profile — see MentorshipApplication's docstring). waitlisted: eligible
# in principle, held back (e.g. program at capacity). declined: not moving
# forward. withdrawn: the applicant pulled out. archived: retired from
# active admin views, record kept for history.
APPLICATION_STATUSES = ("submitted", "reviewing", "shortlisted", "approved", "waitlisted", "declined", "withdrawn", "archived")
_APPLICATION_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in APPLICATION_STATUSES) + ")"

# A controlled career-stage vocabulary reused two ways on the same table:
# a mentee's own `career_stage`, and a mentor's `career_stages_supported`
# (the stages they're comfortable mentoring) — see MentorshipApplication.
CAREER_STAGES = ("Student", "Early Career", "Mid Career", "Senior / Leadership", "Executive", "Career Change")

MEETING_FREQUENCIES = ("Weekly", "Every two weeks", "Monthly", "Flexible")
_MEETING_FREQUENCY_CHECK_SQL = "meeting_frequency IS NULL OR meeting_frequency IN (" + ", ".join(
    f"'{f}'" for f in MEETING_FREQUENCIES
) + ")"

MENTORSHIP_FORMATS = ("Virtual", "In person", "Hybrid", "Flexible")
_MENTORSHIP_FORMAT_CHECK_SQL = "mentorship_format IS NULL OR mentorship_format IN (" + ", ".join(
    f"'{f}'" for f in MENTORSHIP_FORMATS
) + ")"

# proposed: an admin has paired them, not yet confirmed. confirmed: both
# sides/admin have confirmed the pairing. active: the mentorship is
# running. paused: temporarily on hold. completed: ran its course.
# cancelled: ended before completion. rematch_needed: this pairing didn't
# work out and at least one side needs a new match (a NEW MentorshipMatch
# row — this one is kept, never deleted, as history). archived: retired
# from active admin views.
MATCH_STATUSES = ("proposed", "confirmed", "active", "paused", "completed", "cancelled", "rematch_needed", "archived")
_MATCH_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in MATCH_STATUSES) + ")"
# Statuses that count against a mentor's capacity — proposed pairings
# already provisionally occupy a slot, same as confirmed/active/paused
# ones; only a closed-out match (completed/cancelled/rematch_needed/
# archived) frees capacity back up.
MATCH_ACTIVE_STATUSES = ("proposed", "confirmed", "active", "paused")

SESSION_STATUSES = ("scheduled", "completed", "missed", "cancelled")
_SESSION_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in SESSION_STATUSES) + ")"

mentorship_program_topics = db.Table(
    "mentorship_program_topics",
    db.Column("program_id", db.Integer, db.ForeignKey("mentorship_programs.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)

mentorship_application_topics = db.Table(
    "mentorship_application_topics",
    db.Column(
        "application_id", db.Integer, db.ForeignKey("mentorship_applications.id", ondelete="CASCADE"), primary_key=True
    ),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)


class MentorshipProgram(db.Model):
    """A mentorship initiative WSF runs (e.g. "WSF Career Mentorship").
    Dates/capacity/topics live here rather than on a separate Cohort
    model — nothing about the current product needs more than one running
    "batch" of a program open at a time, so a new themed program (or a
    later year's iteration) is simply a new MentorshipProgram row.
    """

    __tablename__ = "mentorship_programs"
    __table_args__ = (db.CheckConstraint(_PROGRAM_STATUS_CHECK_SQL, name="ck_mentorship_programs_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    short_description = db.Column(db.Text)
    # Ordered content-block list — same shape/sanitizer/editor
    # (ArticleBlockEditor + sanitize_content_blocks) as every other
    # editorial content field in this app.
    full_description = db.Column(db.JSON, nullable=False, default=list)

    status = db.Column(db.String(30), nullable=False, default="draft")
    # Independent of status, same principle as Sponsor.public_visible: a
    # program can be fully configured (even Applications Open) without
    # yet being shown on the public /mentorship page.
    public_visible = db.Column(db.Boolean, nullable=False, default=False)

    application_opens_at = db.Column(db.DateTime(timezone=True))
    application_closes_at = db.Column(db.DateTime(timezone=True))
    program_starts_at = db.Column(db.Date)
    program_ends_at = db.Column(db.Date)

    mentor_capacity = db.Column(db.Integer)  # total mentor slots for this program; null = unlimited
    mentee_capacity = db.Column(db.Integer)  # total mentee slots for this program; null = unlimited

    # Geography scope — null means globally open, same GLOBAL/REMOTE
    # pseudo-country convention used elsewhere in this app.
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    eligibility_summary = db.Column(db.Text)

    hero_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    seo = db.Column(db.JSON)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    hero_media = db.relationship("Media", foreign_keys=[hero_media_id])
    topics = db.relationship("Topic", secondary=mentorship_program_topics, backref="mentorship_programs")

    def applications_open_now(self):
        if self.status != "applications_open":
            return False
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if self.application_opens_at and now < self.application_opens_at:
            return False
        if self.application_closes_at and now > self.application_closes_at:
            return False
        return True


class MentorshipApplication(db.Model):
    """A mentor OR mentee application to a MentorshipProgram — one table
    for both roles (see `role`), since the two share most of their
    fields (identity, professional background, geography, topics,
    consent) and a second near-duplicate table would just fork that
    overlap for no benefit — the same reasoning behind PartnershipInquiry
    being one evolving record rather than a separate lead/deal table.

    An APPROVED application IS the mentor/mentee profile — WSF Mentorship
    has no separate MentorProfile/MenteeProfile table. `mentor_capacity`/
    `mentor_active` below only matter once role=mentor and status=approved;
    they're simply unused on every other row. This avoids ever having two
    records to keep in sync for the same person's mentorship participation.
    """

    __tablename__ = "mentorship_applications"
    __table_args__ = (
        db.CheckConstraint(_APPLICATION_ROLE_CHECK_SQL, name="ck_mentorship_applications_role"),
        db.CheckConstraint(_APPLICATION_STATUS_CHECK_SQL, name="ck_mentorship_applications_status"),
        db.CheckConstraint(_MEETING_FREQUENCY_CHECK_SQL, name="ck_mentorship_applications_meeting_frequency"),
        db.CheckConstraint(_MENTORSHIP_FORMAT_CHECK_SQL, name="ck_mentorship_applications_format"),
    )

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("mentorship_programs.id"), nullable=False)
    role = db.Column(db.String(10), nullable=False)

    # Identity
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)  # normalized lower — see api/v1/mentorship.py

    # Professional
    professional_title = db.Column(db.String(200))
    organization_name = db.Column(db.String(200))
    industry = db.Column(db.String(140))
    years_experience = db.Column(db.Integer)  # mentor-relevant; harmless null for a mentee
    linkedin_url = db.Column(db.String(500))
    website_url = db.Column(db.String(500))

    # Expertise / goals — background_text and goals_text each read
    # naturally for either role ("my background" / "why I want to
    # mentor" vs "my background" / "my mentorship goals").
    background_text = db.Column(db.Text)
    goals_text = db.Column(db.Text)
    support_offered_text = db.Column(db.Text)  # mentor-only: what they can help mentees with

    career_stage = db.Column(db.String(30))  # mentee's own stage (controlled CAREER_STAGES)
    career_stages_supported = db.Column(db.JSON)  # mentor-only: list[str] of CAREER_STAGES

    # Matching preferences
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    timezone = db.Column(db.String(50))
    meeting_frequency = db.Column(db.String(30))
    mentorship_format = db.Column(db.String(20))
    availability_note = db.Column(db.Text)

    # Mentor-only operational fields — see class docstring.
    mentor_capacity = db.Column(db.Integer)  # max concurrent active mentees this mentor will take
    mentor_active = db.Column(db.Boolean, nullable=False, default=True)  # accepting new matches right now

    status = db.Column(db.String(20), nullable=False, default="submitted")

    consent_given = db.Column(db.Boolean, nullable=False, default=False)
    consent_at = db.Column(db.DateTime(timezone=True))
    newsletter_opt_in = db.Column(db.Boolean, nullable=False, default=False)

    # Optional admin-only links — never set by the public application
    # itself, never change either linked record's own visibility rules.
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True)

    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    source = db.Column(db.String(50))
    acquisition = db.Column(db.JSON)

    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    program = db.relationship("MentorshipProgram", foreign_keys=[program_id])
    country = db.relationship("Country", foreign_keys=[country_code])
    member = db.relationship("Member", foreign_keys=[member_id])
    person = db.relationship("Person", foreign_keys=[person_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    topics = db.relationship("Topic", secondary=mentorship_application_topics, backref="mentorship_applications")
    notes = db.relationship(
        "MentorshipApplicationNote", order_by="MentorshipApplicationNote.created_at.desc()",
        cascade="all, delete-orphan", backref="application",
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def active_mentee_count(self):
        """Computed live from Matches, never stored, so it can never drift
        out of sync with the matches that actually exist."""
        if self.role != "mentor":
            return 0
        return MentorshipMatch.query.filter(
            MentorshipMatch.mentor_application_id == self.id,
            MentorshipMatch.status.in_(MATCH_ACTIVE_STATUSES),
        ).count()

    def is_at_capacity(self):
        if self.role != "mentor" or not self.mentor_capacity:
            return False
        return self.active_mentee_count() >= self.mentor_capacity


class MentorshipApplicationNote(db.Model):
    """Internal, staff-only note on an application — never returned by
    any public response. Same append-only pattern as MemberNote/
    PartnershipNote.
    """

    __tablename__ = "mentorship_application_notes"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("mentorship_applications.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])


class MentorshipMatch(db.Model):
    """A mentor-mentee pairing within a Program — a real relationship
    (not free text) linking exactly one mentor MentorshipApplication and
    one mentee MentorshipApplication, both required to already be
    role-correct and approved (enforced in api/v1/mentorship.py, not the
    DB, since that needs to query the related rows). Never deleted when a
    pairing ends — see `status`.
    """

    __tablename__ = "mentorship_matches"
    __table_args__ = (
        db.CheckConstraint(_MATCH_STATUS_CHECK_SQL, name="ck_mentorship_matches_status"),
        db.CheckConstraint(
            "planned_end_date IS NULL OR planned_start_date IS NULL OR planned_end_date >= planned_start_date",
            name="ck_mentorship_matches_dates",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("mentorship_programs.id"), nullable=False)
    mentor_application_id = db.Column(db.Integer, db.ForeignKey("mentorship_applications.id"), nullable=False)
    mentee_application_id = db.Column(db.Integer, db.ForeignKey("mentorship_applications.id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="proposed")
    matched_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    planned_start_date = db.Column(db.Date)
    planned_end_date = db.Column(db.Date)
    actual_completion_date = db.Column(db.Date)

    matching_notes = db.Column(db.Text)  # captured at creation — the rationale for this pairing
    closure_reason = db.Column(db.Text)  # optional, set on cancel/rematch_needed/completed

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    program = db.relationship("MentorshipProgram", foreign_keys=[program_id])
    mentor_application = db.relationship("MentorshipApplication", foreign_keys=[mentor_application_id])
    mentee_application = db.relationship("MentorshipApplication", foreign_keys=[mentee_application_id])
    notes = db.relationship(
        "MentorshipMatchNote", order_by="MentorshipMatchNote.created_at.desc()",
        cascade="all, delete-orphan", backref="match",
    )
    sessions = db.relationship(
        "MentorshipSession", order_by="MentorshipSession.session_date.desc()",
        cascade="all, delete-orphan", backref="match",
    )


class MentorshipMatchNote(db.Model):
    """Internal, staff-only note on a match — never returned publicly."""

    __tablename__ = "mentorship_match_notes"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("mentorship_matches.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])


class MentorshipSession(db.Model):
    """A lightweight check-in record on a Match — not a calendar
    invitation, not a video link, not a chat transcript. Admin-only;
    never exposed through any public response (see api/v1/mentorship.py).
    """

    __tablename__ = "mentorship_sessions"
    __table_args__ = (db.CheckConstraint(_SESSION_STATUS_CHECK_SQL, name="ck_mentorship_sessions_status"),)

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("mentorship_matches.id", ondelete="CASCADE"), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    session_number = db.Column(db.Integer)
    status = db.Column(db.String(20), nullable=False, default="scheduled")
    summary = db.Column(db.Text)
    next_step_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
