"""First-party WSF Learning certificates of completion.

A LearningCertificate is issued automatically (never by a client) when an
enrollment in a certificate-enabled, WSF-owned program is completed — see
app/services/learning_certificates.py. Everything a certificate states is
SNAPSHOTTED at issue time (recipient, program title, instructors, issuer,
signatory, completion date), so later edits to the program, instructors or
curriculum never change an issued credential, and adding lessons later never
revokes one.

Lifecycle: active -> revoked (terminal). A correction is revoke + reissue: a
new certificate row (replaces_certificate_id -> the old one), so the audit
trail of what was issued is never overwritten. At most one ACTIVE
certificate per enrollment (partial unique index).

`public_id` (random UUID) is the public verification key; `certificate_number`
is the human-readable credential ID (e.g. WSF-LEAD-2027-7K3QZP) and is not
derived from a sequential database id.
"""
import uuid

from app.extensions import db

CERTIFICATE_STATUSES = ("active", "revoked")
_CERTIFICATE_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in CERTIFICATE_STATUSES) + ")"
DEFAULT_CERTIFICATE_TITLE = "Certificate of Completion"
CERTIFICATE_TEMPLATE_VERSION = 1


class LearningCertificate(db.Model):
    __tablename__ = "learning_certificates"
    __table_args__ = (
        db.CheckConstraint(_CERTIFICATE_STATUS_CHECK_SQL, name="ck_learning_certificates_status"),
        db.Index(
            "uq_learning_certificates_one_active_per_enrollment",
            "enrollment_id",
            unique=True,
            postgresql_where=db.text("status = 'active'"),
            sqlite_where=db.text("status = 'active'"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    certificate_number = db.Column(db.String(40), unique=True, nullable=False)

    learning_program_id = db.Column(db.Integer, db.ForeignKey("learning_programs.id"), nullable=False, index=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("learning_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # --- Snapshot at issue time (never re-derived) ---
    recipient_name = db.Column(db.String(200), nullable=False)
    program_title = db.Column(db.String(200), nullable=False)
    instructor_names = db.Column(db.JSON, nullable=False, default=list)
    issuer_name = db.Column(db.String(200), nullable=False)
    certificate_title = db.Column(db.String(120), nullable=False, default=DEFAULT_CERTIFICATE_TITLE)
    signatory_name = db.Column(db.String(120))
    signatory_title = db.Column(db.String(120))
    completed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    template_version = db.Column(db.Integer, nullable=False, default=CERTIFICATE_TEMPLATE_VERSION)

    issued_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    revoked_at = db.Column(db.DateTime(timezone=True))
    revocation_reason = db.Column(db.String(500))
    replaces_certificate_id = db.Column(db.Integer, db.ForeignKey("learning_certificates.id"), nullable=True)

    learning_program = db.relationship("LearningProgram")
    enrollment = db.relationship("LearningEnrollment")
    user = db.relationship("User")
