"""Server-side refresh sessions (the browser half is an HttpOnly cookie).

Signing in creates one row and gives the browser an opaque random token in
the `wsf_refresh` cookie. Only the SHA-256 hash of that token is stored, so
a database read never yields a usable credential. The cookie can only mint
short-lived access tokens (POST /api/v1/auth/refresh); it is never readable
by JavaScript.

A session stops working when it is revoked (sign-out, password reset,
account deactivation), when it expires (30 days after sign-in), or when the
user's auth_version moves on (password reset).
"""
from app.extensions import db


class RefreshSession(db.Model):
    __tablename__ = "refresh_sessions"
    __table_args__ = (db.Index("ix_refresh_sessions_user_active", "user_id", "revoked_at"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    auth_version = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_used_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    revoked_reason = db.Column(db.String(30))
