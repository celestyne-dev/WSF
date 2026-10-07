"""Protected-file delivery for circle_only Resources (Module 10, part A).

A circle_only Resource's real file is never reachable by a public URL —
it lives under config.PROTECTED_MEDIA_ROOT, a filesystem location Nginx
never serves (see deploy/nginx/womenshapingfutures.conf.example, which
only aliases MEDIA_URL -> MEDIA_ROOT, a different, genuinely-public
directory). The only way to it is:

  1. POST /resources/{slug}/access succeeds (app/services/resource_access
     .py's check_resource_access() has already confirmed current Circle
     entitlement) and calls issue_download_token() here, which returns a
     short-lived, resource-bound, opaque token.
  2. GET /resources/downloads/{token} (ResourceDownloadResource in
     app/api/v1/resources.py) calls resolve_download_token(), which
     verifies the token's hash/expiry/resource binding and nothing else
     — Circle entitlement is deliberately NOT re-checked at this step,
     exactly like a password-reset token's redemption never re-checks
     "is this really their email" (see app/services/password_reset.py);
     that was already established, moments earlier, by step 1.

Same storage convention as app/services/password_reset.py: only a
SHA-256 digest of the raw token is ever persisted (ResourceDownloadToken
.token_hash) — the raw token exists only in step 1's one-time JSON
response and the resulting download URL, never in Postgres or a log
line.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.resource import ResourceDownloadToken
from app.utils.responses import ApiError

_GENERIC_INVALID_DOWNLOAD_MESSAGE = "This download link is invalid or has expired."


def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def is_safe_protected_path(path):
    """True only for a bare relative filename/path with no way to escape
    PROTECTED_MEDIA_ROOT — no absolute path, no `..` traversal segment,
    no backslash (Windows-style separators are never meaningful here and
    would otherwise slip past a POSIX-only traversal check), no leading
    `/`. send_from_directory() (used by the download route below)
    already refuses `..` traversal on its own, but this is checked again
    at save time too — same "re-validate, don't just trust the DB row"
    discipline app/utils/urls.py's is_safe_resource_target() docstring
    describes for Resource.file_url.
    """
    if not path or not isinstance(path, str):
        return False
    if path.startswith("/") or path.startswith("\\"):
        return False
    if ".." in path.split("/") or ".." in path.split("\\"):
        return False
    if "\\" in path:
        return False
    return True


def issue_download_token(resource, user):
    """Called only after the caller has already confirmed `user` may
    access `resource` right now (see check_resource_access()). Returns
    the raw token string — store it nowhere; it belongs only in the
    caller's one-time JSON response.
    """
    ttl_minutes = current_app.config.get("RESOURCE_DOWNLOAD_TOKEN_TTL_MINUTES", 10)
    raw_token = secrets.token_urlsafe(32)
    token = ResourceDownloadToken(
        resource_id=resource.id,
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )
    db.session.add(token)
    db.session.commit()
    return raw_token


def resolve_download_token(raw_token):
    """Returns the bound Resource for a valid, unexpired token. Raises
    ApiError(404) for anything else — unknown token, expired token, or a
    resource that's since stopped being circle_only/publicly visible —
    with the same generic message in every case, so a tampered token and
    an expired one are indistinguishable to the caller (same posture as
    password_reset.py's _find_usable_token/_GENERIC_INVALID_TOKEN_MESSAGE).
    """
    if not raw_token or not isinstance(raw_token, str):
        raise ApiError(_GENERIC_INVALID_DOWNLOAD_MESSAGE, 404, code="not_found")

    token = ResourceDownloadToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if token is None:
        raise ApiError(_GENERIC_INVALID_DOWNLOAD_MESSAGE, 404, code="not_found")
    if token.expires_at < datetime.now(timezone.utc):
        raise ApiError(_GENERIC_INVALID_DOWNLOAD_MESSAGE, 404, code="not_found")

    resource = token.resource
    if (
        resource is None
        or resource.access_type != "circle_only"
        or not resource.is_publicly_visible()
        or not resource.protected_file_path
        or not is_safe_protected_path(resource.protected_file_path)
    ):
        raise ApiError(_GENERIC_INVALID_DOWNLOAD_MESSAGE, 404, code="not_found")
    return resource
