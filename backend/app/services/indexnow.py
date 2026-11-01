"""AI Search / GEO Phase 2 — IndexNow freshness notifications.

IndexNow (https://www.indexnow.org) lets a site tell participating search
engines that specific URLs were added, changed, or removed. It is a
discovery hint only: an accepted submission (HTTP 200/202) never
guarantees a crawl, indexing, or ranking.

Design:
  - Completely inert unless INDEXNOW_ENABLED is true AND INDEXNOW_KEY is
    a valid key (8-128 letters/digits/dashes). Never generates a key.
  - Best effort, always: every public entry point here swallows its own
    failures, logs one concise warning (never the key, never keyLocation,
    never the payload), and returns a result. Callers invoke it only
    AFTER their own db.session.commit() succeeded, so a search-engine
    outage can never fail or roll back a CMS save/publish/delete.
  - Only public paths of PUBLIC_SITE_URL's own host are ever sent; admin/
    account/auth/checkout/unsubscribe/API/media/download paths and any
    URL with a query string or fragment are rejected (see _normalize_url).
  - Which entity URLs are public is decided by public_urls_for() below,
    which mirrors app/services/sitemap.py's own per-type rules (and
    reuses the same shared predicates) rather than inventing new ones.
  - No queue, no retries, no threads: one synchronous POST per batch with
    a short timeout. The sitemap remains the durable fallback.
"""
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import date
from urllib.parse import urlsplit

from flask import current_app

logger = logging.getLogger(__name__)

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
MAX_URLS_PER_REQUEST = 10_000
_KEY_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")

# First path segments (and exact paths) that are never public content —
# never submitted even if a caller mistakenly passes one.
_PRIVATE_PREFIXES = (
    "/admin", "/account", "/api", "/media", "/assets",
    "/login", "/register", "/forgot-password", "/reset-password", "/change-password",
    "/newsletter/unsubscribe", "/resources/checkout", "/circle/checkout", "/search",
)


def is_valid_indexnow_key(key):
    return isinstance(key, str) and bool(_KEY_RE.match(key))


def indexnow_config_problems(config):
    """Production-check helper: enabled + missing/malformed key is a hard
    configuration error; disabled is never a problem. Never echoes the
    key itself back.
    """
    if not config.get("INDEXNOW_ENABLED"):
        return []
    key = config.get("INDEXNOW_KEY")
    if not key:
        return ["INDEXNOW_KEY is not set (required when INDEXNOW_ENABLED=true)."]
    if not is_valid_indexnow_key(key):
        return ["INDEXNOW_KEY is malformed (8-128 characters; letters, digits and dashes only)."]
    return []


def active_indexnow_key():
    """The configured key when IndexNow is enabled and the key is valid,
    else None — the single gate both submissions and the /<key>.txt
    verification route use."""
    if not current_app.config.get("INDEXNOW_ENABLED"):
        return None
    key = current_app.config.get("INDEXNOW_KEY")
    return key if is_valid_indexnow_key(key) else None


def _site():
    parts = urlsplit(current_app.config.get("PUBLIC_SITE_URL") or "")
    return parts.scheme, parts.netloc


def _is_private_path(path):
    return any(path == p or path.startswith(p + "/") for p in _PRIVATE_PREFIXES)


def _normalize_url(value):
    """A relative public path ("/people/x") or an absolute URL on
    PUBLIC_SITE_URL's own scheme+host -> the absolute URL; anything else
    (another host, a query string/fragment, a private route) -> None."""
    if not isinstance(value, str) or not value.strip():
        return None
    scheme, host = _site()
    if not scheme or not host:
        return None
    parts = urlsplit(value.strip())
    if parts.scheme or parts.netloc:
        if parts.scheme != scheme or parts.netloc != host:
            return None
    if parts.query or parts.fragment or "?" in value or "#" in value:
        return None
    path = parts.path or "/"
    if not path.startswith("/") or _is_private_path(path):
        return None
    return f"{scheme}://{host}{path}"


def _post_json(url, payload, timeout):
    """The one outbound HTTP call (stdlib only). Returns the HTTP status
    code. Patched out in tests — never reaches the real API there."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https endpoint
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def submit_indexnow_urls(urls):
    """Submit `urls` (relative public paths preferred). Never raises.
    Returns {"submitted": n, "accepted": bool, "status": int|None,
    "skipped": reason|None}."""
    try:
        key = active_indexnow_key()
        if key is None:
            return {"submitted": 0, "accepted": False, "status": None, "skipped": "disabled"}

        normalized = []
        seen = set()
        for value in urls or []:
            url = _normalize_url(value)
            if url and url not in seen:
                seen.add(url)
                normalized.append(url)
        if not normalized:
            return {"submitted": 0, "accepted": False, "status": None, "skipped": "no_public_urls"}

        scheme, host = _site()
        timeout = float(current_app.config.get("INDEXNOW_TIMEOUT_SECONDS") or 3)
        accepted, last_status = True, None
        for start in range(0, len(normalized), MAX_URLS_PER_REQUEST):
            batch = normalized[start : start + MAX_URLS_PER_REQUEST]
            payload = {"host": host, "key": key, "keyLocation": f"{scheme}://{host}/{key}.txt", "urlList": batch}
            try:
                last_status = _post_json(INDEXNOW_ENDPOINT, payload, timeout)
            except Exception as exc:  # noqa: BLE001 - network/timeout: best effort only
                logger.warning("IndexNow submission failed (%s) for %d URL(s).", type(exc).__name__, len(batch))
                accepted, last_status = False, None
                continue
            if last_status not in (200, 202):
                logger.warning("IndexNow submission not accepted: HTTP %s for %d URL(s).", last_status, len(batch))
                accepted = False
        return {"submitted": len(normalized), "accepted": accepted, "status": last_status, "skipped": None}
    except Exception as exc:  # noqa: BLE001 - never let IndexNow break a caller
        logger.warning("IndexNow submission skipped after an unexpected %s.", type(exc).__name__)
        return {"submitted": 0, "accepted": False, "status": None, "skipped": "error"}


# --- public-URL registry (mirrors app/services/sitemap.py) ---------------


def _detail(prefix, parent=None):
    return lambda slug: (f"{prefix}/{slug}", parent)


def public_urls_for(entity):
    """{public path: parent listing path or None} for `entity` as it is
    RIGHT NOW — empty when it isn't publicly visible. One rule per type,
    each the same one sitemap.py (and the matching public API) uses."""
    from app.models.article import Article
    from app.models.cms import AdvertisePage
    from app.models.commerce import Product
    from app.models.community import CommunityPage
    from app.models.directory import DirectoryListing
    from app.models.learning import LearningProgram
    from app.models.newsletter import NewsletterIssue
    from app.models.opportunity import Event, Job, Opportunity
    from app.models.page import SYSTEM_PAGE_KEYS, Page
    from app.models.people import Author, Organization, Person
    from app.models.resource import Resource
    from app.models.taxonomy import Series, Topic
    from app.services.event_registrations import is_event_publicly_visible
    from app.services.job_access import is_job_publicly_visible

    if entity is None:
        return {}
    if isinstance(entity, Article):
        # No article index page exists — the article URL only.
        return {f"/{entity.slug}": None} if entity.status == "published" else {}
    if isinstance(entity, Person):
        return {f"/people/{entity.slug}": "/people"} if entity.status == "published" else {}
    if isinstance(entity, Author):
        return {f"/authors/{entity.slug}": "/authors"} if entity.status == "active" else {}
    if isinstance(entity, Topic):
        return {f"/topics/{entity.slug}": "/topics"} if entity.status == "published" else {}
    if isinstance(entity, Series):
        return {f"/series/{entity.slug}": "/series"} if entity.status == "published" else {}
    if isinstance(entity, Organization):
        if entity.status != "published":
            return {}
        urls = {f"/organizations/{entity.slug}": "/organizations"}
        # The directory profile lives at the Organization's slug and is
        # public only while both are published — so an Organization's own
        # publish/archive/slug change moves that URL too.
        listing = DirectoryListing.query.filter_by(organization_id=entity.id).first() if entity.id else None
        if listing is not None and listing.status == "published":
            urls[f"/directory/{entity.slug}"] = "/directory"
        return urls
    if isinstance(entity, DirectoryListing):
        org = entity.organization
        if entity.status == "published" and org is not None and org.status == "published":
            return {f"/directory/{org.slug}": "/directory"}
        return {}
    if isinstance(entity, Job):
        return {f"/jobs/{entity.slug}": "/jobs"} if is_job_publicly_visible(entity) else {}
    if isinstance(entity, Opportunity):
        visible = entity.status == "published" and (entity.expiry_date is None or entity.expiry_date >= date.today())
        return {f"/opportunities/{entity.slug}": "/opportunities"} if visible else {}
    if isinstance(entity, Event):
        return {f"/events/{entity.slug}": "/events"} if is_event_publicly_visible(entity) else {}
    if isinstance(entity, Resource):
        return {f"/resources/{entity.slug}": "/resources"} if entity.is_publicly_visible() else {}
    if isinstance(entity, LearningProgram):
        return {f"/learning/{entity.slug}": "/learning"} if entity.status == "published" else {}
    if isinstance(entity, NewsletterIssue):
        return {f"/newsletter/{entity.slug}": "/newsletter"} if entity.status == "sent" else {}
    if isinstance(entity, Product):
        return {f"/shop/{entity.slug}": "/shop"} if entity.status in ("active", "unavailable") else {}
    if isinstance(entity, Page):
        return {f"/{entity.key}": None} if entity.key in SYSTEM_PAGE_KEYS and entity.status == "published" else {}
    if isinstance(entity, AdvertisePage):
        return {"/advertise": None} if entity.status == "published" else {}
    if isinstance(entity, CommunityPage):
        return {"/community": None} if entity.status == "published" else {}
    return {}


def capture_public_urls(entity):
    """Snapshot before a mutation (None/new entity -> {}). Never raises."""
    try:
        return dict(public_urls_for(entity))
    except Exception:  # noqa: BLE001
        return {}


def notify_public_change(before, entity):
    """Call AFTER a successful commit. `before` is capture_public_urls()
    from before the change; `entity` is the saved row (None if deleted).

    Rules (per public URL):
      - public before and after (same path): an ordinary edit — submit
        that URL only.
      - newly public: submit it + its parent listing page (membership
        of that listing changed).
      - no longer public (archived/draft/deleted/slug moved away):
        submit the old URL + its parent listing page.
      - never public on either side (draft-only edits): nothing.
    A slug change on a public entity therefore submits old + new URLs
    (plus the parent once). Never raises.
    """
    try:
        after = public_urls_for(entity) if entity is not None else {}
        urls = []
        for path, parent in after.items():
            urls.append(path)
            if path not in before and parent:
                urls.append(parent)
        for path, parent in (before or {}).items():
            if path not in after:
                urls.append(path)
                if parent:
                    urls.append(parent)
        if not urls:
            return None
        return submit_indexnow_urls(urls)
    except Exception as exc:  # noqa: BLE001
        logger.warning("IndexNow change notification skipped after an unexpected %s.", type(exc).__name__)
        return None
