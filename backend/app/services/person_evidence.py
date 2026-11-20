"""Claim-level evidence for People profiles — the ONE place the shapes of
Person.achievements / Person.awards / Person.career_timeline are decided.

All three stay JSON columns (no migration). Historical rows are plain
strings ("Appointed CEO in 2025") or {year, title} dicts and keep working:
every reader goes through the normalizers below, never through raw JSON.

    achievement  {text, date, sourceLabel, sourceUrl}
    award        {name, issuer, date, sourceLabel, sourceUrl}
    timeline     {year, title, organization, sourceLabel, sourceUrl}

A claim carries its OWN optional source (title + URL) rather than pointing
at an index in the profile's Sources & References list: an index silently
re-targets when an editor reorders or deletes a source, which would attach
evidence to the wrong claim. Sources & References stays the profile's full
bibliography; a claim's source is the specific evidence for that line.

Text is plain text (no markup); a source URL must be a public http(s)
address (the same rule as Sources & References). An invalid URL is a 422
naming the field and item — never silently dropped.
"""
import html

import bleach
from marshmallow import ValidationError

from app.schemas.sources import validate_public_http_url
from app.utils.responses import ApiError

MAX_ITEMS = 40


def _plain(value, limit):
    if not isinstance(value, str):
        return ""
    return html.unescape(bleach.clean(value, tags=[], attributes={}, strip=True)).strip()[:limit]


def _source(raw):
    return {"sourceLabel": _plain(raw.get("sourceLabel"), 200), "sourceUrl": (raw.get("sourceUrl") or "").strip() if isinstance(raw.get("sourceUrl"), str) else ""}


def normalize_achievement(raw):
    if isinstance(raw, str):
        return {"text": _plain(raw, 500), "date": "", "sourceLabel": "", "sourceUrl": ""}
    if not isinstance(raw, dict):
        return None
    return {"text": _plain(raw.get("text"), 500), "date": _plain(raw.get("date"), 40), **_source(raw)}


def normalize_award(raw):
    if isinstance(raw, str):
        return {"name": _plain(raw, 300), "issuer": "", "date": "", "sourceLabel": "", "sourceUrl": ""}
    if not isinstance(raw, dict):
        return None
    return {"name": _plain(raw.get("name"), 300), "issuer": _plain(raw.get("issuer"), 200), "date": _plain(raw.get("date"), 40), **_source(raw)}


def normalize_timeline(raw):
    if not isinstance(raw, dict):
        return None
    return {"year": _plain(str(raw.get("year") or ""), 40), "title": _plain(raw.get("title"), 300),
            "organization": _plain(raw.get("organization"), 200), **_source(raw)}


_KINDS = {
    "achievements": (normalize_achievement, "text", "Achievements"),
    "awards": (normalize_award, "name", "Awards"),
    "career_timeline": (normalize_timeline, "title", "Career Timeline"),
}


def public_entries(kind, values):
    """Normalized, non-empty entries for display (API, prerender, JSON-LD).
    A stored source URL that no longer passes the public-URL rule is not
    linked (its title still shows as plain text)."""
    normalize, primary, _ = _KINDS[kind]
    out = []
    for raw in (values or [])[:MAX_ITEMS]:
        entry = normalize(raw)
        if not entry or not (entry[primary] or (kind == "career_timeline" and entry["year"])):
            continue
        if entry["sourceUrl"]:
            try:
                validate_public_http_url(entry["sourceUrl"])
            except ValidationError:
                entry["sourceUrl"] = ""
        out.append(entry)
    return out


def clean_input(kind, values):
    """Validated list for storage. Blank rows are dropped; a source URL that
    isn't a public http(s) link is a clear 422 (field + item number)."""
    normalize, primary, label = _KINDS[kind]
    if values is None:
        return []
    if not isinstance(values, list):
        raise ApiError(f"{label} must be a list.", 422, code="validation_error")
    if len(values) > MAX_ITEMS:
        raise ApiError(f"{label}: at most {MAX_ITEMS} items.", 422, code="validation_error")
    cleaned = []
    for index, raw in enumerate(values, start=1):
        entry = normalize(raw)
        if entry is None:
            raise ApiError(f"{label}, item {index}: unrecognised format.", 422, code="validation_error")
        has_primary = bool(entry[primary] or (kind == "career_timeline" and entry["year"]))
        if not has_primary:
            if entry["sourceUrl"] or entry["sourceLabel"]:
                raise ApiError(f"{label}, item {index}: add the text this source supports.", 422, code="validation_error")
            continue
        if entry["sourceUrl"]:
            try:
                validate_public_http_url(entry["sourceUrl"])
            except ValidationError:
                raise ApiError(
                    f"{label}, item {index}: the source link must be a full public https:// address.",
                    422, code="validation_error",
                )
        cleaned.append(entry)
    return cleaned
