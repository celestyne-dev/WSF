"""Sanitizes the free-text fields inside an Article.content block list
before it's persisted. The CMS block editor lets an editor apply bold/
italic/links inside paragraphs, list items, and quotes — stored as a small
allow-listed HTML fragment per field, never arbitrary HTML — so this is the
one place that guarantees nothing unsafe (script tags, event handlers,
javascript: links) reaches the database or a reader's browser.

Block types outside the known editorial set (e.g. newsletterCta,
relatedBlock, sponsorBlock, ad, button, table, faq — rendered by
ArticleContent.jsx but not produced by the block editor) are passed through
unchanged; they're either structural (no free text) or out of this
editor's scope.
"""
import html

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
        if block_type == "list" and isinstance(block.get("items"), list):
            block["items"] = [_clean_inline_html(item) for item in block["items"]]
        if block_type == "highlight":
            if "title" in block:
                block["title"] = _clean_callout_title(block["title"])
            _normalize_callout_list(block)

        sanitized.append(block)
    return sanitized
