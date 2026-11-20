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
        if block_type in LEARNING_BLOCK_SANITIZERS:
            block = LEARNING_BLOCK_SANITIZERS[block_type](block)
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


_TAG_RE = re.compile(r"<[^>]*>")


def visible_text(value):
    """The reader-visible text of an inline-HTML field: tags removed,
    entities decoded, non-breaking spaces treated as spaces. Mirrors
    visibleText() in frontend/src/utils/listNumbering.js."""
    if not isinstance(value, str):
        return ""
    return html.unescape(_TAG_RE.sub("", value)).replace("\xa0", " ").strip()


def _is_blank_item(item):
    # Rich list items carry inline markup: "<strong></strong>" or "<br>" is
    # blank, "<a href=...>Source</a>" is not. Tags never count as content.
    return not visible_text(item)


_ASCII_DIGITS_RE = re.compile(r"^[0-9]+$")


def _custom_start(value):
    # Mirrors customStart() in frontend/src/utils/listNumbering.js: a whole
    # number (an integral float like 25.0 too — JSON can't tell them apart
    # in JS) or an ASCII digit string, within 1..100000; anything else is 1.
    if isinstance(value, bool):
        return 1
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str) and _ASCII_DIGITS_RE.match(value.strip()):
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


_A_TAG_RE = re.compile(r"<a\b([^>]*)>", re.IGNORECASE)
_HREF_RE = re.compile(r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
_EVENT_ATTR_RE = re.compile(r"<[a-z][^>]*\son[a-z]+\s*=", re.IGNORECASE)
_DANGEROUS_TAG_RE = re.compile(r"<\s*(script|iframe|object|embed|style)\b", re.IGNORECASE)
_BLOCK_NAMES = {"paragraph": "Paragraph", "list": "List", "blockquote": "Quote", "pullquote": "Pull quote",
                "highlight": "Callout", "faq": "FAQ", "keyTakeaways": "Key takeaways", "cta": "Call to action"}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def unsafe_inline_problem(text):
    """Why an inline-HTML string would lose something on save, or None.
    The sanitizer strips unsafe parts as a last line of defence; at save
    time the editor gets a clear error instead, so a link is never silently
    reduced to its text."""
    if "<" not in text:
        return None
    if _DANGEROUS_TAG_RE.search(text):
        return "contains a script or embedded element, which is not allowed."
    if _EVENT_ATTR_RE.search(text):
        return "contains an event attribute (on...=), which is not allowed."
    for attrs in _A_TAG_RE.findall(text):
        match = _HREF_RE.search(attrs)
        if not match:
            continue
        href = html.unescape(next(g for g in match.groups() if g is not None)).strip()
        if href.startswith("#") or safe_link_url(href, allow_mailto=True):
            continue
        shown = href if len(href) <= 60 else href[:57] + "..."
        return (f'has a link to "{shown}" that can\'t be published. Use a full https:// address, '
                "a mailto: address, or an internal path starting with /.")
    return None


def assert_safe_inline_content(blocks, label="Content"):
    """Save-time check for editor content blocks: raises a 422 naming the
    block (e.g. "Bio, block 2 (List): has a link to ...") instead of letting
    sanitize_content_blocks() silently drop an unsafe link or attribute."""
    from app.utils.responses import ApiError

    if not isinstance(blocks, list):
        return
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            continue
        for text in _strings(block):
            problem = unsafe_inline_problem(text)
            if problem:
                kind = _BLOCK_NAMES.get(block.get("type"), str(block.get("type") or "block").title())
                raise ApiError(f"{label}, block {index} ({kind}): {problem}", 422, code="validation_error")


def sanitize_editor_blocks(blocks, label="Content"):
    """Editor save path: reject unsafe inline content clearly, then sanitize."""
    assert_safe_inline_content(blocks, label)
    return sanitize_content_blocks(blocks)


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


# --- Learning blocks (lesson content) -------------------------------------
# Text-first lesson elements offered by the lesson editor only. Each is
# reduced to a fixed, plain shape: inline formatting only where a reader
# sees running text (Try this / Case study scenario / Key takeaways),
# plain text everywhere else, bounded list lengths, and safe links only.
# Knowledge-check answers (`correct`, `explanation`) are stored here but
# stripped before any lesson content leaves the server — see
# public_lesson_content() — and are only revealed per question by the
# answer-check endpoint after the learner has answered.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
KNOWLEDGE_CHECK_KINDS = ("single", "multiple", "true_false")
MAX_CHECK_QUESTIONS = 5
MAX_ASSESSMENT_QUESTIONS = 25
MAX_OPTIONS = 6


def _plain_list(values, limit, max_items):
    values = values if isinstance(values, list) else []
    out = [_plain(v, limit) for v in values if isinstance(v, str) and v.strip()]
    return out[:max_items]


def _inline_list(values, max_items):
    values = values if isinstance(values, list) else []
    out = [_clean_inline_html(v) for v in values if isinstance(v, str) and v.strip()]
    return out[:max_items]


def _stable_id(value, fallback):
    return value if isinstance(value, str) and _ID_RE.match(value) else fallback


def sanitize_question(question, index):
    """One knowledge-check / final-assessment question. Lenient (a draft
    may be incomplete) but never stores anything outside this shape."""
    q = question if isinstance(question, dict) else {}
    kind = q.get("kind") if q.get("kind") in KNOWLEDGE_CHECK_KINDS else "single"
    if kind == "true_false":
        raw = q.get("options") if isinstance(q.get("options"), list) else []
        true_correct = bool(raw and isinstance(raw[0], dict) and raw[0].get("correct") is True)
        options = [
            {"id": "true", "text": "True", "correct": true_correct},
            {"id": "false", "text": "False", "correct": not true_correct},
        ]
    else:
        options, seen = [], set()
        for i, option in enumerate((q.get("options") if isinstance(q.get("options"), list) else [])[:MAX_OPTIONS]):
            if not isinstance(option, dict):
                continue
            option_id = _stable_id(option.get("id"), f"o{i + 1}")
            if option_id in seen:
                option_id = f"o{i + 1}"
            seen.add(option_id)
            options.append({"id": option_id, "text": _plain(option.get("text"), 200), "correct": option.get("correct") is True})
        if kind == "single":
            # Exactly one correct answer: keep the first one marked.
            first = next((o for o in options if o["correct"]), None)
            for o in options:
                o["correct"] = o is first
    return {
        "id": _stable_id(q.get("id"), f"q{index + 1}"),
        "prompt": _plain(q.get("prompt"), 300),
        "kind": kind,
        "options": options,
        "explanation": _plain(q.get("explanation"), 600),
    }


def sanitize_questions(questions, max_questions):
    questions = questions if isinstance(questions, list) else []
    out, seen = [], set()
    for i, question in enumerate(questions[:max_questions]):
        clean = sanitize_question(question, i)
        if clean["id"] in seen:
            clean["id"] = f"q{i + 1}"
        seen.add(clean["id"])
        out.append(clean)
    return out


def _sanitize_key_takeaways(block):
    return {"type": "keyTakeaways", "title": _plain(block.get("title"), 80), "items": _inline_list(block.get("items"), 12)}


def _sanitize_try_this(block):
    return {"type": "tryThis", "title": _plain(block.get("title"), 80), "text": _clean_inline_html(block.get("text") or "")}


def _sanitize_reflection(block):
    return {"type": "reflection", "title": _plain(block.get("title"), 80), "prompts": _plain_list(block.get("prompts"), 300, 5)}


def _sanitize_case_study(block):
    return {
        "type": "caseStudy",
        "title": _plain(block.get("title"), 160),
        "text": _clean_inline_html(block.get("text") or ""),
        "questions": _plain_list(block.get("questions"), 300, 5),
    }


def _sanitize_checklist(block):
    return {"type": "checklist", "title": _plain(block.get("title"), 80), "items": _plain_list(block.get("items"), 200, 20)}


def _sanitize_knowledge_check(block):
    return {
        "type": "knowledgeCheck",
        "title": _plain(block.get("title"), 80),
        "questions": sanitize_questions(block.get("questions"), MAX_CHECK_QUESTIONS),
    }


def _sanitize_resource_link(block):
    slug = block.get("resourceSlug")
    slug = slug.strip() if isinstance(slug, str) else ""
    return {
        "type": "resourceLink",
        "resourceSlug": slug if _SLUG_RE.match(slug) else "",
        "label": _plain(block.get("label"), 120),
        "note": _plain(block.get("note"), 300),
    }


def _sanitize_further_reading(block):
    links = []
    for link in (block.get("links") if isinstance(block.get("links"), list) else [])[:8]:
        if not isinstance(link, dict):
            continue
        url = safe_link_url(link.get("url"))
        label = _plain(link.get("label"), 160)
        if url and label:
            links.append({"label": label, "url": url})
    return {"type": "furtherReading", "title": _plain(block.get("title"), 80), "links": links}


LEARNING_BLOCK_SANITIZERS = {
    "keyTakeaways": _sanitize_key_takeaways,
    "tryThis": _sanitize_try_this,
    "reflection": _sanitize_reflection,
    "caseStudy": _sanitize_case_study,
    "checklist": _sanitize_checklist,
    "knowledgeCheck": _sanitize_knowledge_check,
    "resourceLink": _sanitize_resource_link,
    "furtherReading": _sanitize_further_reading,
}


def public_question(question):
    """A question as a learner may see it BEFORE answering: no
    correct flags, no explanation."""
    return {
        "id": question.get("id"),
        "prompt": question.get("prompt"),
        "kind": question.get("kind"),
        "options": [{"id": o.get("id"), "text": o.get("text")} for o in question.get("options") or []],
    }


def public_lesson_content(blocks):
    """Lesson content safe to send to any client: knowledge-check answers
    removed. Every other block is returned unchanged."""
    if not isinstance(blocks, list):
        return []
    out = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "knowledgeCheck":
            block = {**block, "questions": [public_question(q) for q in block.get("questions") or [] if isinstance(q, dict)]}
        out.append(block)
    return out
