"""Business & Professional Directory service helpers — reference
generation, listing status-transition rules, and safe (never
auto-merging) duplicate-organization detection for public submissions.
See app/models/directory.py for the full field/lifecycle rationale.
"""
import re
from datetime import date
from urllib.parse import urlsplit

from app.models.directory import DirectorySubmission
from app.models.people import Organization

# A deliberately small, one-way-heavy lifecycle graph. "published" and
# "rejected" both fold back to "archived" only (a rejected listing can be
# reopened to "pending" for re-review, but never silently reappears
# published without going back through the review steps).
DIRECTORY_LISTING_STATUS_TRANSITIONS = {
    "pending": {"under_review", "approved", "rejected", "archived"},
    "under_review": {"approved", "rejected", "pending", "archived"},
    "approved": {"published", "under_review", "rejected", "archived"},
    "published": {"archived"},
    "rejected": {"pending", "archived"},
    "archived": {"pending"},
}


def is_valid_listing_status_transition(from_status, to_status):
    if from_status == to_status:
        return True
    return to_status in DIRECTORY_LISTING_STATUS_TRANSITIONS.get(from_status, set())


def generate_submission_reference(submission):
    """A human-friendly, unique, immutable submission reference — e.g.
    "WSF-DIR-2026-000123". Called once, right after the submission has been
    flushed and has an id (never count()+1 — a deleted row or a concurrent
    insert would collide). Same pattern as Order.reference/
    ContactInquiry.reference.
    """
    year = submission.created_at.year if submission.created_at else date.today().year
    return f"WSF-DIR-{year}-{submission.id:06d}"


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_business_name(name):
    """Lowercase, punctuation/whitespace-collapsed form used ONLY as a
    duplicate-detection signal — never displayed, never used to auto-merge
    records (see find_duplicate_organization's docstring).
    """
    if not name:
        return ""
    return _NON_ALNUM.sub(" ", name.lower()).strip()


def normalize_website_domain(url):
    """Extract a bare registrable-ish domain ("example.com") from a
    website URL for duplicate-detection matching — strips scheme, "www.",
    path/query/fragment, and port. Returns None for anything that isn't a
    plausible http(s) URL (this is a matching signal, not a validator —
    see app/schemas/directory.py for the actual safe-URL validation that
    rejects javascript:/data:/vbscript: schemes on write).
    """
    if not url:
        return None
    candidate = url.strip()
    if not re.match(r"^https?://", candidate, re.IGNORECASE):
        candidate = f"//{candidate}"
    try:
        host = urlsplit(candidate).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def find_duplicate_organization(business_name, website):
    """A same-name or same-domain candidate, surfaced to admins as a
    "possible duplicate" for a human decision — NEVER auto-merged and
    NEVER used to silently attach a submission to an existing Organization.
    See DirectorySubmission.possible_duplicate_organization_id.
    """
    domain = normalize_website_domain(website)
    if domain:
        candidates = Organization.query.filter(Organization.website.isnot(None)).all()
        for org in candidates:
            if normalize_website_domain(org.website) == domain:
                return org

    normalized_name = normalize_business_name(business_name)
    if normalized_name:
        for org in Organization.query.filter(Organization.name.isnot(None)).all():
            if normalize_business_name(org.name) == normalized_name:
                return org
    return None


def find_duplicate_submission(business_name, website, window_minutes=5):
    """Prevent an accidental double submission from repeated button clicks
    — an identical business name (and, if given, the same domain) within a
    short window is treated as the same click, not a second submission.
    Mirrors app/services/contact.py's _find_recent_duplicate pattern.
    """
    from datetime import datetime, timedelta, timezone

    normalized_name = normalize_business_name(business_name)
    domain = normalize_website_domain(website)
    window_start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    recent = DirectorySubmission.query.filter(
        DirectorySubmission.business_name_normalized == normalized_name,
        DirectorySubmission.created_at >= window_start,
    ).all()
    for submission in recent:
        if domain is None or submission.website_domain == domain:
            return submission
    return None
