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
import os
import re
import secrets
import uuid as uuid_lib
import zipfile
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


def resolve_real_protected_path(protected_file_path):
    """Resolves `protected_file_path` against PROTECTED_MEDIA_ROOT using
    canonical, symlink-resolved filesystem paths (os.path.realpath on
    both sides), and returns the resolved absolute path only if it:

      1. passes the lexical is_safe_protected_path() check above;
      2. still resolves to somewhere inside the real PROTECTED_MEDIA_ROOT
         after symlinks are followed (a symlink stored inside the root
         but pointing outside it is rejected here — send_from_directory's
         own traversal guard is lexical-only and would not catch this);
      3. exists on disk as a regular file (not a directory, not a
         device/socket/etc).

    Returns None for any failure — this function never raises, so it
    can be used both to gate publish/schedule (a missing or escaping
    file should produce a normal 422, not a 500) and to gate the actual
    download stream (a 404-equivalent there).
    """
    if not is_safe_protected_path(protected_file_path):
        return None
    root = current_app.config["PROTECTED_MEDIA_ROOT"]
    real_root = os.path.realpath(root)
    real_candidate = os.path.realpath(os.path.join(real_root, protected_file_path))
    try:
        if os.path.commonpath([real_candidate, real_root]) != real_root:
            return None
    except ValueError:
        # Different drives on Windows, or an otherwise non-comparable pair.
        return None
    if not os.path.isfile(real_candidate):
        return None
    return real_candidate


def protected_file_exists(protected_file_path):
    """True only if `protected_file_path` resolves, via
    resolve_real_protected_path(), to an existing regular file inside
    PROTECTED_MEDIA_ROOT. Used at publish/schedule validation time so a
    typo'd or not-yet-uploaded filename can never go live — see
    app/api/v1/resources.py's _validate_publish().
    """
    return resolve_real_protected_path(protected_file_path) is not None


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


def resolve_download_target(raw_token):
    """Full redemption path for GET /resources/downloads/<token>: resolves
    the token (see resolve_download_token()) and then re-resolves the
    bound resource's protected_file_path against the real filesystem
    (see resolve_real_protected_path()) — rejecting a stale token whose
    file has since been removed, moved, or was ever a symlink escaping
    PROTECTED_MEDIA_ROOT. Returns (resource, real_absolute_path). Raises
    the same generic 404 ApiError as resolve_download_token() for every
    failure mode, so none are distinguishable to the caller.
    """
    resource = resolve_download_token(raw_token)
    real_path = resolve_real_protected_path(resource.protected_file_path)
    if real_path is None:
        raise ApiError(_GENERIC_INVALID_DOWNLOAD_MESSAGE, 404, code="not_found")
    return resource, real_path


# ---------------------------------------------------------------------------
# Protected Resource file upload (Module 13B) — lets staff upload a
# circle_only Resource's downloadable file directly from WSF Studio instead
# of placing it on the server by hand. Writes INTO the architecture above
# (same PROTECTED_MEDIA_ROOT, same is_safe_protected_path()/
# resolve_real_protected_path() containment); nothing here bypasses or
# re-derives either check. The browser never chooses a filesystem path —
# every accepted upload is stored under a fresh server-generated UUID
# filename; the client's own filename is kept only as sanitized display/
# download metadata (Resource.protected_original_filename), never as any
# part of the on-disk identity.
# ---------------------------------------------------------------------------

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

# Each OOXML format (docx/xlsx/pptx) is a ZIP container with a predictable
# minimal set of internal entries — checking for these (without ever
# extracting them to disk) is enough to tell a real Word/Excel/PowerPoint
# file apart from an arbitrary ZIP or a renamed file of a different OOXML
# type, using only the stdlib zipfile module (no new dependency).
_OOXML_REQUIRED_ENTRIES = {
    "docx": ("[Content_Types].xml", "word/document.xml"),
    "xlsx": ("[Content_Types].xml", "xl/workbook.xml"),
    "pptx": ("[Content_Types].xml", "ppt/presentation.xml"),
}

# Not a strict allowlist — real browsers/OSes report several legitimate
# MIME strings for the same document format, and some correctly report an
# OOXML file as generic application/zip. Used only to catch an obviously
# wrong value (see _mime_is_contradictory below), never to accept/reject
# on its own.
_EXPECTED_MIME_VALUES = {
    "pdf": {"application/pdf", "application/x-pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
    },
    "zip": {"application/zip", "application/x-zip-compressed", "application/x-zip"},
}
_CONTRADICTORY_MIME_PREFIXES = ("image/", "video/", "audio/", "text/", "font/")
_NEUTRAL_MIMES = {None, "", "application/octet-stream", "binary/octet-stream"}


def _extract_extension(filename):
    if not filename or "." not in filename:
        return None
    return filename.rsplit(".", 1)[-1].lower()


def _sanitize_original_filename(raw_filename, fallback):
    """Display/download metadata only — never used to build a filesystem
    path (save_protected_upload() below always generates the on-disk name
    itself, before this value is even looked at, so no client filename —
    however crafted — can ever influence where a file is written). Strips
    any directory component a path-like client filename might carry (e.g.
    "C:\\fakepath\\../../etc/passwd.pdf") down to its basename, then any
    control character (which could otherwise corrupt the Content-
    Disposition header on download). Unicode is otherwise preserved
    rather than stripped — unlike werkzeug.secure_filename(), which would
    mangle a legitimate non-ASCII name for no reason here, since this is
    never a real path.
    """
    if not raw_filename:
        return fallback
    name = raw_filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = _CONTROL_CHARS_RE.sub("", name).strip()
    name = name[:255]
    return name or fallback


def _mime_is_contradictory(ext, mime):
    """True only for a MIME type that is clearly, obviously wrong for
    `ext` (a different top-level media category entirely, e.g. image/png
    on a .pdf) — never a strict allowlist. application/octet-stream and
    similar "I don't know" values are always treated as neutral, matching
    real-world upload behavior across browsers/OSes.
    """
    if not mime:
        return False
    normalized = mime.split(";", 1)[0].strip().lower()
    if normalized in _NEUTRAL_MIMES or normalized in _EXPECTED_MIME_VALUES.get(ext, ()):
        return False
    return normalized.startswith(_CONTRADICTORY_MIME_PREFIXES)


def _looks_like_pdf(path):
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def _zip_entry_names(path):
    try:
        with zipfile.ZipFile(path) as zf:
            return set(zf.namelist())
    except zipfile.BadZipFile:
        return None


def _validate_protected_file_contents(path, ext):
    """Validates the temp file already written to disk actually is what
    its extension claims — never trusts the extension or the client's
    reported MIME alone. Returns True/False; never raises. ZIP contents
    are inspected via zipfile's in-memory directory listing only — never
    extracted to disk.
    """
    if ext == "pdf":
        return _looks_like_pdf(path)
    if ext == "zip":
        return zipfile.is_zipfile(path)
    if ext in _OOXML_REQUIRED_ENTRIES:
        if not zipfile.is_zipfile(path):
            return False
        names = _zip_entry_names(path)
        if names is None:
            return False
        return all(required in names for required in _OOXML_REQUIRED_ENTRIES[ext])
    return False


def save_protected_upload(file_storage):
    """Validates and stores an uploaded circle_only Resource file under
    PROTECTED_MEDIA_ROOT. Returns a dict of safe metadata only — never a
    filesystem path, never PROTECTED_MEDIA_ROOT's own value:

        {protected_file_path, protected_original_filename,
         file_format, file_size}

    `protected_file_path` is a fresh, server-generated, root-relative
    storage identity ("resource_<uuid>.<ext>") — never derived from the
    client's filename, so no client-controlled input can influence where
    the file is actually written. The temp-write-then-os.replace() below
    is atomic: a file that fails content validation is never visible
    under its final name, and resolve_real_protected_path() (used by
    every read path) would never resolve to a stray temp file anyway,
    since nothing ever stores a ".{uuid}.part" name on a Resource row.

    Raises ApiError for any rejected upload; any temp file written is
    always cleaned up before raising. Does not touch any Resource row —
    callers attach the returned protected_file_path to a Resource via the
    ordinary create/update flow.
    """
    if not file_storage or not file_storage.filename:
        raise ApiError("No file provided.", 400, code="no_file")

    allowed_extensions = current_app.config["ALLOWED_PROTECTED_RESOURCE_EXTENSIONS"]
    ext = _extract_extension(file_storage.filename)
    if ext not in allowed_extensions:
        raise ApiError(f"File type .{ext or ''} is not allowed.", 415, code="unsupported_media_type")

    # Same seek/tell size check MediaService.validate() already uses —
    # cheap (no read into memory) for the SpooledTemporaryFile/BytesIO
    # werkzeug already buffered the upload into.
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    max_size = current_app.config["MAX_PROTECTED_UPLOAD_SIZE"]
    if size > max_size:
        raise ApiError("File exceeds the maximum upload size.", 413, code="file_too_large")

    if _mime_is_contradictory(ext, file_storage.mimetype):
        raise ApiError("File content does not match its reported type.", 415, code="invalid_file")

    root = current_app.config["PROTECTED_MEDIA_ROOT"]
    os.makedirs(root, exist_ok=True)
    file_uuid = str(uuid_lib.uuid4())
    temp_path = os.path.join(root, f".{file_uuid}.part")
    final_name = f"resource_{file_uuid}.{ext}"
    final_path = os.path.join(root, final_name)

    # file_storage.save() streams to disk in chunks (same call
    # MediaService.save() already uses for the original image upload) —
    # never materializes the whole upload in memory at once.
    file_storage.save(temp_path)
    try:
        if not _validate_protected_file_contents(temp_path, ext):
            raise ApiError(
                "File content does not match its extension — the upload may be corrupted or mislabeled.",
                415,
                code="invalid_file",
            )
        os.replace(temp_path, final_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    original_filename = _sanitize_original_filename(file_storage.filename, fallback=final_name)

    return {
        "protected_file_path": final_name,
        "protected_original_filename": original_filename,
        "file_format": ext.upper(),
        "file_size": os.path.getsize(final_path),
    }
