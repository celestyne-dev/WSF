"""Refresh sessions + the HttpOnly refresh cookie (see app/models/refresh_session.py).

Cookie: `wsf_refresh` (REFRESH_COOKIE_NAME), HttpOnly, Secure, SameSite=Strict,
Path=/api/v1/auth/refresh, Max-Age = the session's remaining lifetime (30 days
from sign-in). The path is the ONE endpoint that uses it:
    POST   /api/v1/auth/refresh   -> a new in-memory access token
    DELETE /api/v1/auth/refresh   -> sign out (revoke + clear the cookie)
so the browser never sends it anywhere else.

CSRF: both operations require (1) the custom header `X-WSF-CSRF: 1`, which a
cross-site page cannot send without a CORS preflight that WSF only allows
for its own origins, and (2) an Origin (or, if absent, Referer) that is this
site or a configured CORS origin. SameSite=Strict already keeps the cookie
off cross-site requests; these checks also cover same-site subdomains. No
extra CSRF cookie is needed.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import current_app, request

from app.extensions import db
from app.models.refresh_session import RefreshSession

CSRF_HEADER = "X-WSF-CSRF"
TOKEN_BYTES = 32


class RefreshSessionError(Exception):
    """The presented refresh cookie is not a usable session."""


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def hash_token(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_session(user, two_factor_verified=False):
    """New session for `user`. Returns (raw token for the cookie, session)."""
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    session = RefreshSession(
        user_id=user.id,
        token_hash=hash_token(raw),
        auth_version=user.auth_version,
        two_factor_verified=bool(two_factor_verified),
        expires_at=_now() + current_app.config["REFRESH_SESSION_LIFETIME"],
    )
    db.session.add(session)
    db.session.flush()
    return raw, session


def find_session(raw):
    if not raw or not isinstance(raw, str) or len(raw) > 200:
        return None
    return RefreshSession.query.filter_by(token_hash=hash_token(raw)).first()


def validate_session(raw):
    """The active session and its user for a cookie value, or raise."""
    from app.models.user import User

    session = find_session(raw)
    if session is None:
        raise RefreshSessionError("unknown")
    if session.revoked_at is not None:
        raise RefreshSessionError("revoked")
    if _aware(session.expires_at) <= _now():
        raise RefreshSessionError("expired")
    user = db.session.get(User, session.user_id)
    if user is None or not user.is_active:
        raise RefreshSessionError("inactive")
    if session.auth_version != user.auth_version:
        raise RefreshSessionError("credentials_changed")
    return session, user


def revoke(session, reason):
    if session is not None and session.revoked_at is None:
        session.revoked_at = _now()
        session.revoked_reason = reason


def revoke_all_for_user(user_id, reason):
    """Ends every active session of a user (password reset, deactivation)."""
    count = (RefreshSession.query
             .filter(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
             .update({"revoked_at": _now(), "revoked_reason": reason}, synchronize_session=False))
    return count


# --- cookie --------------------------------------------------------------------------------


def set_refresh_cookie(response, raw, session):
    cfg = current_app.config
    max_age = max(0, int((_aware(session.expires_at) - _now()).total_seconds()))
    response.set_cookie(
        cfg["REFRESH_COOKIE_NAME"], raw, max_age=max_age, path=cfg["REFRESH_COOKIE_PATH"],
        secure=cfg["REFRESH_COOKIE_SECURE"], httponly=True, samesite="Strict",
    )
    return response


def clear_refresh_cookie(response):
    cfg = current_app.config
    response.delete_cookie(cfg["REFRESH_COOKIE_NAME"], path=cfg["REFRESH_COOKIE_PATH"],
                           secure=cfg["REFRESH_COOKIE_SECURE"], httponly=True, samesite="Strict")
    return response


def read_refresh_cookie():
    return request.cookies.get(current_app.config["REFRESH_COOKIE_NAME"])


# --- CSRF ----------------------------------------------------------------------------------


def _origin_of(url):
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def allowed_origins():
    origins = {_origin_of(request.host_url)}
    for value in current_app.config.get("CORS_ORIGINS") or []:
        origins.add(_origin_of(value))
    if current_app.config.get("FRONTEND_URL"):
        origins.add(_origin_of(current_app.config["FRONTEND_URL"]))
    origins.discard(None)
    return origins


def csrf_problem():
    """None when the request may use the refresh cookie, else a reason."""
    if request.headers.get(CSRF_HEADER) != "1":
        return "missing_csrf_header"
    source = request.headers.get("Origin") or request.headers.get("Referer")
    if not source:
        return "missing_origin"
    if _origin_of(source) not in allowed_origins():
        return "origin_not_allowed"
    return None
