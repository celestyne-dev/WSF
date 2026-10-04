"""Shared target-URL safety checks for any model field that stores an
admin-configured URL a visitor's browser will later be sent to (e.g.
Resource.file_url/external_url). http(s) is always allowed; a
root-relative path under this app's own MEDIA_URL prefix is also allowed
for a field that may represent this app's own served asset rather than
an off-site link (see app/models/resource.py's file_url docstring) —
never a raw filesystem path, never any other scheme
(javascript:/data:/file:), never a protocol-relative "//host/..." URL
(browsers resolve that as absolute/off-site, same risk as a bare scheme).
"""
from urllib.parse import urlparse

from flask import current_app

_SAFE_SCHEMES = {"http", "https"}


def is_safe_http_url(url):
    """True only for an absolute http(s) URL with a host."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in _SAFE_SCHEMES and bool(parsed.netloc)


def is_safe_media_path(url):
    """True only for a root-relative path under this app's own MEDIA_URL
    prefix (default "/media/", see config.py) — never protocol-relative
    ("//host/...") and never an arbitrary filesystem-looking path, since
    only this specific prefix is ever actually served publicly (see
    app/__init__.py's send_from_directory route).
    """
    if not url or url.startswith("//"):
        return False
    media_url = current_app.config.get("MEDIA_URL", "/media/")
    return url.startswith(media_url)


def is_safe_resource_target(url):
    """Resource.file_url may be either this app's own served asset or an
    http(s) URL (see that column's docstring) — never any other scheme,
    never a raw filesystem path like /var/www/....
    """
    return is_safe_http_url(url) or is_safe_media_path(url)
