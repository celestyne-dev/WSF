"""Forgot/reset-password flow.

Security properties this module is responsible for maintaining:

- Account enumeration: request_password_reset() always completes
  successfully from its caller's point of view, whether the email
  belongs to an active account, an inactive one, or no account at all.
  Nothing is created, emailed, or audited for the latter two cases — see
  its docstring below.
- Raw tokens are never persisted. Only a SHA-256 hex digest is stored
  (PasswordResetToken.token_hash); the raw token exists only in the
  emailed link and this process's own memory for the duration of the
  request that generated or validated it.
- One-time use: a token is consumed (used_at set) the moment it's
  successfully used to reset a password, or superseded by a newer
  request for the same account, or discarded after a failed email send.
  A used, expired, or unknown token is indistinguishable to the caller —
  see reset_password()'s single generic ApiError.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.audit import log_action
from app.services.email import send_email
from app.utils.responses import ApiError

# Deliberately short: a password-reset link is a bearer credential that's
# often sitting in an inbox/spam folder for a while, so this trades a
# little user convenience for a conservative exposure window. 30 minutes
# is well above what a user actually clicking the email right away needs,
# and short enough to make a stale, forgotten reset email far less
# useful if that inbox is later compromised.
RESET_TOKEN_TTL_MINUTES = 30

_GENERIC_INVALID_TOKEN_MESSAGE = "This password reset link is invalid or has expired."


def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def request_password_reset(email):
    """Always "succeeds" — never raises, never returns anything the
    caller could use to distinguish outcomes. ForgotPasswordResource
    calls this and then unconditionally returns the same generic public
    response, regardless of what happened here:

    - unknown email, or an inactive account: does nothing at all (no
      token row, no email attempt, no audit entry) — there is nothing
      safe to log that wouldn't itself record which emails exist.
    - known, active account: invalidates any previous unused reset
      tokens for it, creates a new one, and attempts delivery. A
      delivery failure invalidates the just-created token (see
      app/services/email.py's send_email()) and logs an operational
      error with no raw token/URL/password — never a user-facing error.
    """
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return

    user = User.query.filter_by(email=normalized_email).first()
    if not user or not user.is_active:
        return

    now = datetime.now(timezone.utc)

    # Supersede any previous unused reset request for this account before
    # issuing a new one, so at most one reset link is ever valid at a
    # time (see task spec: a second request invalidates the first).
    PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update({"used_at": now})

    raw_token = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    )
    db.session.add(token)
    db.session.commit()

    if not _send_reset_email(user, raw_token):
        # Nobody actually received a usable link — don't leave one lying
        # around in the database. No raw token, URL, or password in this
        # log line, only the user id.
        token.used_at = datetime.now(timezone.utc)
        db.session.commit()
        current_app.logger.error(
            "Password reset email delivery failed for user_id=%s; token invalidated.", user.id
        )
        return

    log_action(user, "password_reset.requested", "User", user.id)


def _send_reset_email(user, raw_token):
    frontend_url = current_app.config["FRONTEND_URL"].rstrip("/")
    # A URL fragment (#token=...), not a query string — the raw token
    # then never appears in an ordinary HTTP request path, server access
    # log, or Referer header; see ResetPasswordPage.jsx, which reads
    # window.location.hash client-side only.
    reset_url = f"{frontend_url}/reset-password#token={raw_token}"

    text_body = (
        "A password reset was requested for your Women Shaping Futures account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in {RESET_TOKEN_TTL_MINUTES} minutes.\n\n"
        "If you didn't request this, you can safely ignore this email — "
        "your password has not been changed."
    )
    html_body = (
        "<p>A password reset was requested for your Women Shaping Futures account.</p>"
        f'<p><a href="{reset_url}">Reset your password</a></p>'
        f"<p>This link expires in {RESET_TOKEN_TTL_MINUTES} minutes.</p>"
        "<p>If you didn't request this, you can safely ignore this email — "
        "your password has not been changed.</p>"
    )
    return send_email(
        to=user.email,
        subject="Reset your Women Shaping Futures password",
        text_body=text_body,
        html_body=html_body,
    )


def reset_password(raw_token, new_password):
    """Validates `raw_token`, and if valid, sets `new_password` on the
    token's account — clearing must_change_password and bumping
    auth_version (invalidating every JWT issued before now; see
    app/auth/jwt_callbacks.py) — then consumes the token so it can never
    be reused. Raises ApiError(422, code="invalid_token") for any
    invalid/expired/already-used/unknown token, with the same generic
    message regardless of which of those it actually was. Returns the
    User on success. Never logs the caller in.
    """
    token = _find_usable_token(raw_token)
    if token is None:
        raise ApiError(_GENERIC_INVALID_TOKEN_MESSAGE, 422, code="invalid_token")

    user = db.session.get(User, token.user_id)
    if not user or not user.is_active:
        raise ApiError(_GENERIC_INVALID_TOKEN_MESSAGE, 422, code="invalid_token")

    user.set_password(new_password)
    user.must_change_password = False
    user.auth_version += 1
    token.used_at = datetime.now(timezone.utc)
    db.session.commit()

    log_action(user, "password_reset.completed", "User", user.id)
    return user


def _find_usable_token(raw_token):
    if not raw_token or not isinstance(raw_token, str):
        return None
    token = PasswordResetToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if token is None:
        return None
    if token.used_at is not None:
        return None
    if token.expires_at < datetime.now(timezone.utc):
        return None
    return token
