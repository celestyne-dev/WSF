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
        if block_type == "list" and isinstance(block.get("items"), list):
            block["items"] = [_clean_inline_html(item) for item in block["items"]]

        sanitized.append(block)
    return sanitized
