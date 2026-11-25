"""First-party email verification (Batch 4 corrections).

Proves the account holder controls the address before email-matched
records are ever linked to the account. Separate from newsletter double
opt-in. Only a SHA-256 hash of each link token is stored."""
from app.extensions import db


class EmailVerificationToken(db.Model):
    __tablename__ = "email_verification_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # The address the link was sent to: a later email change makes it useless.
    email = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    superseded_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User")
