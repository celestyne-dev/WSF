"""First-party email verification (Batch 4 corrections).

* Secure random link token (only its SHA-256 hash is stored), valid 24 hours.
* A new link supersedes every earlier unused one; each link works once.
* Accounts registered under the verification-required flow get no normal
  authenticated access until verified (app/auth/decorators.py). Accounts
  that predate it keep access and are offered verification.
* Independent of newsletter double opt-in.
Audit events never contain the token."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.email_verification import EmailVerificationToken
from app.models.user import User

TOKEN_LIFETIME = timedelta(hours=24)


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_verified(user):
    return user is not None and user.email_verified_at is not None


def verification_pending(user):
    """True when this account may not be used until its email is verified."""
    return bool(user is not None and user.email_verification_required and user.email_verified_at is None)


def send_verification(user, actor=None):
    """Issue a fresh link (superseding earlier unused ones) and email it.
    Returns True only if the email service reports a successful hand-off.
    Caller commits."""
    from app.services.audit import log_action
    from app.services.email import TRANSACTIONAL, send_email

    now = _now()
    EmailVerificationToken.query.filter_by(user_id=user.id, used_at=None, superseded_at=None).update(
        {"superseded_at": now}, synchronize_session=False)
    raw = secrets.token_urlsafe(32)
    db.session.add(EmailVerificationToken(user_id=user.id, email=user.email.lower(), token_hash=_hash(raw),
                                          expires_at=now + TOKEN_LIFETIME))
    db.session.flush()
    base = current_app.config["FRONTEND_URL"].rstrip("/")
    sent = send_email(
        user.email, "Confirm your email address for Women Shaping Futures",
        "Please confirm that this is your email address for your Women Shaping Futures account:\n\n"
        f"{base}/verify-email/{raw}\n\n"
        "Open the link and press the button to confirm. It works once, for 24 hours.\n"
        "If you didn't create a Women Shaping Futures account, ignore this email.\n",
        category=TRANSACTIONAL)
    if not sent:
        # Nothing reached the person: don't leave a live link behind, and
        # let them try again straight away.
        EmailVerificationToken.query.filter_by(user_id=user.id, used_at=None, superseded_at=None).update(
            {"superseded_at": now}, synchronize_session=False)
    log_action(actor or user, "user.email_verification_sent" if sent else "user.email_verification_send_failed",
               "User", user.id)
    return bool(sent)


def verify_token(raw):
    """Returns (outcome, user). Outcomes: "verified", "already_verified",
    "expired", "superseded", "invalid". Each link works once; the row is
    locked so two clicks can't both succeed."""
    from app.services.audit import log_action

    if not raw or not isinstance(raw, str) or len(raw) > 100:
        return "invalid", None
    row = (EmailVerificationToken.query.filter_by(token_hash=_hash(raw)).with_for_update().first())
    if row is None:
        return "invalid", None
    user = db.session.get(User, row.user_id)
    if user is None or user.email.lower() != row.email:
        return "invalid", None  # the address changed since this link was sent
    if row.used_at is not None:
        return ("already_verified" if is_verified(user) else "invalid"), user
    if row.superseded_at is not None:
        return ("already_verified" if is_verified(user) else "superseded"), user
    if _aware(row.expires_at) <= _now():
        return "expired", user
    now = _now()
    row.used_at = now
    first = user.email_verified_at is None
    if first:
        user.email_verified_at = now
    db.session.commit()
    if first:
        log_action(user, "user.email_verified", "User", user.id)
    return ("verified" if first else "already_verified"), user


def email_changed(user):
    """An email change (staff edit) voids ownership proof and outstanding links."""
    user.email_verified_at = None
    EmailVerificationToken.query.filter_by(user_id=user.id, used_at=None, superseded_at=None).update(
        {"superseded_at": _now()}, synchronize_session=False)
