"""One-time, short-lived password-reset tokens (see
app/services/password_reset.py for generation/validation/consumption).

Only a SHA-256 digest of the raw token is ever stored in `token_hash` —
the raw token itself exists only in the emailed reset link and this
request's own short-lived memory, never in Postgres, a log line, or an
audit entry. See app/services/password_reset.py's hash_token().
"""
from app.extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    # NULL = still unused/active. Set the moment the token is consumed by
    # a successful reset, superseded by a newer reset request for the
    # same account, or discarded after a failed email delivery attempt —
    # see app/services/password_reset.py for all three call sites.
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])
