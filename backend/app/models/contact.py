from app.extensions import db

# A controlled classification of what a general inquiry is about.
# Deliberately excludes "partnership"/"sponsorship"/"advertising" — those
# already have dedicated inquiry workflows (PartnershipInquiry, Advertise)
# and the public Contact form routes visitors there instead of creating a
# duplicate record here (see ContactPage's "Looking for something
# specific?" panel).
CONTACT_INQUIRY_TYPES = (
    "general",
    "editorial",
    "feedback",
    "technical",
    "media_press",
    "speaking",
    "other",
)
_CONTACT_INQUIRY_TYPE_CHECK_SQL = "inquiry_type IN (" + ", ".join(f"'{t}'" for t in CONTACT_INQUIRY_TYPES) + ")"

# A deliberately small lifecycle — this is an inquiry inbox, not a
# ticketing system. See CONTACT_STATUS_TRANSITIONS in
# app/services/contact.py for which moves between these are allowed.
CONTACT_STATUSES = ("new", "in_progress", "resolved", "closed", "spam")
_CONTACT_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in CONTACT_STATUSES) + ")"


class ContactInquiry(db.Model):
    """A general inquiry submitted through the public Contact form — one
    evolving record from receipt through to Resolved/Closed/Spam, matching
    the PartnershipInquiry/StorySubmission pattern used elsewhere rather
    than separate lead/processed tables.

    This is specifically GENERAL contact — never a duplicate of
    PartnershipInquiry, an Advertise inquiry, a StorySubmission, or a
    Nomination. Those keep their own dedicated tables; the public Contact
    form's inquiry type list deliberately excludes their categories.
    """

    __tablename__ = "contact_inquiries"
    __table_args__ = (
        db.CheckConstraint(_CONTACT_INQUIRY_TYPE_CHECK_SQL, name="ck_contact_inquiries_inquiry_type"),
        db.CheckConstraint(_CONTACT_STATUS_CHECK_SQL, name="ck_contact_inquiries_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # Human-friendly, unique, immutable — e.g. "WSF-CON-2026-000123".
    # Generated once via app/services/contact.py:generate_contact_reference
    # right after the row has an id, same pattern as Order.reference.
    reference = db.Column(db.String(30), unique=True, nullable=True, index=True)

    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)

    inquiry_type = db.Column(db.String(30), nullable=False, default="general", index=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)  # plain text only — never rendered as HTML

    # Where this came from — currently always "contact_page", kept as a
    # column (rather than assumed) so a future second entry point (e.g. a
    # homepage widget) doesn't need a schema change.
    source = db.Column(db.String(50), nullable=False, default="contact_page")

    # Records that the visitor acknowledged the privacy notice at
    # submission time — not a legal-consent-management system, just proof
    # the checkbox was ticked (see FORM CONSENT in the task spec).
    privacy_acknowledged = db.Column(db.Boolean, nullable=False, default=False)

    status = db.Column(db.String(20), nullable=False, default="new", index=True)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    assigned_to = db.relationship("User", foreign_keys=[assigned_to_user_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_user_id])
    notes = db.relationship(
        "ContactNote", backref="inquiry", cascade="all, delete-orphan", order_by="ContactNote.created_at"
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class ContactNote(db.Model):
    """An internal, staff-only note on a contact inquiry — never returned
    by any public response. Same append-only pattern as
    SubmissionNote/PartnershipNote/MemberNote.
    """

    __tablename__ = "contact_notes"

    id = db.Column(db.Integer, primary_key=True)
    inquiry_id = db.Column(db.Integer, db.ForeignKey("contact_inquiries.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
