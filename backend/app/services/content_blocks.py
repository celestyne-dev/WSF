"""Sanitizes the free-text fields inside an Article.content block list
before it's persisted. The CMS block editor lets an editor apply bold/
italic/links inside paragraphs, list items, and quotes — stored as a small
allow-listed HTML fragment per field, never arbitrary HTML — so this is the
one place that guarantees nothing unsafe (script tags, event handlers,
javascript: links) reaches the database or a reader's browser.

Block types outside the known editorial set (e.g. newsletterCta,
sponsorBlock, ad, table, faq — rendered by ArticleContent.jsx but not
produced by the block editor) are passed through unchanged; they're either
structural (no free text) or out of this editor's scope. The editor-made
`button`, `cta` and `relatedBlock` blocks ARE sanitized here: their URLs
may only be a safe internal path or an http(s) URL (never javascript:,
data: or anything else), and their text is plain text.
"""
import html
import re

import bleach

_INLINE_TAGS = ["b", "strong", "i", "em", "u", "a", "br"]
_INLINE_ATTRS = {"a": ["href", "target", "rel"]}
_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

# Fields allowed limited inline formatting (bold/italic/links).
_INLINE_TEXT_FIELDS = {
    "paragraph": ("text",),
    "blockquote": ("text",),
    "pullquote": ("text",),
    "highlight": ("text",),
}
# Fields stripped to plain text — no inline formatting expected.
_PLAIN_TEXT_FIELDS = {
    "heading": ("text",),
    "image": ("alt", "caption", "credit"),
    "blockquote": ("attribution",),
    "pullquote": ("attribution",),
}


def _clean_inline_html(value):
    if not isinstance(value, str):
        return value
    return bleach.clean(value, tags=_INLINE_TAGS, attributes=_INLINE_ATTRS, protocols=_ALLOWED_PROTOCOLS, strip=True).strip()


def _clean_plain_text(value):
    if not isinstance(value, str):
        return value
    return bleach.clean(value, tags=[], attributes={}, strip=True).strip()


# A Callout (highlight) may carry an optional list below its text —
# {listStyle: "bullet"|"number"|None, items: [str, ...]}. "none"/""/any
# unknown value all normalize to None (no list shown) while the items are
# kept, so an editor toggling "No list" and back doesn't lose them.
_CALLOUT_LIST_STYLES = ("bullet", "number")


# The Callout title is rendered as a React text node (never as HTML), so
# it's stored as genuine plain text: tags stripped, and bleach's entity
# escaping undone so "Q&A" doesn't come back to the editor as "Q&amp;A".
def _clean_callout_title(value):
    if not isinstance(value, str):
        return value
    return html.unescape(_clean_plain_text(value))


def _normalize_callout_list(block):
    if "listStyle" in block:
        style = block["listStyle"]
        block["listStyle"] = style if style in _CALLOUT_LIST_STYLES else None
    if "items" in block:
        items = block["items"] if isinstance(block["items"], list) else []
        block["items"] = [_clean_inline_html(item) for item in items if isinstance(item, str)]


# Only Python's own real boolean True counts — a string like "false" or
# "0" is truthy in Python, so without this a client that sent decorative
# as text could mark every image decorative by accident (and silently
# bypass the publish-time alt-text requirement in articles.py).
def _as_bool(value):
    return value is True


def sanitize_content_blocks(blocks):
    if not isinstance(blocks, list):
        return []

    sanitized = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block = dict(block)
        block_type = block.get("type")

        for field in _INLINE_TEXT_FIELDS.get(block_type, ()):
            if field in block:
                block[field] = _clean_inline_html(block[field])
        for field in _PLAIN_TEXT_FIELDS.get(block_type, ()):
            if field in block:
                block[field] = _clean_plain_text(block[field])
        if block_type == "image" and "decorative" in block:
            block["decorative"] = _as_bool(block["decorative"])
        if block_type == "list":
            if isinstance(block.get("items"), list):
                block["items"] = [_clean_inline_html(item) for item in block["items"]]
            _normalize_list_numbering(block)
        if block_type == "cta":
            block = _sanitize_cta(block)
        if block_type == "button":
            block = _sanitize_button(block)
        if block_type == "relatedBlock":
            block = _sanitize_related_block(block)
        if block_type == "highlight":
            if "title" in block:
                block["title"] = _clean_callout_title(block["title"])
            _normalize_callout_list(block)

        sanitized.append(block)
    return sanitized


# --- Numbered lists -------------------------------------------------------
# Numbered List blocks may carry `numberingMode` ("continue" | "restart" |
# "custom") and, for "custom", `startNumber`. A list without the field
# (everything published before this existed) keeps starting at 1. The
# effective start of each list is DERIVED from the whole block list (never
# stored for "continue"), with the same rule as frontend/src/utils/
# listNumbering.js — both tested against tests/fixtures/
# list_numbering_cases.json.
NUMBERING_MODES = ("continue", "restart", "custom")
_MAX_START_NUMBER = 100000


def _is_blank_item(item):
    return not isinstance(item, str) or not item.strip()


def _custom_start(value):
    if isinstance(value, bool):
        return 1
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    else:
        return 1
    return number if 1 <= number <= _MAX_START_NUMBER else 1


def resolve_list_starts(blocks):
    """Resolved start number per block (None for anything that is not a
    rendered numbered list). See the module comment above."""
    last_end = 0
    starts = []
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict) or block.get("type") != "list" or block.get("style") != "number":
            starts.append(None)
            continue
        count = sum(1 for item in (block.get("items") or []) if not _is_blank_item(item))
        if count == 0:
            starts.append(None)
            continue
        mode = block.get("numberingMode")
        if mode == "continue":
            start = last_end + 1
        elif mode == "custom":
            start = _custom_start(block.get("startNumber"))
        else:
            start = 1
        last_end = start + count - 1
        starts.append(start)
    return starts


def _normalize_list_numbering(block):
    mode = block.get("numberingMode")
    if mode not in NUMBERING_MODES or block.get("style") != "number":
        block.pop("numberingMode", None)
        block.pop("startNumber", None)
        return
    if mode == "custom":
        block["startNumber"] = _custom_start(block.get("startNumber"))
    else:
        block.pop("startNumber", None)


# --- Links in CTA / button blocks -----------------------------------------
_INTERNAL_PATH_RE = re.compile(r"^/(?!/)[^\s\\<>\"']*$")
_EXTERNAL_URL_RE = re.compile(r"^https?://[^\s<>\"']+$", re.IGNORECASE)
_RESERVED_INTERNAL = ("/admin", "/api")


_MAILTO_RE = re.compile(r"^mailto:[^\s<>\"']+@[^\s<>\"']+$", re.IGNORECASE)


def safe_link_url(value, allow_mailto=False):
    """An internal WSF path ("/career-hub", "/topics/leadership?x=1#y") or an
    http(s) URL; anything else (javascript:, data:, protocol-relative "//",
    admin/API paths, control characters) becomes "". `allow_mailto` keeps
    the simple Button block's existing mailto: links (Newsletter) working."""
    if not isinstance(value, str):
        return ""
    url = value.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in url):
        return ""
    if allow_mailto and _MAILTO_RE.match(url):
        return url
    if _INTERNAL_PATH_RE.match(url):
        path = url.split("#")[0].split("?")[0].lower().rstrip("/")
        if any(path == p or path.startswith(p + "/") for p in _RESERVED_INTERNAL):
            return ""
        return url
    if _EXTERNAL_URL_RE.match(url):
        return url
    return ""


def _plain(value, limit):
    if not isinstance(value, str):
        return ""
    return html.unescape(_clean_plain_text(value))[:limit]


CTA_STYLES = ("soft", "outline", "strong")
CTA_ALIGNMENTS = ("left", "center")


def _sanitize_cta(block):
    return {
        "type": "cta",
        "eyebrow": _plain(block.get("eyebrow"), 80),
        "title": _plain(block.get("title"), 160),
        "text": _plain(block.get("text"), 600),
        "buttonLabel": _plain(block.get("buttonLabel"), 60),
        "buttonUrl": safe_link_url(block.get("buttonUrl")),
        "style": block.get("style") if block.get("style") in CTA_STYLES else "soft",
        "align": block.get("align") if block.get("align") in CTA_ALIGNMENTS else "left",
    }


def _sanitize_button(block):
    block["label"] = _plain(block.get("label"), 80)
    block["url"] = safe_link_url(block.get("url"), allow_mailto=True)
    if "external" in block:
        block["external"] = _as_bool(block["external"])
    return block


_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _sanitize_related_block(block):
    slugs = block.get("articleSlugs") if isinstance(block.get("articleSlugs"), list) else []
    clean = []
    for slug in slugs:
        if isinstance(slug, str) and _SLUG_RE.match(slug.strip()) and slug.strip() not in clean:
            clean.append(slug.strip())
    return {"type": "relatedBlock", "heading": _plain(block.get("heading"), 80), "articleSlugs": clean[:3]}
