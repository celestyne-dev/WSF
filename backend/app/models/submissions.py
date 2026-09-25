from app.extensions import db
from app.models.article import AI_INVOLVEMENT_VALUES

# A public story submission is reviewed by editorial staff before it can
# ever inform published content — it is never itself an Article. See
# STORY SUBMISSION VS ARTICLE in the task spec.
#
# submitted: received, not yet reviewed.
# reviewing: editorial team is assessing it.
# needs_information: additional details/materials requested from the submitter.
# shortlisted: potential fit, further review needed.
# approved: approved for editorial development (not yet an Article).
# converted: an Article draft has been created from this submission.
# published: the linked Article has actually been published (see
#   `is_published`/status-guard below — never set manually to imply
#   publication that hasn't happened).
# declined: not proceeding.
# withdrawn: submitter requested withdrawal, or the process ended that way.
# archived: historical record retained, out of active review.
SUBMISSION_STATUSES = (
    "submitted",
    "reviewing",
    "needs_information",
    "shortlisted",
    "approved",
    "converted",
    "published",
    "declined",
    "withdrawn",
    "archived",
)
_SUBMISSION_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in SUBMISSION_STATUSES) + ")"

# A controlled classification of what kind of story this is — editorial
# reuses/aligns with the existing Topics/Series taxonomy for subject
# matter, but this captures the narrative *shape* a submitter is offering,
# which topics/series alone don't express.
STORY_TYPES = (
    "personal_story",
    "career_journey",
    "leadership_story",
    "founder_story",
    "business_story",
    "community_impact",
    "starting_again",
    "overcoming_barriers",
    "women_doing_incredible_things",
    "women_leading_organizations",
    "workplace_story",
    "opportunity_achievement",
    "other",
)
_STORY_TYPE_CHECK_SQL = "story_type IS NULL OR story_type IN (" + ", ".join(
    f"'{t}'" for t in STORY_TYPES
) + ")"

# Where the submitted text actually came from — informs editorial
# handling, never automated copyright verification.
CONTENT_ORIGINS = ("first_person", "on_behalf_of", "previously_published", "adapted")
_CONTENT_ORIGIN_CHECK_SQL = "content_origin IS NULL OR content_origin IN (" + ", ".join(
    f"'{o}'" for o in CONTENT_ORIGINS
) + ")"

_AI_INVOLVEMENT_CHECK_SQL = "ai_involvement IN (" + ", ".join(f"'{v}'" for v in AI_INVOLVEMENT_VALUES) + ")"

# Simple internal indicators, not a fact-checking platform.
VERIFICATION_STATUSES = ("unverified", "verification_needed", "verified")
_VERIFICATION_STATUS_CHECK_SQL = "verification_status IN (" + ", ".join(
    f"'{v}'" for v in VERIFICATION_STATUSES
) + ")"

# When a story is about someone other than the submitter, staff need a
# clear indicator of whether the subject's own consent is confirmed
# before anything about her can be published — never inferred, always
# staff-recorded.
SUBJECT_PERMISSION_STATUSES = ("not_applicable", "unknown", "needs_confirmation", "confirmed")
_SUBJECT_PERMISSION_CHECK_SQL = "subject_permission_status IN (" + ", ".join(
    f"'{s}'" for s in SUBJECT_PERMISSION_STATUSES
) + ")"

submission_topics = db.Table(
    "submission_topics",
    db.Column("submission_id", db.Integer, db.ForeignKey("story_submissions.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)


class StorySubmission(db.Model):
    """A story received from the public — reviewed and classified by
    editorial staff, and only ever turned into an Article through a
    deliberate "Create Article Draft" handoff (never auto-published). One
    evolving record from first submission through to Converted/Published/
    Declined/Withdrawn/Archived, matching the PartnershipInquiry/Member
    pattern used elsewhere rather than separate lead/converted tables.
    """

    __tablename__ = "story_submissions"
    __table_args__ = (
        db.CheckConstraint(_SUBMISSION_STATUS_CHECK_SQL, name="ck_story_submissions_status"),
        db.CheckConstraint(_STORY_TYPE_CHECK_SQL, name="ck_story_submissions_story_type"),
        db.CheckConstraint(_CONTENT_ORIGIN_CHECK_SQL, name="ck_story_submissions_content_origin"),
        db.CheckConstraint(_AI_INVOLVEMENT_CHECK_SQL, name="ck_story_submissions_ai_involvement"),
        db.CheckConstraint(_VERIFICATION_STATUS_CHECK_SQL, name="ck_story_submissions_verification_status"),
        db.CheckConstraint(_SUBJECT_PERMISSION_CHECK_SQL, name="ck_story_submissions_subject_permission"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # Human-friendly, unique, immutable — e.g. "WSF-STORY-2026-00125".
    # Generated once via app/services/submissions.py:generate_submission_reference
    # right after the row has an id, same pattern as Order.reference.
    reference = db.Column(db.String(30), unique=True, nullable=True, index=True)

    # --- Submitter (About You) ---
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    city = db.Column(db.String(120))
    professional_title = db.Column(db.String(200))
    organization_name = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(500))
    website_url = db.Column(db.String(500))

    # --- Story ---
    title = db.Column(db.String(300), nullable=False)
    summary = db.Column(db.Text)
    body = db.Column(db.Text, nullable=False)  # the original submitted material — never overwritten
    why_it_matters = db.Column(db.Text)
    key_lessons = db.Column(db.Text)
    story_type = db.Column(db.String(40))

    # --- Subject ---
    subject_is_submitter = db.Column(db.Boolean, nullable=False, default=True)
    subject_name = db.Column(db.String(200))
    subject_relationship = db.Column(db.String(200))
    subject_permission_status = db.Column(db.String(20), nullable=False, default="not_applicable")

    # --- Provenance / content origin ---
    content_origin = db.Column(db.String(20))
    previous_publication_url = db.Column(db.String(500))
    ai_involvement = db.Column(db.String(30), nullable=False, default="none")
    ai_provenance_note = db.Column(db.Text)

    # --- Consent / rights (never exposed publicly) ---
    consent_review_given = db.Column(db.Boolean, nullable=False, default=False)
    consent_contact_given = db.Column(db.Boolean, nullable=False, default=False)
    consent_accuracy_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    consent_media_rights_confirmed = db.Column(db.Boolean, nullable=True)
    consent_recorded_at = db.Column(db.DateTime(timezone=True))

    # Separate, optional, unchecked-by-default — see NEWSLETTER CONSENT.
    # The live subscription lives in NewsletterSubscriber; this is only an
    # audit record of what the submitter asked for at submission time.
    newsletter_opt_in = db.Column(db.Boolean, nullable=False, default=False)

    # --- Editorial classification (staff-set; never required of the public submitter) ---
    series_id = db.Column(db.Integer, db.ForeignKey("series.id"), nullable=True)
    recommended_format = db.Column(db.String(120))
    verification_status = db.Column(db.String(20), nullable=False, default="unverified")
    permission_followup_required = db.Column(db.Boolean, nullable=False, default=False)
    media_followup_required = db.Column(db.Boolean, nullable=False, default=False)
    information_requested_note = db.Column(db.Text)  # what's needed, when status = needs_information

    # --- Review / status ---
    status = db.Column(db.String(20), nullable=False, default="submitted")
    editorial_assessment = db.Column(db.Text)
    assigned_editor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True))

    # --- Linked records (all optional, all editor-controlled — never auto-created) ---
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)

    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    series = db.relationship("Series", foreign_keys=[series_id])
    assigned_editor = db.relationship("User", foreign_keys=[assigned_editor_id])
    person = db.relationship("Person", foreign_keys=[person_id])
    organization = db.relationship("Organization", foreign_keys=[organization_id])
    topics = db.relationship("Topic", secondary=submission_topics)
    notes = db.relationship(
        "SubmissionNote", backref="submission", cascade="all, delete-orphan", order_by="SubmissionNote.created_at"
    )
    media_items = db.relationship(
        "SubmissionMedia", backref="submission", cascade="all, delete-orphan", order_by="SubmissionMedia.created_at"
    )
    # `resulting_article` is defined as a backref from Article.source_submission_id
    # (see app/models/article.py) — the authoritative FK lives on Article.

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def sync_published_state(self):
        """A submission may only read as Published when its linked Article
        actually is — never set manually to imply a publication that
        hasn't happened. Called after loading/whenever the linked
        Article's status might have changed.
        """
        if self.status == "published" and (not self.resulting_article or self.resulting_article.status != "published"):
            self.status = "converted"
        elif self.status == "converted" and self.resulting_article and self.resulting_article.status == "published":
            self.status = "published"


class SubmissionNote(db.Model):
    """An internal, staff-only note on a submission — never returned by any
    public response. Same append-only pattern as PartnershipNote/MemberNote.
    """

    __tablename__ = "submission_notes"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("story_submissions.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])


class SubmissionMedia(db.Model):
    """One optional image attached to a submission, with the rights/credit
    context editorial needs before ever reusing it — reuses the existing
    Media model/upload service for storage (see the public
    `POST /submissions/media` route), never a second file-storage system.
    Kept as its own association row (not a bare many-to-many) because the
    caption/credit/rights confirmation are specific to this submission's
    use of the image, not the shared Media row's global metadata.
    """

    __tablename__ = "submission_media"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("story_submissions.id", ondelete="CASCADE"), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    caption = db.Column(db.String(500))
    credit = db.Column(db.String(255))
    rights_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    media = db.relationship("Media", foreign_keys=[media_id])
