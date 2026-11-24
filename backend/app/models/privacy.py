"""Privacy requests (Step 16): the Studio log of requests about personal
data — access/export, correction, deletion, other — with WSF's 30-day
operational target (a working target, not a statement of any legal
deadline). Self-service export and deletion create rows automatically;
staff add requests that arrive by email/phone. Every change is also in the
Audit Log."""
from app.extensions import db

PRIVACY_REQUEST_TYPES = ("access", "correction", "deletion", "other")
PRIVACY_REQUEST_STATUSES = ("open", "in_progress", "completed", "declined")
PRIVACY_REQUEST_TARGET_DAYS = 30
_TYPE_CHECK = "request_type IN (" + ", ".join(f"'{t}'" for t in PRIVACY_REQUEST_TYPES) + ")"
_STATUS_CHECK = "status IN (" + ", ".join(f"'{s}'" for s in PRIVACY_REQUEST_STATUSES) + ")"


class PrivacyRequest(db.Model):
    __tablename__ = "privacy_requests"
    __table_args__ = (
        db.CheckConstraint(_TYPE_CHECK, name="ck_privacy_requests_type"),
        db.CheckConstraint(_STATUS_CHECK, name="ck_privacy_requests_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # The member, when the request is tied to an account. SET NULL: the
    # request record outlives a deleted account (it documents the deletion).
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    requester_name = db.Column(db.String(200))
    requester_email = db.Column(db.String(255))
    request_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")
    source = db.Column(db.String(40), nullable=False, default="studio")  # self_service | studio | member_form
    details = db.Column(db.Text)
    admin_notes = db.Column(db.Text)
    opened_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    due_at = db.Column(db.DateTime(timezone=True), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(),
                           nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
