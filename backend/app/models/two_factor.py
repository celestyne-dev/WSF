"""TOTP two-factor authentication (app/services/two_factor.py).

Kept in separate tables (not columns on users) so no user serializer can
ever include them.

- user_two_factor: one row per user who started or completed set-up. The
  TOTP secret is stored ENCRYPTED (Fernet, TWO_FACTOR_ENCRYPTION_KEY);
  `pending_secret_encrypted` holds a secret during set-up until the first
  code confirms it. `last_used_step` blocks replaying a code.
- two_factor_recovery_codes: one-use recovery codes, stored only as keyed
  HMAC-SHA256 hashes; `used_at` marks a spent code.
"""
from app.extensions import db


class UserTwoFactor(db.Model):
    __tablename__ = "user_two_factor"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    secret_encrypted = db.Column(db.Text)
    pending_secret_encrypted = db.Column(db.Text)
    enabled_at = db.Column(db.DateTime(timezone=True))
    last_used_step = db.Column(db.BigInteger)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(),
                           nullable=False)


class TwoFactorRecoveryCode(db.Model):
    __tablename__ = "two_factor_recovery_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
