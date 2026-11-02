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
_SOURCES_SECTION_CLASS = "mt-12 border-t border-taupe-200 pt-8"
_SOURCES_H2_CLASS = "font-serif text-xl font-semibold text-charcoal"
_SOURCES_LIST_CLASS = "mt-4 list-decimal space-y-3 pl-5 text-sm leading-relaxed text-charcoal-600"


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


def _safe_source_url(value):
    """Sources are validated as http(s) on save; re-checked here anyway."""
    return value if isinstance(value, str) and (value.startswith("https://") or value.startswith("http://")) else None


def render_article_sources(sources):
    """AI Search / GEO Phase 3A — the article's editor-entered sources as
    a visible "Sources & references" list (same data/order React shows)."""
    return render_source_references(sources, "article-sources")


def render_source_references(sources, section_id):
    """Shared by Article (3A) and Person/Author profiles (4A) — the same
    markup React's SourceReferences component renders, with that page's
    own section id. Every field is escaped plain text; links are ordinary
    crawlable anchors (editorial citations: no nofollow/sponsored/ugc)."""
    items = []
    for source in sources or []:
        if not isinstance(source, dict) or not _is_nonblank(source.get("title")):
            continue
        url = _safe_source_url(source.get("url"))
        title = _text(source["title"])
        parts = [
            f'<a href="{_attr(url)}" target="_blank" rel="noopener noreferrer" class="{_LINK_CLASS}">{title}</a>' if url else title
        ]
        meta = [_text(source[k]) for k in ("author", "publisher") if _is_nonblank(source.get(k))]
        iso, label = _format_date(source.get("publishedDate")) if _is_nonblank(source.get("publishedDate")) else (None, None)
        if iso:
            meta.append(f'<time datetime="{_attr(source["publishedDate"])}">{_text(label)}</time>')
        if meta:
            parts.append(f'<span class="block">{" · ".join(meta)}</span>')
        if _is_nonblank(source.get("note")):
            parts.append(f'<span class="block">{_text(source["note"])}</span>')
        items.append(f"<li>{''.join(parts)}</li>")
    if not items:
        return ""
    return (
        f'<section aria-labelledby="{_attr(section_id)}" class="{_SOURCES_SECTION_CLASS}">'
        f'<h2 id="{_attr(section_id)}" class="{_SOURCES_H2_CLASS}">Sources &amp; references</h2>'
        f'<ol class="{_SOURCES_LIST_CLASS}">{"".join(items)}</ol></section>'
    )


_CREDENTIALS_LIST_CLASS = "mt-4 space-y-4"
_CREDENTIAL_NAME_CLASS = "text-base font-semibold text-charcoal"
_CREDENTIAL_NOTE_CLASS = "mt-1 text-sm text-charcoal-600/80"


def render_credentials(credentials, section_id):
    """AI Search / GEO Phase 4B — a profile's editor-entered credentials &
    qualifications, the same markup React's CredentialsList renders (same
    order, same section id). Escaped plain text; a credential link only
    for an http(s) URL, as an ordinary crawlable anchor (no nofollow/
    sponsored/ugc). Never any verification wording: an entry records what
    the profile states, nothing more."""
    items = []
    for credential in credentials or []:
        if not isinstance(credential, dict) or not _is_nonblank(credential.get("name")):
            continue
        parts = [f'<p class="{_CREDENTIAL_NAME_CLASS}">{_text(credential["name"])}</p>']
        meta = [_text(credential[k]) for k in ("category", "issuer") if _is_nonblank(credential.get(k))]
        if meta:
            parts.append(f'<p class="{_META_CLASS}">{" · ".join(meta)}</p>')
        url = _safe_source_url(credential.get("url"))
        if url:
            parts.append(
                f'<p class="mt-1 text-sm"><a href="{_attr(url)}" target="_blank" rel="noopener noreferrer" '
                f'class="{_LINK_CLASS}">Credential details</a></p>'
            )
        if _is_nonblank(credential.get("note")):
            parts.append(f'<p class="{_CREDENTIAL_NOTE_CLASS}">{_text(credential["note"])}</p>')
        items.append(f"<li>{''.join(parts)}</li>")
    if not items:
        return ""
    return (
        f'<section aria-labelledby="{_attr(section_id)}">'
        f'<h2 id="{_attr(section_id)}" class="{_SECTION_H2_CLASS}">Credentials &amp; qualifications</h2>'
        f'<ul class="{_CREDENTIALS_LIST_CLASS}">{"".join(items)}</ul></section>'
    )


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
    sources = render_article_sources(payload.get("sources") or [])
    return (
        f'<main data-wsf-prerender="article" class="{_MAIN_CLASS}"><article class="{_ARTICLE_CLASS}">'
        f'<header>{"".join(header)}</header><section>{body}</section>{sources}</article></main>'
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
    # GEO Phase 4B — after the Career Timeline, before Achievements/Awards.
    sections.append(render_credentials(person.credentials or [], "person-credentials"))
    for heading, values in (("Achievements", person.achievements), ("Awards", person.awards)):
        items = [v for v in (values or []) if _is_nonblank(v)]
        if items:
            rows = "".join(f"<li>{_text(v)}</li>" for v in items)
            sections.append(f'<section><h2 class="{_SECTION_H2_CLASS}">{heading}</h2><ul class="{_PLAIN_LIST_CLASS}">{rows}</ul></section>')
    # GEO Phase 4A — after the biography/achievements/awards, as on the page.
    sections.append(render_source_references(person.sources or [], "person-sources"))

    return (
        f'<main data-wsf-prerender="person" class="{_MAIN_CLASS}"><article class="{_ARTICLE_CLASS}">'
        f'<header>{"".join(header)}</header>{"".join(sections)}</article></main>'
    )


# --- AI Search / GEO Phase 3B1: public entity detail pages -------------------
#
# Each renderer below takes the SAME anonymous public payload the matching
# public API detail endpoint returns to a signed-out visitor (built in
# spa_shell.py from that endpoint's own public builder with viewer=None) —
# so nothing can appear here that an anonymous API caller can't already
# read. Learning is the one exception: its public payload can carry the
# curriculum, so render_learning_prerender reads explicit catalog columns
# only and never touches modules/lessons. Plain-text fields are escaped;
# content-block fields go through render_content_blocks (re-sanitized);
# links are emitted only for http(s) URLs the public payload itself
# carries (a job's mailto only when the payload carries that email).

_SECTION_LIST_CLASS = "mt-4 list-disc space-y-2 pl-5 text-base text-charcoal-600"


def _humanize(value):
    """Stored enums are either display labels already ("Full-time",
    "On-site", "Fellowship") or snake_case ("self_paced") — only the
    latter needs touching: underscores -> spaces, first letter upper."""
    if not _is_nonblank(value):
        return ""
    text = value.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def _http_url(value):
    return value if isinstance(value, str) and (value.startswith("https://") or value.startswith("http://")) else None


def _section(heading, inner):
    if not inner:
        return ""
    return f'<section><h2 class="{_SECTION_H2_CLASS}">{_text(heading)}</h2>{inner}</section>'


def _string_list(values):
    items = [v for v in (values or []) if _is_nonblank(v)]
    if not items:
        return ""
    return f'<ul class="{_SECTION_LIST_CLASS}">{"".join(f"<li>{_text(v)}</li>" for v in items)}</ul>'


def _facts(pairs):
    """A short <dl> of label/value facts (already-escaped values)."""
    rows = "".join(f"<dt class=\"font-semibold text-charcoal\">{_text(label)}</dt><dd>{value}</dd>" for label, value in pairs if value)
    return f'<dl class="{_META_CLASS}">{rows}</dl>' if rows else ""


def _date_html(value):
    iso, label = _format_date(value) if _is_nonblank(value) else (None, None)
    return f'<time datetime="{_attr(value)}">{_text(label)}</time>' if iso else ""


def _external_link(url, label):
    url = _http_url(url)
    if not url:
        return ""
    return f'<p class="mt-4"><a href="{_attr(url)}" target="_blank" rel="noopener noreferrer" class="{_LINK_CLASS}">{_text(label)}</a></p>'


def _org_link(org):
    if not isinstance(org, dict) or not _is_nonblank(org.get("name")):
        return ""
    if _is_nonblank(org.get("slug")):
        return f'<a href="/organizations/{_attr(org["slug"])}" class="{_LINK_CLASS}">{_text(org["name"])}</a>'
    return _text(org["name"])


def _paragraph(value, cls=None):
    return f'<p class="{cls or _DECK_CLASS}">{_text(value)}</p>' if _is_nonblank(value) else ""


def _main(kind, header, body):
    return (
        f'<main data-wsf-prerender="{kind}" class="{_MAIN_CLASS}"><article class="{_ARTICLE_CLASS}">'
        f'<header>{"".join(header)}</header>{"".join(body)}</article></main>'
    )


def _h1(title):
    return f'<h1 class="{_H1_CLASS}">{_text(title)}</h1>'


def _salary(payload):
    low, high, currency = payload.get("salary_min"), payload.get("salary_max"), payload.get("currency") or ""
    if low is None and high is None:
        return ""
    amounts = " – ".join(f"{v:,}" for v in (low, high) if isinstance(v, int))
    period = f" per {_humanize(payload.get('salary_period')).lower()}" if _is_nonblank(payload.get("salary_period")) else ""
    return _text(f"{currency} {amounts}{period}".strip())


def render_job_prerender(payload):
    """`payload` = build_public_job_payload(job, None, detail=True)."""
    company = _org_link(payload.get("organization")) or _text(payload.get("company_name"))
    header = [_h1(payload.get("title"))]
    if company:
        header.append(f'<p class="{_DECK_CLASS}">{company}</p>')
    header.append(_facts([
        ("Location", _text(payload.get("location"))),
        ("Work mode", _text(_humanize(payload.get("work_mode")))),
        ("Employment type", _text(_humanize(payload.get("employment_type")))),
        ("Career level", _text(_humanize(payload.get("career_level")))),
        ("Industry", _text(payload.get("industry"))),
        ("Salary", _salary(payload) if payload.get("salary_visible") else ""),
        ("Apply by", _date_html(payload.get("deadline"))),
    ]))
    body = [
        _paragraph(payload.get("short_description"), _PARAGRAPH_CLASS),
        render_content_blocks(payload.get("description") or []),
        _section("Responsibilities", _string_list(payload.get("responsibilities"))),
        _section("Requirements", _string_list(payload.get("requirements"))),
        _section("Qualifications", _string_list(payload.get("qualifications"))),
        _section("Skills", _string_list(payload.get("skills"))),
        _section("Benefits", _string_list(payload.get("benefits"))),
    ]
    # Only present when the public builder itself attached it (public,
    # open, safe channel) — never for circle_only or closed jobs.
    if _http_url(payload.get("application_url")):
        body.append(_external_link(payload["application_url"], "Apply for this role"))
    elif _is_nonblank(payload.get("application_email")):
        email = payload["application_email"]
        body.append(f'<p class="mt-4"><a href="mailto:{_attr(email)}" class="{_LINK_CLASS}">Email your application</a></p>')
    return _main("job", header, body)


def render_opportunity_prerender(payload):
    """`payload` = build_public_opportunity_payload(opp, None, detail=True)."""
    provider = _org_link(payload.get("organization")) or _text(payload.get("organization_name"))
    header = [_h1(payload.get("title"))]
    if provider:
        header.append(f'<p class="{_DECK_CLASS}">{provider}</p>')
    funding = _text(payload.get("funding_value")) if _is_nonblank(payload.get("funding_value")) else ""
    header.append(_facts([
        ("Type", _text(_humanize(payload.get("type")))),
        ("Location", _text(payload.get("location"))),
        ("Career stage", _text(_humanize(payload.get("career_stage")))),
        ("Funding", funding),
        ("Opens", _date_html(payload.get("opening_date"))),
        ("Deadline", _date_html(payload.get("deadline"))),
    ]))
    eligibility = _paragraph(payload.get("eligibility"), _PARAGRAPH_CLASS) + _paragraph(payload.get("eligibility_notes"), _PARAGRAPH_CLASS)
    body = [
        _paragraph(payload.get("short_description"), _PARAGRAPH_CLASS),
        render_content_blocks(payload.get("description") or []),
        _section("Eligibility", eligibility),
        _external_link(payload.get("application_url"), "Apply now"),
    ]
    return _main("opportunity", header, body)


def render_event_prerender(payload):
    """`payload` = serialize_event_for_viewer(event, None) — virtual_link
    is withheld there for anonymous viewers and never read here anyway."""
    organizer = _org_link(payload.get("organizer")) or _text(payload.get("organizer_name"))
    header = [_h1(payload.get("title"))]
    if organizer:
        header.append(f'<p class="{_DECK_CLASS}">Hosted by {organizer}</p>')
    when = _date_html(payload.get("date"))
    if when and _is_nonblank(payload.get("end_date")) and payload.get("end_date") != payload.get("date"):
        when += f" – {_date_html(payload['end_date'])}"
    times = " – ".join(_text(str(t)[:5]) for t in (payload.get("start_time"), payload.get("end_time")) if t)
    place_parts = [_text(v) for v in (payload.get("venue"), payload.get("address"), payload.get("city")) if _is_nonblank(v)]
    place = f"<address class=\"not-italic\">{', '.join(place_parts)}</address>" if place_parts else ""
    if not place and payload.get("format") in ("virtual", "hybrid"):
        place = "Online"
    header.append(_facts([
        ("Date", when),
        ("Time", f"{times} {_text(payload.get('timezone') or '')}".strip() if times else ""),
        ("Format", _text(_humanize(payload.get("format")))),
        ("Where", place),
        ("Register by", _date_html(payload.get("registration_deadline"))),
    ]))
    agenda = "".join(
        f"<li>{_text(item.get('time') or '')}{' — ' if item.get('time') else ''}{_text(item.get('title') or '')}</li>"
        for item in (payload.get("agenda") or [])
        if isinstance(item, dict) and _is_nonblank(item.get("title"))
    )
    speakers = "".join(_speaker_item(s) for s in (payload.get("speakers") or []) if isinstance(s, dict))
    body = [
        _paragraph(payload.get("short_description"), _PARAGRAPH_CLASS),
        render_content_blocks(payload.get("description") or []),
        _section("Agenda", f'<ul class="{_SECTION_LIST_CLASS}">{agenda}</ul>' if agenda else ""),
        _section("Speakers", f'<ul class="{_SECTION_LIST_CLASS}">{speakers}</ul>' if speakers else ""),
    ]
    if not payload.get("is_past") and payload.get("status") not in ("cancelled", "postponed"):
        body.append(_external_link(payload.get("registration_url"), "Register"))
    return _main("event", header, body)


def _speaker_item(speaker):
    """Same fallbacks as frontend/src/api/events.js's mapSpeaker()."""
    person = speaker.get("person") if isinstance(speaker.get("person"), dict) else {}
    name = person.get("name") or speaker.get("name")
    if not _is_nonblank(name):
        return ""
    detail = [v for v in (person.get("title") or speaker.get("title"), speaker.get("organization_name")) if _is_nonblank(v)]
    return f"<li>{_text(name)}{' — ' + ' · '.join(_text(v) for v in detail) if detail else ''}</li>"


_RESOURCE_ACCESS_LABELS = {
    "direct_download": "Free download",
    "email_gate": "Free with email",
    "external_link": "Free",
    "member_only": "Free for members",
    "circle_only": "WSF Circle members",
    "premium": "Premium",
}


def render_resource_prerender(payload):
    """`payload` = build_public_resource_payload(resource, None) — never
    carries file_url/external_url/protected paths; only the catalog/
    marketing description an anonymous visitor already sees."""
    header = [_h1(payload.get("name"))]
    header.append(_paragraph(payload.get("subtitle")))
    author = payload.get("author") if isinstance(payload.get("author"), dict) else None
    by = (
        f'<a href="/authors/{_attr(author["slug"])}" class="{_LINK_CLASS}">{_text(author["name"])}</a>'
        if author and _is_nonblank(author.get("slug")) and _is_nonblank(author.get("name"))
        else _text(payload.get("authorName"))
    )
    price = ""
    if payload.get("accessType") == "premium" and isinstance(payload.get("price"), int):
        price = _text(f"{payload.get('currency') or ''} {payload['price']:,}".strip())
    topics = ", ".join(_text(t.get("name")) for t in (payload.get("topics") or []) if isinstance(t, dict) and _is_nonblank(t.get("name")))
    header.append(_facts([
        ("Type", _text(payload.get("type"))),
        ("By", by),
        ("Access", _text(_RESOURCE_ACCESS_LABELS.get(payload.get("accessType"), ""))),
        ("Price", price),
        ("Topics", topics),
    ]))
    body = [
        _paragraph(payload.get("shortDescription"), _PARAGRAPH_CLASS),
        render_content_blocks(payload.get("description") or []),
    ]
    return _main("resource", header, body)


def render_learning_prerender(program):
    """`program` is the published LearningProgram row. Public CATALOG
    columns only — modules, lessons, assessments, enrollment and the
    external/product delivery targets are never read here."""
    header = [_h1(program.title), _paragraph(program.subtitle)]
    instructor = program.primary_instructor
    by = (
        f'<a href="/authors/{_attr(instructor.slug)}" class="{_LINK_CLASS}">{_text(instructor.name)}</a>'
        if instructor is not None and instructor.status == "active"
        else ""
    )
    provider = program.provider_organization
    provider_html = _text(provider.name) if provider is not None and provider.status == "published" else ""
    duration = _text(f"{program.duration_value} {program.duration_unit or ''}".strip()) if program.duration_value else ""
    access = {"free": "Free", "circle_only": "WSF Circle members"}.get(program.access_type, "")
    header.append(_facts([
        ("Type", _text(_humanize(program.program_type))),
        ("Level", _text(_humanize(program.difficulty_level))),
        ("Instructor", by),
        ("Provided by", provider_html),
        ("Duration", duration),
        ("Format", _text(_humanize(program.delivery_mode))),
        ("Access", _text(access)),
    ]))
    body = [
        _paragraph(program.short_description, _PARAGRAPH_CLASS),
        render_content_blocks(program.overview or []),
        _section("What you'll learn", _string_list(program.learning_outcomes)),
        _section("Prerequisites", _string_list(program.prerequisites)),
    ]
    return _main("learning", header, body)


def render_organization_prerender(payload):
    """`payload` = OrganizationSchema().dump(org) — the same public dump
    the Organization detail API returns."""
    header = [_h1(payload.get("name")), _paragraph(payload.get("short_description"))]
    country = payload.get("country") if isinstance(payload.get("country"), dict) else {}
    location = ", ".join(_text(v) for v in (payload.get("location"), country.get("name")) if _is_nonblank(v))
    website = _http_url(payload.get("website"))
    header.append(_facts([
        ("Type", _text(_humanize(payload.get("org_type")))),
        ("Industry", _text(payload.get("industry"))),
        ("Location", location),
        ("Founded", _text(payload.get("founded_year")) if payload.get("founded_year") else ""),
        ("Website", f'<a href="{_attr(website)}" target="_blank" rel="noopener noreferrer" class="{_LINK_CLASS}">{_text(website)}</a>' if website else ""),
    ]))
    body = [render_content_blocks(payload.get("description") or [])]
    return _main("organization", header, body)


# --- AI Search / GEO Phase 3B2: secondary public detail pages ----------------
#
# Same contract as Phase 3B1: each renderer reads the anonymous public
# representation the matching public API returns (AuthorSchema,
# TopicSchema, SeriesSchema, DirectoryListingPublicSchema, the product
# API's _dump_product(..., can_view_all=False), NewsletterIssuePublicSchema)
# and shows only what that page visibly renders. No article/job grids —
# collections are Phase 3B3.


def _social_links(social):
    """Same handle -> URL patterns as AuthorProfilePage/PersonProfilePage."""
    social = social if isinstance(social, dict) else {}
    patterns = (("linkedin", "LinkedIn", "https://linkedin.com/in/{}"), ("twitter", "Twitter", "https://twitter.com/{}"),
                ("instagram", "Instagram", "https://instagram.com/{}"))
    return [(label, pattern.format(social[key])) for key, label, pattern in patterns if _is_nonblank(social.get(key))]


def _link_list(links):
    items = "".join(
        f'<li><a href="{_attr(url)}" target="_blank" rel="noopener noreferrer" class="{_LINK_CLASS}">{_text(label)}</a></li>'
        for label, url in links
        if _http_url(url)
    )
    return f'<ul class="{_CHIPS_CLASS}">{items}</ul>' if items else ""


def render_author_prerender(payload):
    """`payload` = the public Author payload (AuthorSchema dump + public
    filtering): `person` is null unless published, `topics` holds only
    published Topics."""
    header = [_h1(payload.get("name")), _paragraph(payload.get("role"))]
    country = payload.get("country") if isinstance(payload.get("country"), dict) else {}
    place = payload.get("location") or country.get("name")
    if _is_nonblank(place):
        header.append(f'<p class="{_META_CLASS}">{_text(place)}</p>')
    topics = [t for t in (payload.get("topics") or []) if isinstance(t, dict) and _is_nonblank(t.get("slug"))]
    if topics:
        chips = "".join(f'<li class="{_CHIP_CLASS}"><a href="/topics/{_attr(t["slug"])}">{_text(t.get("name"))}</a></li>' for t in topics)
        header.append(f'<ul class="{_CHIPS_CLASS}" aria-label="Topics">{chips}</ul>')
    links = ([("Website", payload.get("website"))] if _http_url(payload.get("website")) else []) + _social_links(payload.get("social"))
    header.append(_link_list(links))
    person = payload.get("person") if isinstance(payload.get("person"), dict) else None
    if person and _is_nonblank(person.get("slug")):
        header.append(f'<p class="mt-4"><a href="/people/{_attr(person["slug"])}" class="{_LINK_CLASS}">View profile</a></p>')
    body = [
        render_content_blocks(payload.get("bio") or []),
        render_credentials(payload.get("credentials") or [], "author-credentials"),
        render_source_references(payload.get("sources") or [], "author-sources"),
    ]
    return _main("author", header, body)


def render_topic_prerender(payload):
    """`payload` = TopicSchema().dump(topic)."""
    header = [f'<p class="eyebrow">Topic</p>', _h1(payload.get("name")), _paragraph(payload.get("description"))]
    return _main("topic", header, [])


def render_series_prerender(payload):
    """`payload` = SeriesSchema().dump(series). The public SeriesSchema
    never serializes sponsor_organization, so no sponsor is shown here
    either (the real page shows none from the live API)."""
    header = [f'<p class="eyebrow">Series</p>', _h1(payload.get("name")), _paragraph(payload.get("subtitle"))]
    body = [_paragraph(payload.get("description"), _PARAGRAPH_CLASS)]
    return _main("series", header, body)


_DIRECTORY_LISTING_TYPE_LABELS = {
    "business": "Business", "nonprofit": "Nonprofit", "professional_service": "Professional service",
    "social_enterprise": "Social enterprise", "association": "Professional association",
}
_DIRECTORY_OWNERSHIP_LABELS = {
    "women_owned": "Women-owned", "women_led": "Women-led", "women_founded": "Women-founded", "women_focused": "Women-focused",
}
_DIRECTORY_SERVICE_MODE_LABELS = {
    "local": "Local", "national": "National", "international": "International",
    "remote": "Remote", "online": "Online", "in_person": "In person",
}


def render_directory_prerender(payload):
    """`payload` = DirectoryListingPublicSchema().dump(listing) — excludes
    verification notes, rejection reasons, reviewer/verifier identity and
    all submitter data by construction. Labels mirror
    frontend/src/constants/directory.js."""
    org = payload.get("organization") if isinstance(payload.get("organization"), dict) else {}
    country = org.get("country") if isinstance(org.get("country"), dict) else {}
    place = ", ".join(_text(v) for v in (org.get("location"), country.get("name")) if _is_nonblank(v))
    meta = " · ".join(v for v in (_text(_DIRECTORY_LISTING_TYPE_LABELS.get(payload.get("listing_type"), "")), _text(org.get("industry")), place) if v)
    header = [_h1(org.get("name"))]
    if meta:
        header.append(f'<p class="{_META_CLASS}">{meta}</p>')
    if _http_url(org.get("website")):
        header.append(_external_link(org["website"], "Visit website"))
    badges = [_DIRECTORY_OWNERSHIP_LABELS.get(payload.get("ownership_classification"), "")]
    if payload.get("verification_status") == "verified":
        badges.append("Verified by WSF")
    badges += [c.get("name") for c in (payload.get("categories") or []) if isinstance(c, dict)]
    chips = "".join(f'<li class="{_CHIP_CLASS}">{_text(b)}</li>' for b in badges if _is_nonblank(b))
    if chips:
        header.append(f'<ul class="{_CHIPS_CLASS}">{chips}</ul>')
    modes = ", ".join(_DIRECTORY_SERVICE_MODE_LABELS.get(m, "") for m in (payload.get("service_modes") or []) if _DIRECTORY_SERVICE_MODE_LABELS.get(m))
    contact = []
    email = payload.get("public_contact_email")
    if _is_nonblank(email) and "@" in email:
        contact.append(f'<p><a href="mailto:{_attr(email)}" class="{_LINK_CLASS}">{_text(email)}</a></p>')
    if _is_nonblank(payload.get("public_contact_phone")):
        contact.append(_paragraph(payload["public_contact_phone"], _META_CLASS))
    body = [
        _paragraph(payload.get("service_summary"), _PARAGRAPH_CLASS),
        _section("Key services", _string_list(payload.get("key_services"))),
        _section("Service coverage", _paragraph(modes, _PARAGRAPH_CLASS) if modes else ""),
        _section("Contact", "".join(contact)),
    ]
    return _main("directory", header, body)


def _product_price(amount, currency):
    if not isinstance(amount, int):
        return ""
    if amount == 0:
        return "Free"
    return f"${amount:,.2f}" if currency == "USD" else f"{currency or 'KES'} {amount:,.2f}"


def render_product_prerender(payload):
    """`payload` = the product API's anonymous dump (_dump_product with
    can_view_all=False): price fields are already None when price_visible
    is False, and the nested `resource` is only {id, slug, name} — never
    a file/external URL, protected path or download token."""
    category = payload.get("category") if isinstance(payload.get("category"), dict) else {}
    eyebrow = category.get("name") or payload.get("type")
    header = [f'<p class="eyebrow">{_text(eyebrow)}</p>' if _is_nonblank(eyebrow) else "", _h1(payload.get("name"))]
    price, sale = payload.get("price"), payload.get("sale_price")
    on_sale = isinstance(sale, int) and isinstance(price, int) and sale < price
    shown = _product_price(sale if on_sale else price, payload.get("currency"))
    if shown:
        was = f' <s>{_text(_product_price(price, payload.get("currency")))}</s>' if on_sale else ""
        header.append(f'<p class="{_DECK_CLASS}">{_text(shown)}{was}</p>')
    available = bool(payload.get("is_available"))
    status_label = "Available" if available else ("No longer available" if payload.get("status") == "archived" else "Currently unavailable")
    header.append(f'<p class="{_META_CLASS}">{status_label}</p>')
    body = [_paragraph(payload.get("short_description"), _PARAGRAPH_CLASS), render_content_blocks(payload.get("description") or [])]
    if available and _http_url(payload.get("purchase_url")):
        body.append(_external_link(payload["purchase_url"], "Get it free" if payload.get("price") == 0 else "Buy now"))
    return _main("product", header, body)


def _render_newsletter_block(block, published_article_slugs):
    """The email-safe block types the archive page also renders
    (ArticleContent's articleCard/button/footerNote) — static display
    only: no merge fields, no unsubscribe placeholders, http(s) links
    only, and an article card links only to a still-published article."""
    from app.services.content_blocks import _clean_inline_html

    kind = block.get("type")
    if kind == "articleCard":
        if not _is_nonblank(block.get("title")):
            return ""
        title = _text(block["title"])
        slug = block.get("articleSlug")
        title_html = f'<a href="/{_attr(slug)}" class="{_LINK_CLASS}">{title}</a>' if slug in published_article_slugs else title
        excerpt = _paragraph(block.get("excerpt"), _META_CLASS)
        return f'<div class="my-8 border border-taupe-200 p-4"><p class="eyebrow">Read the story</p><p>{title_html}</p>{excerpt}</div>'
    if kind == "button":
        return _external_link(block.get("url"), block.get("label") or "Learn more") if _is_nonblank(block.get("label")) else ""
    if kind == "footerNote":
        text = _clean_inline_html(block.get("text")) if _is_nonblank(block.get("text")) else ""
        return f'<p class="mt-10 text-xs text-charcoal-600/70">{text}</p>' if text else ""
    return _render_block(block)


def render_newsletter_prerender(payload, published_article_slugs=frozenset()):
    """`payload` = NewsletterIssuePublicSchema().dump(issue) — subject,
    issue number, preheader, summary, content, cover, sent date only;
    never the internal title, status, audience filter, scheduling,
    provider/delivery metadata, or anything about subscribers."""
    number = payload.get("issue_number")
    header = [
        f'<p class="eyebrow">WSF Weekly #{_text(number)}</p>' if number else '<p class="eyebrow">WSF Weekly</p>',
        _h1(payload.get("subject")),
    ]
    sent = _date_html(payload.get("sent_at"))
    if sent:
        header.append(f'<p class="{_META_CLASS}">Sent {sent}</p>')
    blocks = sanitize_content_blocks(payload.get("content") or [])
    body = ["".join(_render_newsletter_block(b, published_article_slugs) for b in blocks)]
    return _main("newsletter", header, body)


# --- AI Search / GEO Phase 3B3: public hubs & listing pages ------------------
#
# Each hub = the page's own header copy (verbatim from its React page) +
# one small representative batch of public items (app/services/
# public_hubs.py — the same anonymous builders/schemas + public linked-
# entity filtering the public APIs use) as crawlable <a href> links.
# Exactly one H1 (the page title); items use H3 inside a section H2.

_HUB_ITEM_TITLE_CLASS = "font-serif text-lg font-semibold text-charcoal"
_HUB_LIST_CLASS = "mt-4 space-y-5"


def _hub_link(path, label):
    return f'<a href="{_attr(path)}" class="{_LINK_CLASS}">{_text(label)}</a>'


def _hub_item(path, title, meta_parts=(), summary=None):
    meta = " · ".join(p for p in meta_parts if p)
    return (
        f'<li><article><h3 class="{_HUB_ITEM_TITLE_CLASS}">{_hub_link(path, title)}</h3>'
        + (f'<p class="{_META_CLASS}">{meta}</p>' if meta else "")
        + (_paragraph(summary, _META_CLASS) if _is_nonblank(summary) else "")
        + "</article></li>"
    )


def _org_name(payload, *fallback_keys):
    org = payload.get("organization") if isinstance(payload.get("organization"), dict) else None
    if org and _is_nonblank(org.get("name")):
        return _text(org["name"])
    for key in fallback_keys:
        if _is_nonblank(payload.get(key)):
            return _text(payload[key])
    return ""


def _job_card(p):
    return _hub_item(f"/jobs/{p['slug']}", p.get("title"), (
        _text(p.get("company_name")), _text(p.get("location") or p.get("work_mode")),
        f"Apply by {_date_html(p['deadline'])}" if _is_nonblank(p.get("deadline")) else "",
    ), p.get("short_description"))


def _opportunity_card(p):
    return _hub_item(f"/opportunities/{p['slug']}", p.get("title"), (
        _org_name(p, "organization_name"), _text(p.get("type")),
        f"Deadline {_date_html(p['deadline'])}" if _is_nonblank(p.get("deadline")) else "",
    ), p.get("short_description"))


def _event_card(p):
    where = p.get("location") or p.get("city") or ("Online" if p.get("format") == "virtual" else None)
    return _hub_item(f"/events/{p['slug']}", p.get("title"), (
        _date_html(p.get("date")), _org_name(p, "organizer_name"), _text(where),
    ), p.get("short_description"))


def _resource_card(p):
    price = _text(f"{p.get('currency') or ''} {p['price']:,}".strip()) if p.get("accessType") == "premium" and isinstance(p.get("price"), int) else ""
    return _hub_item(f"/resources/{p['slug']}", p.get("name"), (
        _text(p.get("type")), _text(_RESOURCE_ACCESS_LABELS.get(p.get("accessType"), "")), price,
    ), p.get("shortDescription"))


def _learning_card(p):
    duration = f"{p['duration_value']} {p.get('duration_unit') or ''}".strip() if p.get("duration_value") else ""
    return _hub_item(f"/learning/{p['slug']}", p.get("title"), (
        _text(_humanize(p.get("program_type"))), _text(_humanize(p.get("difficulty_level"))),
        _text(duration), _text(_humanize(p.get("delivery_mode"))),
    ), p.get("short_description"))


def _person_card(p):
    return _hub_item(f"/people/{p['slug']}", p.get("name"), (_text(p.get("title")), _org_name(p), _text(p.get("location"))), p.get("short_bio"))


def _organization_card(p):
    return _hub_item(f"/organizations/{p['slug']}", p.get("name"), (
        _text(_humanize(p.get("org_type"))), _text(p.get("industry")), _text(p.get("location")),
    ), p.get("short_description"))


def _author_card(p):
    return _hub_item(f"/authors/{p['slug']}", p.get("name"), (_text(p.get("role")),), p.get("short_bio"))


def _topic_card(p):
    return _hub_item(f"/topics/{p['slug']}", p.get("name"), (), p.get("description"))


def _series_card(p):
    return _hub_item(f"/series/{p['slug']}", p.get("name"), (_text(p.get("subtitle")),), p.get("description"))


def _directory_card(p):
    org = p.get("organization") if isinstance(p.get("organization"), dict) else {}
    if not _is_nonblank(org.get("slug")):
        return ""
    categories = ", ".join(_text(c.get("name")) for c in (p.get("categories") or []) if isinstance(c, dict) and _is_nonblank(c.get("name")))
    return _hub_item(f"/directory/{org['slug']}", org.get("name"), (
        _text(_DIRECTORY_LISTING_TYPE_LABELS.get(p.get("listing_type"), "")),
        _text(_DIRECTORY_OWNERSHIP_LABELS.get(p.get("ownership_classification"), "")),
        _text(org.get("location")), categories,
    ), p.get("service_summary"))


def _product_card(p):
    category = p.get("category") if isinstance(p.get("category"), dict) else {}
    on_sale = isinstance(p.get("sale_price"), int) and isinstance(p.get("price"), int) and p["sale_price"] < p["price"]
    price = _product_price(p.get("sale_price") if on_sale else p.get("price"), p.get("currency"))
    availability = "Available" if p.get("is_available") else "Currently unavailable"
    return _hub_item(f"/shop/{p['slug']}", p.get("name"), (_text(category.get("name") or p.get("type")), _text(price), availability), p.get("short_description"))


def _newsletter_card(p):
    number = f"WSF Weekly #{_text(p['issue_number'])}" if p.get("issue_number") else ""
    sent = f"Sent {_date_html(p['sent_at'])}" if _is_nonblank(p.get("sent_at")) else ""
    return _hub_item(f"/newsletter/{p['slug']}", p.get("subject"), (number, sent), p.get("preheader") or p.get("summary"))


def _article_card(p):
    author = p.get("author") if isinstance(p.get("author"), dict) else {}
    return _hub_item(f"/{p['slug']}", p.get("title"), (_text(author.get("name")), _date_html(p.get("publish_date"))), p.get("excerpt"))


HUB_CARD_RENDERERS = {
    "jobs": _job_card, "opportunities": _opportunity_card, "events": _event_card, "resources": _resource_card,
    "learning": _learning_card, "people": _person_card, "organizations": _organization_card, "authors": _author_card,
    "topics": _topic_card, "series": _series_card, "directory": _directory_card, "shop": _product_card,
    "newsletter": _newsletter_card,
}


def _item_list(cards):
    cards = [c for c in cards if c]
    return f'<ul class="{_HUB_LIST_CLASS}">{"".join(cards)}</ul>' if cards else ""


def render_hub_prerender(marker, eyebrow, title, description, list_heading, kind, items, empty_text, extra_sections=()):
    """A hub/listing page: its own header copy, then one representative
    batch of public items (or a plain empty-state sentence — never a fake
    item)."""
    header = [f'<p class="eyebrow">{_text(eyebrow)}</p>' if _is_nonblank(eyebrow) else "", _h1(title), _paragraph(description)]
    body = list(extra_sections)
    if kind is not None:
        render = HUB_CARD_RENDERERS[kind]
        cards = _item_list(render(item) for item in items if isinstance(item, dict) and (_is_nonblank(item.get("slug")) or kind == "directory"))
        body.append(_section(list_heading, cards or _paragraph(empty_text, _META_CLASS)))
    return _main(marker, header, body)


# Internal areas that are private, transactional or non-indexable: a
# homepage CTA into one is never emitted as a crawlable prerender link
# (CMS validation still lets editors configure them for the React page).
_PRIVATE_CTA_PREFIXES = (
    "/admin", "/account", "/api", "/media", "/assets", "/login", "/register",
    "/forgot-password", "/reset-password", "/change-password",
    "/newsletter/unsubscribe", "/resources/checkout", "/circle/checkout", "/search",
)


def _is_private_cta_path(url):
    # React Router matches case-insensitively, so compare lowercased.
    path = url.split("#", 1)[0].split("?", 1)[0].lower().rstrip("/") or "/"
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _PRIVATE_CTA_PREFIXES)


def _safe_cta_href(url):
    """Homepage CTA targets were validated on save as an internal "/..."
    path or http(s) — re-checked here; private areas never linked."""
    if not isinstance(url, str):
        return None
    if url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return None if _is_private_cta_path(url) else url
    return _http_url(url)


def _cta_links(ctas):
    links = []
    for label, url in ctas or []:
        href = _safe_cta_href(url)
        if href and _is_nonblank(label):
            links.append(f'<a href="{_attr(href)}" class="{_LINK_CLASS}">{_text(label)}</a>')
    return f'<p class="mt-4">{" · ".join(links)}</p>' if links else ""


_HOME_DEFAULT_HEADINGS = {
    "featured_stories": "Editors' picks", "latest_stories": "Latest stories", "featured_woman": "Featured woman",
    "jobs": "Jobs", "opportunities": "Opportunities", "events": "Events", "resources": "Resources",
}
_HOME_ITEM_KIND = {"jobs": "jobs", "opportunities": "opportunities", "events": "events", "resources": "resources"}


def render_homepage_prerender(sections, site_name):
    """The configured homepage modules (public_hubs.homepage_sections) in
    builder order. Exactly one H1, matching HeroModule.jsx: with a lead
    Article, the module heading override else the Article title (linked to
    the Article); else the manual hero heading; else the site name."""
    hero = next((s for s in sections if s["type"] == "hero"), None)
    if hero and hero.get("lead"):
        # ArticleCard receives {...lead, title: module.heading} when an
        # override is set, and its headline links to the Article.
        lead = hero["lead"]
        title = hero["heading"] if _is_nonblank(hero.get("heading")) else lead.get("title")
        h1 = f'<h1 class="{_H1_CLASS}">{_hub_link("/" + lead["slug"], title)}</h1>'
    elif hero and _is_nonblank(hero.get("heading")):
        h1 = _h1(hero["heading"])
    else:
        h1 = _h1(site_name)
    header = [h1]
    body = []
    for section in sections:
        heading = section.get("heading") or _HOME_DEFAULT_HEADINGS.get(section["type"]) or ""
        sub = _paragraph(section.get("subheading"), _META_CLASS)
        if section["type"] == "hero":
            if section.get("lead"):
                lead = section["lead"]
                header.append(_paragraph(lead.get("excerpt")))
                header.append(_cta_links(section.get("ctas")))
            else:
                header.append(_paragraph(section.get("subheading")))
                header.append(_cta_links(section.get("ctas")))
            if section.get("articles"):
                body.append(_section("More stories", _item_list(_article_card(a) for a in section["articles"])))
        elif section.get("articles") is not None and section["type"] in ("featured_stories", "latest_stories"):
            body.append(_section(heading, sub + _item_list(_article_card(a) for a in section["articles"])))
        elif section["type"] == "featured_woman":
            body.append(_section(heading or "Featured woman", sub + _item_list([_person_card(section["person"])])))
        elif section.get("term"):
            term = section["term"]
            path = f"/{'series' if term['kind'] == 'series' else 'topics'}/{term['slug']}"
            inner = sub + f'<p>{_hub_link(path, term["name"])}</p>' + _paragraph(term.get("description"), _META_CLASS)
            body.append(_section(heading or term["name"], inner + _item_list(_article_card(a) for a in section.get("articles") or [])))
        elif section["type"] in _HOME_ITEM_KIND:
            render = HUB_CARD_RENDERERS[_HOME_ITEM_KIND[section["type"]]]
            body.append(_section(heading, sub + _item_list(render(i) for i in section["items"])))
        elif section.get("ctas") is not None and _is_nonblank(section.get("heading")):
            body.append(_section(section["heading"], sub + _cta_links(section["ctas"])))
    return _main("home", header, body)
