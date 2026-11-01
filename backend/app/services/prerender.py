"""AI Search / GEO Phase 1B — visible, semantic HTML for a published
Article's or Person's own public content, placed INSIDE the SPA's
`<div id="root">` (see spa_shell.py's `_set_root_prerender`).

Why inside #root: main.jsx mounts with `createRoot(...).render(...)` (no
hydration), and React replaces the root's existing children on its first
commit — so this markup is the page's real first paint and no-JS reading
experience, then React takes over; there is never a second, permanent
copy of the content anywhere in the document. Every visitor gets the
same HTML (no User-Agent branch anywhere), and nothing here is hidden.

Content comes only from the same records React displays (Article.content
/ Person.bio plus the visible header fields). Block HTML is re-sanitized
through content_blocks.sanitize_content_blocks() — the SAME sanitizer
every save already runs (defense in depth, never a second, looser
allow-list) — and every plain-text field is HTML-escaped here.

CSS classes are copied verbatim from existing React source
(ArticleContent.jsx / PersonProfilePage.jsx) so Tailwind has already
generated them; a class only ever written in this Python file would not
exist in the build.
"""
from datetime import datetime
from html import escape

from app.services.content_blocks import sanitize_content_blocks

# --- class names (each one already present in the React source) ---------
_MAIN_CLASS = "container-editorial py-10"
_ARTICLE_CLASS = "max-w-reading"
_H1_CLASS = "font-serif text-4xl font-semibold text-charcoal sm:text-5xl"
_DECK_CLASS = "mt-2 text-lg text-charcoal-600"
_META_CLASS = "mt-1 text-sm text-charcoal-600"
_HEADING_CLASSES = {
    2: "mt-10 font-serif font-semibold text-charcoal text-2xl sm:text-3xl",
    3: "mt-10 font-serif font-semibold text-charcoal text-xl sm:text-2xl",
    4: "mt-10 font-serif font-semibold text-charcoal text-lg sm:text-xl",
}
_PARAGRAPH_CLASS = "mt-5 font-sans text-lg leading-[1.85] text-charcoal-600"
_LIST_CLASS = "mt-5 space-y-2 pl-5 font-sans text-lg leading-relaxed text-charcoal-600"
_QUOTE_CLASS = "my-8 border-l-2 border-burgundy-500 pl-6"
_QUOTE_TEXT_CLASS = "font-serif text-xl italic leading-snug text-charcoal"
_CITE_CLASS = "mt-2 block font-sans text-sm not-italic text-charcoal-600"
_CALLOUT_CLASS = "my-8 border border-taupe-200 bg-cream p-6"
_CALLOUT_TEXT_CLASS = "font-serif text-lg leading-relaxed text-charcoal"
_CALLOUT_LIST_CLASS = "mt-3 space-y-1.5 pl-5 font-sans text-base leading-relaxed text-charcoal"
_HR_CLASS = "my-10 border-t border-taupe-300"
_FIGURE_CLASS = "my-10"
_FIGCAPTION_CLASS = "mt-2 text-sm text-charcoal-600"
_TABLE_WRAP_CLASS = "my-8 overflow-x-auto"
_TABLE_CLASS = "w-full border-collapse text-left text-sm"
_TH_CLASS = "py-2 pr-4 font-semibold text-charcoal"
_TD_CLASS = "py-2 pr-4 text-charcoal-600"
_FAQ_CLASS = "my-8 space-y-5"
_FAQ_Q_CLASS = "font-serif text-lg font-semibold text-charcoal"
_FAQ_A_CLASS = "mt-1 text-base text-charcoal-600"
_SECTION_H2_CLASS = "mt-10 font-serif text-2xl font-semibold text-charcoal"
_SHORT_BIO_CLASS = "mt-4 max-w-2xl font-serif text-lg leading-relaxed text-charcoal sm:text-xl"
_PROFESSION_CLASS = "mt-1 text-sm font-semibold uppercase tracking-wide text-charcoal-600/80"
_CHIPS_CLASS = "mt-4 flex flex-wrap gap-2"
_CHIP_CLASS = "bg-taupe-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600"
_FEATURED_QUOTE_CLASS = "border-y border-taupe-200 py-8 text-center"
_FEATURED_QUOTE_TEXT_CLASS = "font-serif text-2xl font-medium italic text-charcoal"
_PLAIN_LIST_CLASS = "mt-4 list-disc space-y-2 pl-5 text-base text-charcoal-600"
_TIMELINE_CLASS = "mt-5 space-y-5 border-l border-taupe-300 pl-6"
_TIMELINE_YEAR_CLASS = "text-sm font-semibold uppercase tracking-wide text-burgundy-600"
_TIMELINE_TITLE_CLASS = "mt-0.5 text-base text-charcoal"
_LINK_CLASS = "font-medium text-burgundy-600 hover:underline"


def _text(value):
    """A plain-text field: always escaped, never trusted as markup."""
    return escape(str(value), quote=True) if value not in (None, "") else ""


def _attr(value):
    return escape(str(value), quote=True)


def _is_nonblank(value):
    return isinstance(value, str) and value.strip() != ""


def _inline(value):
    """An inline-HTML field that sanitize_content_blocks() has just
    re-cleaned (b/strong/i/em/u/a/br only, http/https/mailto links only).
    Non-strings are never emitted.
    """
    return value if isinstance(value, str) else ""


def _list_html(tag, items, list_class):
    rows = "".join(f"<li>{_inline(item)}</li>" for item in items if _is_nonblank(item))
    if not rows:
        return ""
    marker = "list-decimal" if tag == "ol" else "list-disc"
    return f'<{tag} class="{list_class} {marker}">{rows}</{tag}>'


def _safe_media_url(media, fallback_path=None):
    """Only a public media URL (Media.public_url's own "/media/..." shape,
    or an absolute http(s) URL) — never a filesystem path."""
    candidates = []
    if isinstance(media, dict):
        candidates += [media.get("mediaPath"), media.get("public_url"), media.get("url")]
    candidates.append(fallback_path)
    for value in candidates:
        if isinstance(value, str) and (value.startswith("/media/") or value.startswith("https://") or value.startswith("http://")):
            return value
    return None


def _render_block(block):
    kind = block.get("type")
    if kind == "heading":
        if not _is_nonblank(block.get("text")):
            return ""
        level = block.get("level") if block.get("level") in (2, 3, 4) else 2
        return f'<h{level} class="{_HEADING_CLASSES[level]}">{_text(block["text"])}</h{level}>'
    if kind == "paragraph":
        return f'<p class="{_PARAGRAPH_CLASS}">{_inline(block.get("text"))}</p>' if _is_nonblank(block.get("text")) else ""
    if kind == "list":
        items = block.get("items") if isinstance(block.get("items"), list) else []
        return _list_html("ol" if block.get("style") == "number" else "ul", items, _LIST_CLASS)
    if kind in ("blockquote", "pullquote"):
        if not _is_nonblank(block.get("text")):
            return ""
        cite = f'<cite class="{_CITE_CLASS}">{_text(block["attribution"])}</cite>' if _is_nonblank(block.get("attribution")) else ""
        return f'<blockquote class="{_QUOTE_CLASS}"><p class="{_QUOTE_TEXT_CLASS}">{_inline(block["text"])}</p>{cite}</blockquote>'
    if kind == "highlight":
        parts = []
        if _is_nonblank(block.get("title")):
            parts.append(f'<p class="eyebrow mb-2">{_text(block["title"])}</p>')
        if _is_nonblank(block.get("text")):
            parts.append(f'<p class="{_CALLOUT_TEXT_CLASS}">{_inline(block["text"])}</p>')
        style = block.get("listStyle")
        if style in ("bullet", "number") and isinstance(block.get("items"), list):
            parts.append(_list_html("ol" if style == "number" else "ul", block["items"], _CALLOUT_LIST_CLASS))
        body = "".join(parts)
        return f'<aside class="{_CALLOUT_CLASS}">{body}</aside>' if body else ""
    if kind == "divider":
        return f'<hr class="{_HR_CLASS}">'
    if kind == "image":
        url = _safe_media_url(block.get("media"), block.get("mediaPath"))
        if not url:
            return ""
        alt = "" if block.get("decorative") is True else (block.get("alt") or "")
        caption_parts = []
        if _is_nonblank(block.get("caption")):
            caption_parts.append(_text(block["caption"]))
        if _is_nonblank(block.get("credit")):
            caption_parts.append(f"— {_text(block['credit'])}")
        caption = f'<figcaption class="{_FIGCAPTION_CLASS}">{" ".join(caption_parts)}</figcaption>' if caption_parts else ""
        return (
            f'<figure class="{_FIGURE_CLASS}"><img src="{_attr(url)}" alt="{_attr(alt)}" loading="lazy" '
            f'decoding="async" class="w-full">{caption}</figure>'
        )
    if kind == "table":
        headers = block.get("headers") if isinstance(block.get("headers"), list) else []
        rows = block.get("rows") if isinstance(block.get("rows"), list) else []
        head = "".join(f'<th class="{_TH_CLASS}">{_text(h)}</th>' for h in headers)
        body = "".join(
            "<tr>" + "".join(f'<td class="{_TD_CLASS}">{_text(cell)}</td>' for cell in row) + "</tr>"
            for row in rows
            if isinstance(row, list)
        )
        if not head and not body:
            return ""
        thead = f"<thead><tr>{head}</tr></thead>" if head else ""
        return f'<div class="{_TABLE_WRAP_CLASS}"><table class="{_TABLE_CLASS}">{thead}<tbody>{body}</tbody></table></div>'
    if kind == "faq":
        items = block.get("items") if isinstance(block.get("items"), list) else []
        entries = "".join(
            f'<div><h3 class="{_FAQ_Q_CLASS}">{_text(item.get("q"))}</h3><p class="{_FAQ_A_CLASS}">{_text(item.get("a"))}</p></div>'
            for item in items
            if isinstance(item, dict) and _is_nonblank(item.get("q"))
        )
        return f'<section class="{_FAQ_CLASS}">{entries}</section>' if entries else ""
    # newsletterCta / ad / sponsorBlock / button / relatedBlock /
    # articleCard / footerNote / anything unknown: application or
    # interactive blocks React alone renders — never guessed at here.
    return ""


def render_content_blocks(blocks):
    return "".join(_render_block(block) for block in sanitize_content_blocks(blocks))


def _format_date(value):
    """formatDate()'s en-US "Month D, YYYY" (utils/format.js)."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None, None
    if not isinstance(value, datetime):
        return None, None
    return value.isoformat(), f"{value.strftime('%B')} {value.day}, {value.year}"


def _author_link(author):
    if not isinstance(author, dict) or not _is_nonblank(author.get("name")):
        return ""
    if _is_nonblank(author.get("slug")):
        return f'<a href="/authors/{_attr(author["slug"])}" class="{_LINK_CLASS}">{_text(author["name"])}</a>'
    return _text(author["name"])


def _sponsor_disclosure(payload):
    """Same disclosure ArticlePage.jsx shows above the byline for a
    sponsored article — never omitted from the no-JS reading view."""
    if not payload.get("is_sponsored"):
        return ""
    record = payload.get("sponsorRecord")
    sponsor = payload.get("sponsor") if isinstance(payload.get("sponsor"), dict) else None
    if isinstance(record, dict):
        label = record.get("disclosure_label") or "Sponsored"
        name = record.get("publicName") or (record.get("organization") or {}).get("name")
    elif sponsor:
        label, name = "Sponsored", sponsor.get("disclosure")
    else:
        return ""
    return f'<p class="{_META_CLASS}">{_text(label)} {_text(name or "")}</p>'


def render_article_prerender(payload):
    """`payload` is the same public_article_schema() dump the Article
    bootstrap embeds — so the prerender can only ever show what the
    public Article API already exposes."""
    header = [f'<h1 class="{_H1_CLASS}">{_text(payload.get("title"))}</h1>']
    if _is_nonblank(payload.get("subtitle")):
        header.append(f'<p class="{_DECK_CLASS}">{_text(payload["subtitle"])}</p>')
    header.append(_sponsor_disclosure(payload))
    names = [link for link in [_author_link(payload.get("author"))] + [_author_link(a) for a in payload.get("co_authors") or []] if link]
    if names:
        header.append(f'<p class="{_META_CLASS}">By {" &amp; ".join(names)}</p>')
    iso, label = _format_date(payload.get("publish_date"))
    if iso:
        header.append(f'<p class="{_META_CLASS}"><time datetime="{_attr(iso)}">{_text(label)}</time></p>')
    body = render_content_blocks(payload.get("content") or [])
    return (
        f'<main data-wsf-prerender="article" class="{_MAIN_CLASS}"><article class="{_ARTICLE_CLASS}">'
        f'<header>{"".join(header)}</header><section>{body}</section></article></main>'
    )


def _normalize_label(value):
    return " ".join((value or "").split()).lower()


def render_person_prerender(person):
    """`person` is the published Person ORM row; only fields
    PersonProfilePage.jsx shows publicly are read, and its Organization
    only when that Organization is itself published (the same rule as
    PersonSchema.get_organization)."""
    org = person.organization if person.organization is not None and person.organization.status == "published" else None
    header = [f'<h1 class="{_H1_CLASS}">{_text(person.name)}'
              + (f' <span class="text-xl font-normal text-charcoal-600/60">({_text(person.pronouns)})</span>' if _is_nonblank(person.pronouns) else "")
              + "</h1>"]
    role_parts = []
    if _is_nonblank(person.title):
        role_parts.append(_text(person.title))
    if org is not None:
        org_html = f'<a href="/organizations/{_attr(org.slug)}" class="{_LINK_CLASS}">{_text(org.name)}</a>'
        role_parts.append(("at " if role_parts else "") + org_html)
    if role_parts:
        header.append(f'<p class="{_DECK_CLASS}">{" ".join(role_parts)}</p>')
    if _is_nonblank(person.profession) and _normalize_label(person.profession) != _normalize_label(person.title):
        header.append(f'<p class="{_PROFESSION_CLASS}">{_text(person.profession)}</p>')
    place = " · ".join(_text(v) for v in (person.location, person.industry) if _is_nonblank(v))
    if place:
        header.append(f'<p class="{_META_CLASS}">{place}</p>')
    if _is_nonblank(person.short_bio):
        header.append(f'<p class="{_SHORT_BIO_CLASS}">{_text(person.short_bio)}</p>')
    expertise = [e for e in (person.expertise or []) if _is_nonblank(e)]
    if expertise:
        chips = "".join(f'<li class="{_CHIP_CLASS}">{_text(e)}</li>' for e in expertise)
        header.append(f'<ul class="{_CHIPS_CLASS}" aria-label="Expertise">{chips}</ul>')

    sections = []
    if _is_nonblank(person.featured_quote):
        sections.append(
            f'<blockquote class="{_FEATURED_QUOTE_CLASS}"><p class="{_FEATURED_QUOTE_TEXT_CLASS}">{_text(person.featured_quote)}</p></blockquote>'
        )
    bio = render_content_blocks(person.bio or [])
    if bio:
        sections.append(f'<section><h2 class="{_SECTION_H2_CLASS}">About</h2>{bio}</section>')
    timeline = [t for t in (person.career_timeline or []) if isinstance(t, dict) and (t.get("year") or t.get("title"))]
    if timeline:
        rows = "".join(
            f'<li><p class="{_TIMELINE_YEAR_CLASS}">{_text(t.get("year"))}</p><p class="{_TIMELINE_TITLE_CLASS}">{_text(t.get("title"))}</p></li>'
            for t in timeline
        )
        sections.append(f'<section><h2 class="{_SECTION_H2_CLASS}">Career Timeline</h2><ol class="{_TIMELINE_CLASS}">{rows}</ol></section>')
    for heading, values in (("Achievements", person.achievements), ("Awards", person.awards)):
        items = [v for v in (values or []) if _is_nonblank(v)]
        if items:
            rows = "".join(f"<li>{_text(v)}</li>" for v in items)
            sections.append(f'<section><h2 class="{_SECTION_H2_CLASS}">{heading}</h2><ul class="{_PLAIN_LIST_CLASS}">{rows}</ul></section>')

    return (
        f'<main data-wsf-prerender="person" class="{_MAIN_CLASS}"><article class="{_ARTICLE_CLASS}">'
        f'<header>{"".join(header)}</header>{"".join(sections)}</article></main>'
    )
