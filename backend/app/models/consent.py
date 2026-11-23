"""Account-linked cookie-consent history.

The browser keeps the visitor's current choice in localStorage
(`wsf_cookie_consent`, frontend/src/utils/consent.js) because it must
apply immediately, before any request. For a signed-in member, every
distinct decision is ALSO recorded here, append-only, so WSF can show
what was chosen, under which consent version and when.

Never stored: IP address, user agent or any device identifier.
`decided_at` is the time the visitor made the choice (taken from the
browser record); `recorded_at` is when the server stored it. The unique
constraint makes re-sending the same decision (e.g. after a page reload
or on another tab) a no-op rather than a duplicate row.

user_id is SET NULL on account deletion: retention of these rows after
an account ends is decided by the retention rules, not by a cascade.
"""
from app.extensions import db


class ConsentRecord(db.Model):
    __tablename__ = "consent_records"
    __table_args__ = (
        db.UniqueConstraint("user_id", "decided_at", "consent_version", name="uq_consent_records_user_decision"),
        db.Index("ix_consent_records_user_recorded", "user_id", "recorded_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    consent_version = db.Column(db.String(20), nullable=False)
    preferences = db.Column(db.Boolean, nullable=False)
    analytics = db.Column(db.Boolean, nullable=False)
    marketing = db.Column(db.Boolean, nullable=False)
    decided_at = db.Column(db.DateTime(timezone=True), nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
