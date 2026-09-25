from app.extensions import db

# A public nomination is reviewed by editorial staff before it can inform
# any published content — it is never itself public. See NOMINATION VS
# STORY SUBMISSION and NOMINEE VS PERSON in the task spec.
#
# submitted: received, not yet reviewed.
# reviewing: editorial team is assessing it.
# verification_needed: key nominee/achievement details need checking.
# shortlisted: strong candidate under further consideration.
# approved: approved for editorial/recognition development.
# in_editorial: linked editorial content (an Article draft) is underway.
# published: the linked Article's own status is actually published (see
#   `sync_published_state()` — never set manually to imply a recognition
#   that hasn't happened).
# declined: not proceeding.
# withdrawn: removed from consideration.
# archived: historical record retained.
NOMINATION_STATUSES = (
    "submitted", "reviewing", "verification_needed", "shortlisted", "approved",
    "in_editorial", "published", "declined", "withdrawn", "archived",
)
_NOMINATION_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in NOMINATION_STATUSES) + ")"

# Whether the nominee is known to be aware of the nomination — informational
# for editorial contact planning, never a legal consent verification.
NOMINEE_AWARENESS_VALUES = ("aware", "not_aware", "unknown")
_NOMINEE_AWARENESS_CHECK_SQL = "nominee_awareness IN (" + ", ".join(
    f"'{v}'" for v in NOMINEE_AWARENESS_VALUES
) + ")"

# A simple internal verification workflow — not a fact-checking platform.
VERIFICATION_STATES = ("not_started", "in_progress", "complete")
_VERIFICATION_STATE_CHECK_SQL = "verification_state IN (" + ", ".join(
    f"'{v}'" for v in VERIFICATION_STATES
) + ")"

nomination_topics = db.Table(
    "nomination_topics",
    db.Column("nomination_id", db.Integer, db.ForeignKey("nominations.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)


class Nomination(db.Model):
    """A nomination proposing a woman for editorial recognition — reviewed
    and classified by editorial staff, and only ever turned into
    editorial content through a deliberate handoff (never auto-published).
    One evolving record from first submission through to In Editorial/
    Published/Declined/Withdrawn/Archived, matching the StorySubmission/
    PartnershipInquiry/Member pattern used elsewhere.

    Deliberately distinct from StorySubmission: a nomination proposes a
    *person* for recognition; it does not carry a full first-person
    narrative. If an approved nomination later needs a full story, staff
    use the existing Story Submission / Article workflow directly — this
    model never duplicates that content shape.
    """

    __tablename__ = "nominations"
    __table_args__ = (
        db.CheckConstraint(_NOMINATION_STATUS_CHECK_SQL, name="ck_nominations_status"),
        db.CheckConstraint(_NOMINEE_AWARENESS_CHECK_SQL, name="ck_nominations_nominee_awareness"),
        db.CheckConstraint(_VERIFICATION_STATE_CHECK_SQL, name="ck_nominations_verification_state"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # Human-friendly, unique, immutable — e.g. "WSF-NOM-2026-00124".
    # Generated once via app/services/nominations.py:generate_nomination_reference
    # right after the row has an id, same pattern as Order.reference.
    reference = db.Column(db.String(30), unique=True, nullable=True, index=True)

    # --- Nominee (About the nominee) ---
    nominee_name = db.Column(db.String(200), nullable=False)
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    city = db.Column(db.String(120))
    professional_title = db.Column(db.String(200))
    organization_name = db.Column(db.String(200))
    website_url = db.Column(db.String(500))
    linkedin_url = db.Column(db.String(500))
    short_bio = db.Column(db.Text)
    # Admin-only follow-up contact — never collected as a required public
    # field, never exposed publicly (see NOMINEE CONTACT INFORMATION).
    nominee_email = db.Column(db.String(255))

    # --- Why you are nominating her ---
    nomination_summary = db.Column(db.String(300))
    achievements = db.Column(db.Text, nullable=False)  # what has she done / key achievements
    why_significant = db.Column(db.Text)
    who_impacted = db.Column(db.Text)
    # [{"url": "...", "label": "..."}] — structured rather than a raw text
    # blob, validated at submission time (see schemas/nominations.py).
    supporting_links = db.Column(db.JSON)
    # An optional public suggestion; editors remain authoritative and may
    # change this freely during review (see NOMINATION TYPES / SERIES).
    series_id = db.Column(db.Integer, db.ForeignKey("series.id"), nullable=True)

    # --- Self-nomination ---
    is_self_nomination = db.Column(db.Boolean, nullable=False, default=False)

    # --- About the nominator (private) ---
    nominator_name = db.Column(db.String(200), nullable=False)
    nominator_email = db.Column(db.String(255), nullable=False)
    nominator_organization = db.Column(db.String(200))
    relationship_to_nominee = db.Column(db.String(200))
    nominee_awareness = db.Column(db.String(20), nullable=False, default="unknown")

    # --- Consent (never exposed publicly) ---
    consent_accuracy_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    consent_review_given = db.Column(db.Boolean, nullable=False, default=False)
    consent_contact_given = db.Column(db.Boolean, nullable=False, default=False)
    consent_recorded_at = db.Column(db.DateTime(timezone=True))

    # Separate, optional, unchecked-by-default — see NEWSLETTER CONSENT.
    # The live subscription lives in NewsletterSubscriber; this is only an
    # audit record of what the nominator asked for at submission time.
    newsletter_opt_in = db.Column(db.Boolean, nullable=False, default=False)

    # --- Duplicate detection (never auto-merged) ---
    # Set at creation time when another nomination shares a normalized
    # nominee name — a simple, non-destructive editorial signal, not a
    # fuzzy-matching or AI system. See DUPLICATE NOMINATION HANDLING.
    possible_duplicate = db.Column(db.Boolean, nullable=False, default=False)

    # --- Review / status ---
    status = db.Column(db.String(20), nullable=False, default="submitted")
    editorial_assessment = db.Column(db.Text)
    assigned_reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True))

    verification_state = db.Column(db.String(20), nullable=False, default="not_started")
    verification_notes = db.Column(db.Text)
    contact_nominee_before_publication = db.Column(db.Boolean, nullable=False, default=False)

    # --- Linked records (all optional, all editor-controlled — never auto-created) ---
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    # A simple internal indicator that a new Person profile should
    # eventually be created through People CMS — never creates one here.
    person_profile_needed = db.Column(db.Boolean, nullable=False, default=False)

    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    series = db.relationship("Series", foreign_keys=[series_id])
    assigned_reviewer = db.relationship("User", foreign_keys=[assigned_reviewer_id])
    person = db.relationship("Person", foreign_keys=[person_id])
    organization = db.relationship("Organization", foreign_keys=[organization_id])
    topics = db.relationship("Topic", secondary=nomination_topics)
    notes = db.relationship(
        "NominationNote", backref="nomination", cascade="all, delete-orphan", order_by="NominationNote.created_at"
    )
    # `resulting_article` is defined as a backref from Article.source_nomination_id
    # (see app/models/article.py) — the authoritative FK lives on Article.

    def sync_published_state(self):
        """A nomination may only read as Published when its linked Article
        actually is — never set manually to imply a recognition that
        hasn't happened. Called after loading/whenever the linked
        Article's status might have changed.
        """
        if self.status == "published" and (not self.resulting_article or self.resulting_article.status != "published"):
            self.status = "in_editorial"
        elif self.status == "in_editorial" and self.resulting_article and self.resulting_article.status == "published":
            self.status = "published"


class NominationNote(db.Model):
    """An internal, staff-only note on a nomination — never returned by any
    public response. Same append-only pattern as SubmissionNote/
    PartnershipNote/MemberNote.
    """

    __tablename__ = "nomination_notes"

    id = db.Column(db.Integer, primary_key=True)
    nomination_id = db.Column(db.Integer, db.ForeignKey("nominations.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
