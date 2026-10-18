"""Module 12B, extended for "WSF SEO Core Readiness — Phase 1": crawler-
readable initial HTML for public pages, served through a Flask SPA-shell
fallback (see app/__init__.py's catch-all route, and deploy/nginx/*.conf.
example's `@spa_shell` named location that proxies a static-file miss
here in production).

Phase 0 (pre-existing, UNCHANGED) built this only for published ARTICLE
flat /<slug> routes (render_article_shell/_build_article_json_ld). Every
other route fell through to render_generic_shell() — the same static
frontend/dist/index.html every route always starts from, untouched.

Phase 1 generalizes the SAME proven pattern (read index.html fresh, strip
a handful of managed <head> tags, inject per-page ones, never touch
anything else) to:
  - the homepage (render_homepage_shell)
  - 8 public entity-detail route families — Topic/Series/Person/Author/
    Opportunity/Job/Resource/Event — each resolved via that entity's own
    EXISTING public-visibility rule (the same one its public API already
    uses), never a new one invented here
  - the corresponding 8 list/landing pages, plus Circle/Newsletter and
    the CMS-backed About/Contact/Privacy/Terms/Cookies/Editorial-Policy
    Page routes
  - a real 404 (with raw noindex metadata) for a genuinely unknown path,
    or a known entity-detail route whose slug doesn't resolve — see
    resolve_spa_response()'s own docstring for the full route-class
    breakdown this replaced the old blanket-200 soft-404 with

Every route not covered above (an organizations/directory/learning/shop/
newsletter-issue detail page, /admin/*, every other already-working SPA
route) is deliberately left exactly as it already behaved — generic
shell, HTTP 200 — because no per-entity visibility rule for those has
been vetted here; expanding them is future work, not a regression risk
to take on in this phase.

Every visitor — human or crawler — still receives the SAME initial HTML;
nothing here ever special-cases a request by User-Agent. Still
deliberately NOT Next.js, a Node SSR server, or a separate prerender
service — a small, stdlib-only (no HTML-parsing dependency) rewrite of a
handful of <head> tags over Vite's own static build output.

Phase 2A ("Server Structured Data + Breadcrumbs") adds, on top of
Phase 1's metadata-only coverage:
  - mirrored entity-specific JSON-LD (JobPosting/Event/Resource's
    DigitalDocument-or-VideoObject/Person twice over, for both Person
    and Author) for the 5 entity-detail types whose existing frontend
    structured-data hook this app already trusts — see each
    _build_*_json_ld() function's own docstring for exactly which
    frontend hook it mirrors and why
  - server-rendered BreadcrumbList JSON-LD for every entity-detail
    type (all 8, including the 3 — Topic/Series/Opportunity — that
    don't get their own entity schema this phase), their list/landing
    pages, the Article shell, and CMS Page routes — see
    _build_breadcrumb_json_ld()
  - no frontend changes for the 5 entity-detail types' own entity
    JSON-LD: each one's existing client-side structured-data hook
    (JobDetailPage.jsx et al.) already finds and reuses a script tag by
    attribute PRESENCE, not by content — so it naturally adopts this
    phase's server-rendered tag instead of appending a duplicate
  - a shared frontend hook, useBreadcrumbStructuredData.js, wired into
    every list/landing page and CMS page that receives a server
    BreadcrumbList (plus the detail pages, added alongside their own
    entity hook) using the SAME find-by-attribute-presence pattern, so
    every route that gets a server BreadcrumbList also owns and updates
    it client-side on SPA navigation, and a page with no breadcrumb of
    its own can never inherit a previous page's stale one
"""
import json
import re
from html import escape as _escape

from flask import Response, abort, current_app, redirect

from app.extensions import db
from app.models.article import Article, Redirect
from app.models.entity_redirect import EntityRedirect
from app.models.media import Media
from app.models.opportunity import Event, Job, Opportunity
from app.models.page import Page
from app.models.people import Author, Person
from app.models.resource import Resource
from app.models.taxonomy import Series, Topic
from app.services.event_registrations import is_event_publicly_visible
from app.services.job_access import is_job_application_open, is_job_publicly_visible
from app.services.site_settings import get_site_identity_resolved, get_visible_social_links

_HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
_TITLE_RE = re.compile(r"<title\b[^>]*>.*?</title>", re.IGNORECASE | re.DOTALL)
_CANONICAL_RE = re.compile(r'<link\s+(?:[^>]*?\s)?rel=["\']canonical["\'][^>]*>', re.IGNORECASE)

# Paths the SPA shell must never handle — each either already has its
# own dedicated Flask route (api/*, sitemap.xml, robots.txt — Werkzeug
# always prefers that more specific match over this module's catch-all
# regardless of registration order) or is served directly by Nginx in
# production with no Flask route at all (assets/, media/ outside debug
# mode). This guard is what stops a request made straight against Flask
# — bypassing Nginx entirely, exactly as a test client does — from ever
# getting an HTML page back for one of these instead of a real 404.
_RESERVED_PREFIXES = ("api/", "assets/", "media/")
_RESERVED_EXACT = ("sitemap.xml", "robots.txt")


def _meta_re(attr, key):
    return re.compile(rf'<meta\s+(?:[^>]*?\s)?{attr}=["\']{re.escape(key)}["\'][^>]*>', re.IGNORECASE)


def _insert_before_head_close(html_doc, fragment):
    match = _HEAD_CLOSE_RE.search(html_doc)
    if not match:
        # Defensive only — a real Vite build always has a </head>.
        return html_doc + fragment
    return html_doc[: match.start()] + fragment + html_doc[match.start() :]


def _set_title(html_doc, title):
    # Strip EVERY existing <title> first (re.sub with no count removes
    # all matches, not just the first) so a baseline index.html that
    # already carries duplicates — or ever acquires one from a bad prior
    # build — always collapses to exactly one managed tag, never a
    # leftover extra.
    html_doc = _TITLE_RE.sub("", html_doc)
    if title:
        tag = f"<title>{_escape(title, quote=True)}</title>"
        html_doc = _insert_before_head_close(html_doc, tag + "\n")
    return html_doc


def _set_meta(html_doc, attr, key, content):
    """Removes EVERY existing <meta attr="key" ...> tag (any attribute
    order, any number of duplicates) and, when `content` is truthy,
    inserts exactly one fresh tag before </head> — so the result always
    has exactly one managed tag for this key when a value is set, and
    zero when it's absent, regardless of how many (if any) the baseline
    index.html started with. A falsy `content` leaves the key removed
    entirely, matching useSeo.js's own clear-when-absent behavior.
    """
    pattern = _meta_re(attr, key)
    html_doc = pattern.sub("", html_doc)
    if content:
        tag = f'<meta {attr}="{_escape(key, quote=True)}" content="{_escape(str(content), quote=True)}">'
        html_doc = _insert_before_head_close(html_doc, tag + "\n")
    return html_doc


def _set_canonical(html_doc, href):
    html_doc = _CANONICAL_RE.sub("", html_doc)
    if href:
        tag = f'<link rel="canonical" href="{_escape(href, quote=True)}">'
        html_doc = _insert_before_head_close(html_doc, tag + "\n")
    return html_doc


def _safe_json_ld(data):
    # Standard </script>-breakout guard: valid JSON permits an escaped
    # forward slash, and no browser's HTML tokenizer treats "<\/script"
    # as a real closing tag, so this is invisible to JSON.parse/any JSON
    # consumer while making it impossible for CMS text containing a
    # literal "</script>" (or "<!--") to terminate this <script> element
    # early or otherwise break out of it.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _structured_data_re(attr_name):
    return re.compile(rf"<script\b[^>]*{re.escape(attr_name)}[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)


def _set_structured_data(html_doc, attr_name, data):
    """Same dedup-then-insert shape as _set_meta/_set_canonical, but
    parametrized by the managed script's own data-*-structured-data
    attribute name so independent JSON-LD blocks (Article's own,
    site-wide WebSite+Organization, ...) can coexist on one page without
    colliding or needing their own copy of this logic. Article's own
    attribute name (data-article-structured-data) is unchanged from
    Phase 0 — existing tests depend on it.
    """
    html_doc = _structured_data_re(attr_name).sub("", html_doc)
    if data:
        tag = f'<script type="application/ld+json" {attr_name}="true">{_safe_json_ld(data)}</script>'
        html_doc = _insert_before_head_close(html_doc, tag + "\n")
    return html_doc


_IMAGE_PRELOAD_RE = re.compile(r'<link\b[^>]*data-lcp-image-preload="true"[^>]*>', re.IGNORECASE)


def _image_preload_candidates(media):
    """Sorted-ascending, deduped-by-width (width, url) pairs built from a
    real Media's own generated MediaVariant rows — mirrors frontend/src/
    utils/media.js's resolveMediaImage() srcSet construction (same sort/
    dedupe/invalid-width-filter rules) so the preloaded candidate set
    matches what the browser will actually pick once the SPA mounts and
    renders the same image with a real srcSet. Returns (href, candidates)
    where `href` is a real generated variant when any exist (preferring
    "large", matching what a browser that ignores imagesrcset would
    fetch) and `candidates` is `[]` when none do — never the protected
    filesystem path, only Media/MediaVariant.public_url.
    """
    by_width = {}
    for variant in media.variants:
        if variant.public_url and variant.width and variant.width > 0:
            by_width[variant.width] = variant.public_url
    if not by_width:
        return media.public_url, []
    candidates = sorted(by_width.items())
    preferred = media.variant_url("large") or media.variant_url("hero") or candidates[-1][1]
    return preferred, candidates


def _set_image_preload(html_doc, *, media, public_site_url, sizes):
    """WSF SEO Phase 2C — the ONE managed <link rel=preload as=image> tag
    for this page's genuine LCP/hero image, same dedup-then-insert shape
    as _set_meta/_set_structured_data (strip every existing managed tag,
    then insert exactly one fresh tag when there's a real image to
    preload). Only ever called for a route whose frontend ALSO marks
    this same image `priority` — see render_article_shell and
    _render_entity_detail's _ENTITY_IMAGE_PRELOAD for exactly which
    routes that is. `sizes` should match that frontend <img>'s own
    `sizes` attribute closely so the browser's preload candidate
    selection agrees with its later real image-element selection.
    """
    html_doc = _IMAGE_PRELOAD_RE.sub("", html_doc)
    if media is None:
        return html_doc
    href, candidates = _image_preload_candidates(media)
    href_url = _absolute_url(href, public_site_url)
    if not href_url:
        return html_doc
    attrs = [
        'rel="preload"',
        'as="image"',
        f'href="{_escape(href_url, quote=True)}"',
        'fetchpriority="high"',
        'data-lcp-image-preload="true"',
    ]
    if len(candidates) > 1:
        srcset_urls = [(w, _absolute_url(u, public_site_url)) for w, u in candidates]
        if all(u for _, u in srcset_urls):
            srcset = ", ".join(f"{_escape(u, quote=True)} {w}w" for w, u in srcset_urls)
            attrs.append(f'imagesrcset="{srcset}"')
            attrs.append(f'imagesizes="{_escape(sizes, quote=True)}"')
    tag = f"<link {' '.join(attrs)}>"
    return _insert_before_head_close(html_doc, tag + "\n")


def _read_index_html():
    # Read fresh on every call — never cached in a module-level variable
    # — so a newer frontend build is picked up immediately with no
    # backend restart or code change (see config.SPA_INDEX_PATH).
    path = current_app.config["SPA_INDEX_PATH"]
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _absolute_url(value, public_site_url):
    if not value:
        return None
    if re.match(r"^https?://", value, re.IGNORECASE):
        return value
    if value.startswith("/"):
        return f"{public_site_url.rstrip('/')}{value}"
    return None


def _html_response(html_doc, status=200):
    response = Response(html_doc, status=status, mimetype="text/html")
    # Matches the Nginx template's own `location = /index.html` treatment
    # of this exact file — this is the same document, just with metadata
    # injected, so it must never be cached any more aggressively than the
    # static original already isn't.
    response.headers["Cache-Control"] = "no-cache"
    return response


def render_generic_shell():
    """The plain, unmodified built index.html — every SPA route that
    isn't one of the server-rendered routes below (including a slug/
    entity that's draft/scheduled/archived/unknown, where leaking even
    its existence would be wrong) gets exactly this, same as Nginx's own
    previous `try_files ... /index.html` fallback already did. Also what
    a legitimate, already-working route this phase deliberately didn't
    enhance (/admin/*, organizations/directory/learning/shop/newsletter-
    issue detail pages) keeps getting — never 404, never rewritten.
    """
    return _html_response(_read_index_html())


def _resolve_social_image(explicit_media, fallback_media, site_identity, public_site_url):
    """Three-tier social-image priority, shared by every server-rendered
    page: an explicit SEO-image override (Article only — no other
    content type's frontend page distinguishes a separate "social share
    image" from its own primary image) -> the content's own primary
    image (hero/cover/logo/photo — `fallback_media`, already resolved to
    a Media row or None by the caller) -> the global Site Settings
    default image. Every other server-rendered page calls this with
    `explicit_media=None`, exactly matching what its own frontend
    useSeo() call does today (none of them reference `seo.ogImageMediaId`
    for their `image` prop — only ArticlePage/articleStructuredData.js
    do).
    """
    if explicit_media is not None:
        return _absolute_url(explicit_media.public_url, public_site_url), explicit_media.alt_text or None
    if fallback_media is not None:
        return _absolute_url(fallback_media.public_url, public_site_url), fallback_media.alt_text or None
    default_image = site_identity.get("og_image")
    if default_image is not None:
        image_path = default_image.variant_url("large") or default_image.public_url
        return _absolute_url(image_path, public_site_url), None
    return None, None


def _explicit_seo_image_media(seo):
    media_id = (seo or {}).get("ogImageMediaId")
    return db.session.get(Media, media_id) if media_id else None


def _build_site_json_ld(site_identity, public_site_url):
    """Mirrors frontend/src/hooks/useSiteStructuredData.js's WebSite +
    Organization pair exactly (same two @types, same name/url/logo/
    sameAs fields, same "only real admin-configured values, nothing
    fabricated" rule) so the browser- and server-rendered shapes never
    drift apart. Rendered on every server-rendered page — homepage, list
    pages, the 8 entity-detail types, CMS Page routes, and (under its
    own data-site-structured-data attribute, alongside and never
    replacing the existing data-article-structured-data block) the
    Article shell too — see render_article_shell().
    """
    site_name = site_identity.get("site_name") or "Women Shaping Futures"
    data = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": site_name, "url": public_site_url},
        {"@context": "https://schema.org", "@type": "Organization", "name": site_name, "url": public_site_url},
    ]
    logo = site_identity.get("logo")
    if logo is not None:
        logo_path = logo.variant_url("card") or logo.public_url
        logo_url = _absolute_url(logo_path, public_site_url)
        if logo_url:
            data[1]["logo"] = logo_url
    same_as = [link.url for link in get_visible_social_links() if link.url]
    if same_as:
        data[1]["sameAs"] = same_as
    return data


def _apply_base_seo(html_doc, *, title, description, canonical, robots, og_type, image_url, image_alt, site_name):
    """The one shared primitive every server-rendered page (Article
    included) builds its <head> from — title/description/robots/
    canonical/OG/Twitter. Structured data is applied separately by each
    caller (_set_structured_data), since which block(s) a page gets
    varies (Article's own JSON-LD; the site-wide WebSite+Organization
    block for everything else this phase covers; both possible on a
    single page without colliding).
    """
    html_doc = _set_title(html_doc, title)
    html_doc = _set_meta(html_doc, "name", "description", description)
    html_doc = _set_meta(html_doc, "name", "robots", robots)
    html_doc = _set_canonical(html_doc, canonical)
    html_doc = _set_meta(html_doc, "property", "og:title", title)
    html_doc = _set_meta(html_doc, "property", "og:description", description)
    html_doc = _set_meta(html_doc, "property", "og:url", canonical)
    html_doc = _set_meta(html_doc, "property", "og:type", og_type)
    html_doc = _set_meta(html_doc, "property", "og:site_name", site_name)
    html_doc = _set_meta(html_doc, "property", "og:image", image_url)
    html_doc = _set_meta(html_doc, "property", "og:image:alt", image_alt if image_url else None)
    html_doc = _set_meta(html_doc, "name", "twitter:card", "summary_large_image")
    html_doc = _set_meta(html_doc, "name", "twitter:title", title)
    html_doc = _set_meta(html_doc, "name", "twitter:description", description)
    html_doc = _set_meta(html_doc, "name", "twitter:image", image_url)
    html_doc = _set_meta(html_doc, "name", "twitter:image:alt", image_alt if image_url else None)
    return html_doc


def _build_article_json_ld(article, canonical_url, image_url, site_identity, public_site_url):
    """Same shape/semantics as frontend/src/utils/articleStructuredData.js's
    buildArticleStructuredData() — deliberately recomputes headline/
    description straight from the article rather than reusing the
    meta-tag description (which also falls back to the global SEO
    default): JSON-LD's description never gets that global fallback,
    exactly matching the frontend builder.
    """
    seo = article.seo or {}
    headline = seo.get("title") or article.title
    description = seo.get("description") or article.excerpt

    authors = [a for a in ([article.author] + list(article.co_authors or [])) if a is not None]
    author_base_url = f"{public_site_url.rstrip('/')}/authors"
    author_objs = [
        {"@type": "Person", "name": author.name, **({"url": f"{author_base_url}/{author.slug}"} if author.slug else {})}
        for author in authors
    ]

    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
        "url": canonical_url,
    }
    if description:
        data["description"] = description
    if image_url:
        data["image"] = image_url
    if article.publish_date:
        data["datePublished"] = article.publish_date.isoformat()
    if article.updated_at:
        data["dateModified"] = article.updated_at.isoformat()
    if len(author_objs) == 1:
        data["author"] = author_objs[0]
    elif len(author_objs) > 1:
        data["author"] = author_objs

    publisher = {
        "@type": "Organization",
        "name": site_identity.get("site_name") or "Women Shaping Futures",
        "url": public_site_url,
    }
    logo = site_identity.get("logo")
    if logo is not None:
        # The generated `card` MediaVariant when one exists, falling back
        # to public_url when it doesn't — matches the frontend's own
        # resolveMediaImage() variant resolution for the site logo.
        logo_path = logo.variant_url("card") or logo.public_url
        logo_url = _absolute_url(logo_path, public_site_url)
        if logo_url:
            publisher["logo"] = {"@type": "ImageObject", "url": logo_url}
    data["publisher"] = publisher

    return data


def render_article_shell(article):
    """Builds the crawler-readable HTML for a published Article's flat
    /<slug> route. `article` must already be confirmed PUBLISHED by the
    caller (resolve_spa_response() below) — this function never checks
    status itself. UNCHANGED behavior from Phase 0 apart from two
    additive-only tags: the new og:site_name (_apply_base_seo), and the
    site-wide WebSite/Organization JSON-LD block every other server-
    rendered page gets too — added under its own data-site-structured-
    data attribute, alongside (never replacing) the Article's own
    data-article-structured-data block. Title/description/canonical/
    robots computation and the 3-tier image priority are unchanged.
    """
    public_site_url = current_app.config["PUBLIC_SITE_URL"]
    site_identity = get_site_identity_resolved()
    seo = article.seo or {}

    title = seo.get("title") or article.title or site_identity.get("seo_default_title")
    meta_description = seo.get("description") or article.excerpt or site_identity.get("seo_default_description")
    canonical_url = seo.get("canonical") or f"{public_site_url.rstrip('/')}/{article.slug}"
    robots = seo.get("robots") or "index, follow"
    site_name = site_identity.get("site_name") or "Women Shaping Futures"

    explicit_media = _explicit_seo_image_media(seo)
    image_url, image_alt = _resolve_social_image(explicit_media, article.hero_media, site_identity, public_site_url)

    html_doc = _read_index_html()
    html_doc = _apply_base_seo(
        html_doc,
        title=title,
        description=meta_description,
        canonical=canonical_url,
        robots=robots,
        og_type="article",
        image_url=image_url,
        image_alt=image_alt,
        site_name=site_name,
    )

    structured_data = _build_article_json_ld(article, canonical_url, image_url, site_identity, public_site_url)
    html_doc = _set_structured_data(html_doc, "data-article-structured-data", structured_data)
    html_doc = _set_structured_data(html_doc, "data-site-structured-data", _build_site_json_ld(site_identity, public_site_url))

    # Fixed "Home > Stories > Article title" hierarchy regardless of
    # whether this article has a Topic — matches the visible
    # ArticlePage.jsx breadcrumb's "Stories" link target (/topics) when
    # there IS a topic; this phase doesn't add the extra per-topic
    # breadcrumb level ArticlePage.jsx's visible trail inserts in that
    # case, so it never has to fabricate/guess a topic that may not
    # exist. The Article's own JSON-LD above is unaffected either way.
    breadcrumb = _build_breadcrumb_json_ld(
        public_site_url,
        [("Stories", f"{public_site_url.rstrip('/')}/topics"), (article.title, canonical_url)],
    )
    html_doc = _set_structured_data(html_doc, "data-breadcrumb-structured-data", breadcrumb)

    # WSF SEO Phase 2C — ArticlePage.jsx's hero is `priority` with
    # `sizes="(min-width: 1120px) 1120px, 100vw"` (see that component);
    # mirrored here exactly so a browser can start fetching the real LCP
    # candidate before any JS/API round-trip resolves it client-side.
    # `article.hero_media` is None for an article with no hero image, so
    # this is a no-op (no preload tag) in that case.
    html_doc = _set_image_preload(
        html_doc, media=article.hero_media, public_site_url=public_site_url, sizes="(min-width: 1120px) 1120px, 100vw"
    )

    return _html_response(html_doc)


def render_homepage_shell():
    """The one page with its own dedicated Flask route (app/__init__.py's
    `spa_shell_root`) rather than reaching this module through
    resolve_spa_response() — there's no slug/entity to resolve, just the
    same hardcoded copy HomePage.jsx's own useSeo() call already uses,
    now also present before any JavaScript runs.
    """
    public_site_url = current_app.config["PUBLIC_SITE_URL"]
    site_identity = get_site_identity_resolved()
    site_name = site_identity.get("site_name") or "Women Shaping Futures"
    canonical = f"{public_site_url.rstrip('/')}/"
    title = "Women Shaping Futures — Stories, Opportunity & Growth for Women Worldwide"
    description = (
        "Women Shaping Futures is a global media and opportunity platform amplifying "
        "women’s stories and connecting women to jobs, mentorship, and growth."
    )
    image_url, image_alt = _resolve_social_image(None, None, site_identity, public_site_url)

    html_doc = _read_index_html()
    html_doc = _apply_base_seo(
        html_doc,
        title=title,
        description=description,
        canonical=canonical,
        robots="index, follow",
        og_type="website",
        image_url=image_url,
        image_alt=image_alt,
        site_name=site_name,
    )
    html_doc = _set_structured_data(html_doc, "data-site-structured-data", _build_site_json_ld(site_identity, public_site_url))
    return _html_response(html_doc)


def _render_404_shell():
    """A genuinely unknown path, or a known entity-detail route whose
    slug doesn't resolve to anything publicly visible — see
    resolve_spa_response()'s docstring for exactly which cases reach
    here. Deliberately generic: never mentions which entity type or slug
    was requested, so a draft/private/non-public record's mere existence
    is never leaked through the 404 response either. The frontend's own
    NotFoundPage (unchanged, still reachable via React Router's `*`
    route) renders the same way regardless of this HTTP-layer change.
    """
    site_identity = get_site_identity_resolved()
    site_name = site_identity.get("site_name") or "Women Shaping Futures"
    html_doc = _read_index_html()
    html_doc = _apply_base_seo(
        html_doc,
        title="Page Not Found | Women Shaping Futures",
        description="The page you are looking for could not be found.",
        canonical=None,
        robots="noindex, follow",
        og_type="website",
        image_url=None,
        image_alt=None,
        site_name=site_name,
    )
    return _html_response(html_doc, status=404)


# --- Entity-detail resolution: each entity's lookup reuses that SAME
# entity's own existing public-visibility rule (the one its public API
# list/detail routes already enforce) rather than a new rule invented
# here — see each function's one-line docstring for which rule and
# where it's defined.


def _lookup_topic(slug):
    """Same filter as app/api/v1/taxonomy.py's public Topic detail route."""
    return Topic.query.filter_by(slug=slug, status="published").first()


def _lookup_series(slug):
    """Same filter as app/api/v1/taxonomy.py's public Series detail route."""
    return Series.query.filter_by(slug=slug, status="published").first()


def _lookup_person(slug):
    """Same status check as app/api/v1/people.py's public Person detail route."""
    person = Person.query.filter_by(slug=slug).first()
    return person if person is not None and person.status == "published" else None


def _lookup_author(slug):
    """Same status check as app/api/v1/authors.py's public Author detail
    route — Author uses "active" (not "published") as its live status.
    """
    author = Author.query.filter_by(slug=slug).first()
    return author if author is not None and author.status == "active" else None


def _lookup_opportunity(slug):
    """Same status check as app/api/v1/opportunities.py's public detail route."""
    opportunity = Opportunity.query.filter_by(slug=slug).first()
    return opportunity if opportunity is not None and opportunity.status == "published" else None


def _lookup_job(slug):
    """app/services/job_access.py's is_job_publicly_visible() — the one
    rule the public list/detail routes and sitemap.py already share.
    """
    job = Job.query.filter_by(slug=slug).first()
    return job if job is not None and is_job_publicly_visible(job) else None


def _lookup_event(slug):
    """app/services/event_registrations.py's is_event_publicly_visible()
    — same shared rule sitemap.py already reuses.
    """
    event = Event.query.filter_by(slug=slug).first()
    return event if event is not None and is_event_publicly_visible(event) else None


def _lookup_resource(slug):
    """Resource.is_publicly_visible() — the one rule the public list/
    detail/access routes and sitemap.py already share.
    """
    resource = Resource.query.filter_by(slug=slug).first()
    return resource if resource is not None and resource.is_publicly_visible() else None


# --- Per-entity metadata builders. Each mirrors that entity's OWN
# frontend useSeo() fallback chain exactly (seo.<field> || generated),
# using the same generated-fallback wording the frontend already shows
# today — see this task's implementation notes for the exact file:line
# each one was read from. None of these pass an explicit SEO-image
# override (see _resolve_social_image's docstring): every one of these
# frontend pages already uses its own primary image (logo/cover/photo)
# directly, never a separate `seo.ogImageMediaId`.


def _topic_meta(topic, public_site_url, site_identity):
    seo = topic.seo or {}
    image_url, image_alt = _resolve_social_image(None, topic.hero_media, site_identity, public_site_url)
    return {
        "title": seo.get("title") or f"{topic.name} | Women Shaping Futures",
        "description": seo.get("description") or topic.description,
        "canonical": seo.get("canonical") or f"{public_site_url.rstrip('/')}/topics/{topic.slug}",
        "robots": seo.get("robots") or "index, follow",
        "image_url": image_url,
        "image_alt": image_alt,
    }


def _series_meta(series, public_site_url, site_identity):
    seo = series.seo or {}
    image_url, image_alt = _resolve_social_image(None, series.cover_media, site_identity, public_site_url)
    return {
        "title": seo.get("title") or f"{series.name} | Women Shaping Futures",
        "description": seo.get("description") or series.description,
        "canonical": seo.get("canonical") or f"{public_site_url.rstrip('/')}/series/{series.slug}",
        "robots": seo.get("robots") or "index, follow",
        "image_url": image_url,
        "image_alt": image_alt,
    }


def _person_meta(person, public_site_url, site_identity):
    seo = person.seo or {}
    image_url, image_alt = _resolve_social_image(None, person.photo, site_identity, public_site_url)
    return {
        "title": seo.get("title") or f"{person.name} | Women Shaping Futures",
        "description": seo.get("description") or person.short_bio,
        "canonical": seo.get("canonical") or f"{public_site_url.rstrip('/')}/people/{person.slug}",
        "robots": seo.get("robots") or "index, follow",
        "image_url": image_url,
        "image_alt": image_alt,
    }


def _author_meta(author, public_site_url, site_identity):
    seo = author.seo or {}
    image_url, image_alt = _resolve_social_image(None, author.photo, site_identity, public_site_url)
    return {
        "title": seo.get("title") or f"{author.name} | Women Shaping Futures",
        "description": seo.get("description") or author.short_bio,
        "canonical": seo.get("canonical") or f"{public_site_url.rstrip('/')}/authors/{author.slug}",
        "robots": seo.get("robots") or "index, follow",
        "image_url": image_url,
        "image_alt": image_alt,
    }


def _opportunity_meta(opportunity, public_site_url, site_identity):
    seo = opportunity.seo or {}
    image_url, image_alt = _resolve_social_image(None, opportunity.logo, site_identity, public_site_url)
    return {
        "title": seo.get("title") or f"{opportunity.title} | Women Shaping Futures Opportunities",
        "description": seo.get("description") or opportunity.short_description or opportunity.eligibility,
        "canonical": seo.get("canonical") or f"{public_site_url.rstrip('/')}/opportunities/{opportunity.slug}",
        "robots": seo.get("robots") or "index, follow",
        "image_url": image_url,
        "image_alt": image_alt,
    }


def _job_meta(job, public_site_url, site_identity):
    seo = job.seo or {}
    image_url, image_alt = _resolve_social_image(None, job.logo, site_identity, public_site_url)
    # Matches JobDetailPage.jsx exactly: expired/closed listings stay
    # reachable for record but shouldn't rank, unless an editor
    # explicitly overrides seo.robots.
    is_closed = not is_job_application_open(job)
    return {
        "title": seo.get("title") or f"{job.title} at {job.company_name} | Women Shaping Futures Jobs",
        "description": seo.get("description") or job.short_description,
        "canonical": seo.get("canonical") or f"{public_site_url.rstrip('/')}/jobs/{job.slug}",
        "robots": seo.get("robots") or ("noindex, follow" if is_closed else "index, follow"),
        "image_url": image_url,
        "image_alt": image_alt,
    }


def _event_meta(event, public_site_url, site_identity):
    seo = event.seo or {}
    image_url, image_alt = _resolve_social_image(None, event.cover_media, site_identity, public_site_url)
    return {
        "title": seo.get("title") or f"{event.title} | Women Shaping Futures Events",
        "description": seo.get("description") or event.short_description,
        "canonical": seo.get("canonical") or f"{public_site_url.rstrip('/')}/events/{event.slug}",
        "robots": seo.get("robots") or "index, follow",
        "image_url": image_url,
        "image_alt": image_alt,
    }


def _resource_meta(resource, public_site_url, site_identity):
    seo = resource.seo or {}
    image_url, image_alt = _resolve_social_image(None, resource.cover_media, site_identity, public_site_url)
    return {
        "title": seo.get("title") or f"{resource.name} | Women Shaping Futures Resources",
        "description": seo.get("description") or resource.short_description or resource.name,
        "canonical": seo.get("canonical") or f"{public_site_url.rstrip('/')}/resources/{resource.slug}",
        # Deliberately no computed robots fallback (matches
        # ResourceDetailPage.jsx exactly) — a Premium/Circle-gated
        # resource's own MARKETING page stays indexable even though its
        # download is gated; only an explicit seo.robots overrides this.
        "robots": seo.get("robots") or "index, follow",
        "image_url": image_url,
        "image_alt": image_alt,
    }


def _build_breadcrumb_json_ld(public_site_url, crumbs):
    """Server-rendered schema.org BreadcrumbList — WSF SEO Phase 2A.
    Always anchored at Home (position 1, the site root); `crumbs` is the
    ordered list of (name, absolute_url) pairs for every crumb AFTER
    Home, including the current page's own crumb (using that page's own
    canonical URL, so the trail always ends on the exact address the
    page itself canonicalizes to). Positions are always contiguous
    starting at 1. The hierarchy for each route this phase covers
    mirrors that page's own EXISTING visible <Breadcrumb items=...> —
    see each call site — never a level invented here that isn't already
    shown there.
    """
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{public_site_url.rstrip('/')}/"}]
    for position, (name, url) in enumerate(crumbs, start=2):
        items.append({"@type": "ListItem", "position": position, "name": name, "item": url})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


_JOB_EMPLOYMENT_TYPE_SCHEMA = {
    "Full-time": "FULL_TIME",
    "Part-time": "PART_TIME",
    "Contract": "CONTRACTOR",
    "Temporary": "TEMPORARY",
    "Internship": "INTERN",
}


def _build_job_json_ld(job, canonical_url, public_site_url, site_name):
    """Mirrors frontend/src/pages/JobDetailPage.jsx's
    useJobStructuredData field-for-field — same EMPLOYMENT_TYPE_SCHEMA
    mapping, same remote/on-site location branching, same
    salary-visibility gate, nothing fabricated beyond what that hook
    already shows. Only ever called (see _render_entity_detail) for a
    Job _lookup_job already confirmed publicly visible
    (is_job_publicly_visible) — this function never re-checks status
    itself. `site_name` is accepted for signature parity with the other
    4 entity builders but unused here — a JobPosting's organization is
    always the job's own employer, never WSF itself.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.title,
        "description": job.short_description or job.title,
    }
    if job.published_date:
        data["datePosted"] = job.published_date.isoformat()
    if job.deadline:
        # Matches new Date(job.deadline).toISOString() for a date-only
        # JS Date — midnight UTC on that calendar date.
        data["validThrough"] = f"{job.deadline.isoformat()}T00:00:00Z"
    if job.employment_type and job.employment_type in _JOB_EMPLOYMENT_TYPE_SCHEMA:
        data["employmentType"] = _JOB_EMPLOYMENT_TYPE_SCHEMA[job.employment_type]

    hiring_org = {"@type": "Organization", "name": job.company_name}
    logo_media = job.organization.logo if job.organization and job.organization.logo else job.logo
    if logo_media is not None:
        logo_url = _absolute_url(logo_media.public_url, public_site_url)
        if logo_url:
            hiring_org["logo"] = logo_url
    data["hiringOrganization"] = hiring_org

    if job.work_mode == "Remote":
        data["jobLocationType"] = "TELECOMMUTE"
        if job.remote_scope == "worldwide":
            data["applicantLocationRequirements"] = {"@type": "Country", "name": "Anywhere"}
        elif job.remote_scope == "country" and job.country:
            data["applicantLocationRequirements"] = {"@type": "Country", "name": job.country.name}
        elif job.remote_scope == "region" and job.remote_region:
            data["applicantLocationRequirements"] = {"@type": "Place", "name": job.remote_region}
    elif job.location or job.country:
        address = {"@type": "PostalAddress"}
        if job.city:
            address["addressLocality"] = job.city
        elif job.location:
            address["addressLocality"] = job.location
        if job.country:
            address["addressCountry"] = job.country.code
        data["jobLocation"] = {"@type": "Place", "address": address}

    if job.salary_min and job.currency and job.salary_visible:
        value = {"@type": "QuantitativeValue", "minValue": job.salary_min}
        if job.salary_max:
            value["maxValue"] = job.salary_max
        value["unitText"] = (job.salary_period or "year").upper()[:4]
        data["baseSalary"] = {"@type": "MonetaryAmount", "currency": job.currency, "value": value}

    return data


_EVENT_ATTENDANCE_MODE = {
    "in-person": "https://schema.org/OfflineEventAttendanceMode",
    "virtual": "https://schema.org/OnlineEventAttendanceMode",
    "hybrid": "https://schema.org/MixedEventAttendanceMode",
}


def _build_event_json_ld(event, canonical_url, public_site_url, site_name):
    """Mirrors frontend/src/pages/EventDetailPage.jsx's
    useEventStructuredData field-for-field, including its `offers.price`
    semantics. The Event model has no separate "this event is free"
    flag — a ticket_price that was simply never entered is treated as
    free by convention, the SAME rule the public API already applies
    (EventSchema.get_is_free: `not event.ticket_price` — see
    app/schemas/opportunity.py), so free here means `price: "0"`, never
    a fabricated priceCurrency when no currency was ever configured. A
    real ticket_price only ever gets a price when a real currency is
    also on file — see the frontend hook for the identical rule; the
    two must stay in lockstep or hydration overwrites this SSR offer
    with a disagreeing one.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event.title,
        "description": event.short_description or event.title,
    }
    if event.cover_media is not None:
        image_url = _absolute_url(event.cover_media.public_url, public_site_url)
        if image_url:
            data["image"] = image_url

    data["startDate"] = f"{event.date.isoformat()}T{event.start_time.isoformat()}" if event.start_time else event.date.isoformat()
    if event.end_time:
        end_date_val = event.end_date or event.date
        data["endDate"] = f"{end_date_val.isoformat()}T{event.end_time.isoformat()}"
    elif event.end_date:
        data["endDate"] = event.end_date.isoformat()

    if event.status == "cancelled":
        data["eventStatus"] = "https://schema.org/EventCancelled"
    elif event.status == "postponed":
        data["eventStatus"] = "https://schema.org/EventPostponed"
    else:
        data["eventStatus"] = "https://schema.org/EventScheduled"

    if event.format and event.format in _EVENT_ATTENDANCE_MODE:
        data["eventAttendanceMode"] = _EVENT_ATTENDANCE_MODE[event.format]

    organizer_name = event.organizer.name if event.organizer else (event.organizer_name or site_name)
    data["organizer"] = {"@type": "Organization", "name": organizer_name}

    if event.format == "virtual":
        # Never the private virtual_link — the canonical page URL, same
        # as the frontend hook, regardless of virtual_link_public.
        data["location"] = {"@type": "VirtualLocation", "url": canonical_url}
    else:
        address = {"@type": "PostalAddress"}
        if event.address:
            address["streetAddress"] = event.address
        if event.city:
            address["addressLocality"] = event.city
        elif event.location:
            address["addressLocality"] = event.location
        if event.country:
            address["addressCountry"] = event.country.code
        place = {"@type": "Place", "address": address}
        if event.venue:
            place["name"] = event.venue
        data["location"] = place

    if event.registration_url:
        offer = {
            "@type": "Offer",
            "url": event.registration_url,
            "availability": "https://schema.org/SoldOut" if event.sold_out else "https://schema.org/InStock",
        }
        if not event.ticket_price:
            offer["price"] = "0"
            if event.currency:
                offer["priceCurrency"] = event.currency
        elif event.currency:
            offer["price"] = event.ticket_price
            offer["priceCurrency"] = event.currency
        data["offers"] = offer

    speakers = [
        {"@type": "Person", "name": (s.person.name if s.person else s.name)} for s in (event.speakers or [])
    ]
    speakers = [p for p in speakers if p["name"]]
    if speakers:
        data["performer"] = speakers

    return data


def _build_resource_json_ld(resource, canonical_url, public_site_url, site_name):
    """Mirrors frontend/src/pages/ResourceDetailPage.jsx's
    useResourceStructuredData field-for-field. The @type branch checks
    `resource.type == "Video Resource"` — the Resource model's actual
    content-type field (see RESOURCE_TYPES in app/models/resource.py) —
    never `access_type` (the delivery/gating mechanism: direct_download/
    email_gate/member_only/circle_only/premium/external_link), which has
    no "video" value at all and was the wrong field checked here and on
    the frontend hook before this correction. Never references
    file_url/external_url/protected_file_path/download tokens/purchase
    IDs/member IDs — same safe fields the frontend hook already limits
    itself to.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "VideoObject" if resource.type == "Video Resource" else "DigitalDocument",
        "name": resource.name,
        "description": resource.short_description or resource.name,
        "url": canonical_url,
    }
    if resource.cover_media is not None:
        image_url = _absolute_url(resource.cover_media.public_url, public_site_url)
        if image_url:
            data["image"] = image_url

    if resource.author is not None and resource.author.name:
        data["author"] = {"@type": "Person", "name": resource.author.name}
    elif resource.author_name:
        data["author"] = {"@type": "Organization", "name": resource.author_name}

    data["publisher"] = {"@type": "Organization", "name": site_name}

    # A zero-price Offer is only truthful for a resource that's openly
    # available for the taking. member_only/circle_only gate on
    # something real (an account, a paid Circle membership) rather than
    # a price, so neither gets an Offer — omitted entirely rather than
    # falsely advertised as free/InStock. premium has a real,
    # purchasable price and gets its own real Offer instead.
    if resource.access_type in ("direct_download", "email_gate", "external_link"):
        data["offers"] = {
            "@type": "Offer",
            "price": 0,
            "priceCurrency": resource.currency or "KES",
            "availability": "https://schema.org/InStock",
        }
    elif resource.access_type == "premium":
        data["offers"] = {
            "@type": "Offer",
            "price": resource.price,
            "priceCurrency": resource.currency or "KES",
            "availability": "https://schema.org/InStock",
            "url": canonical_url,
        }

    return data


def _social_same_as(entity):
    """Shared by Person/Author — identical sameAs derivation as
    PersonProfilePage.jsx/AuthorProfilePage.jsx's own hooks: the real
    website plus LinkedIn/Twitter profile URLs built from the stored
    handle, only when actually present. Never a fabricated profile.
    """
    social = entity.social or {}
    candidates = [
        entity.website,
        f"https://linkedin.com/in/{social['linkedin']}" if social.get("linkedin") else None,
        f"https://twitter.com/{social['twitter']}" if social.get("twitter") else None,
    ]
    return [url for url in candidates if url]


def _build_person_json_ld(person, canonical_url, public_site_url, site_name):
    """Mirrors frontend/src/pages/PersonProfilePage.jsx's
    usePersonStructuredData field-for-field. Never exposes email or any
    internal account/role ID — none of those are referenced here, same
    as the frontend hook.
    """
    data = {"@context": "https://schema.org", "@type": "Person", "name": person.name, "url": canonical_url}
    if person.title:
        data["jobTitle"] = person.title
    if person.organization is not None and person.organization.name:
        data["worksFor"] = {"@type": "Organization", "name": person.organization.name}
    if person.photo is not None:
        image_url = _absolute_url(person.photo.public_url, public_site_url)
        if image_url:
            data["image"] = image_url
    same_as = _social_same_as(person)
    if same_as:
        data["sameAs"] = same_as
    return data


def _build_author_json_ld(author, canonical_url, public_site_url, site_name):
    """Mirrors frontend/src/pages/AuthorProfilePage.jsx's
    useAuthorStructuredData field-for-field. Never exposes email or any
    internal account/role ID — none of those are referenced here, same
    as the frontend hook.
    """
    data = {"@context": "https://schema.org", "@type": "Person", "name": author.name, "url": canonical_url}
    if author.role:
        data["jobTitle"] = author.role
    if author.photo is not None:
        image_url = _absolute_url(author.photo.public_url, public_site_url)
        if image_url:
            data["image"] = image_url
    same_as = _social_same_as(author)
    if same_as:
        data["sameAs"] = same_as
    return data


# Maps each in-scope entity-detail URL prefix (/<prefix>/<slug>) to its
# (lookup, metadata-builder, breadcrumb section label, display-name
# getter) tuple. A prefix NOT in this dict but still a real two-segment
# SPA route (organizations, directory, learning, shop, newsletter) is
# handled by _UNENHANCED_PREFIXES below instead — left exactly as it
# already behaved, never enhanced and never 404'd. The breadcrumb
# section label doubles as that section's own path segment
# (f"/{prefix}") — see _render_entity_detail.
_ENTITY_DETAIL_PREFIXES = {
    "topics": (_lookup_topic, _topic_meta, "Topics", lambda e: e.name),
    "series": (_lookup_series, _series_meta, "Series", lambda e: e.name),
    "people": (_lookup_person, _person_meta, "People", lambda e: e.name),
    "authors": (_lookup_author, _author_meta, "Authors", lambda e: e.name),
    "opportunities": (_lookup_opportunity, _opportunity_meta, "Opportunities", lambda e: e.title),
    "jobs": (_lookup_job, _job_meta, "Jobs", lambda e: e.title),
    "resources": (_lookup_resource, _resource_meta, "Resources", lambda e: e.name),
    "events": (_lookup_event, _event_meta, "Events", lambda e: e.title),
}

# WSF SEO Phase 2B — maps each nested entity-detail route prefix to the
# matching EntityRedirect.entity_type value (see
# app/models/entity_redirect.py's own docstring for why entity_type is
# the singular noun, not this plural URL segment). Used only by
# _render_entity_detail's redirect fallback below, once the live-entity
# lookup at that exact slug has already missed — the live route always
# wins over stale redirect history.
_ENTITY_TYPE_BY_PREFIX = {
    "topics": "topic",
    "series": "series",
    "people": "person",
    "authors": "author",
    "opportunities": "opportunity",
    "jobs": "job",
    "resources": "resource",
    "events": "event",
}

# The 5 entity-detail prefixes that additionally get their OWN
# entity-specific JSON-LD (mirroring that entity's existing frontend
# structured-data hook — see each builder's own docstring), under the
# SAME data-*-structured-data attribute name that entity's existing
# client-side hook already looks for (JobDetailPage.jsx et al.) — so the
# existing client hook finds and reuses this server-rendered tag rather
# than appending a duplicate, with no change needed to any of those 5
# hooks themselves (useBreadcrumbStructuredData, which every one of
# these detail pages also now calls, is a separate, shared hook — see
# frontend/src/hooks/useBreadcrumbStructuredData.js).
# Topic/Series/Opportunity get BreadcrumbList only (see section 9 of the
# implementation task) — deliberately absent from this second dict.
_ENTITY_STRUCTURED_DATA_BUILDERS = {
    "jobs": ("data-job-structured-data", _build_job_json_ld),
    "events": ("data-event-structured-data", _build_event_json_ld),
    "resources": ("data-resource-structured-data", _build_resource_json_ld),
    "people": ("data-person-structured-data", _build_person_json_ld),
    "authors": ("data-author-structured-data", _build_author_json_ld),
}

# WSF SEO Phase 2C — the 3 non-Article entity-detail prefixes whose
# OWN frontend page marks its primary image `priority` (a genuine
# above-the-fold hero/cover, not a small avatar/logo — see
# SeriesDetailPage.jsx/ResourceDetailPage.jsx/EventDetailPage.jsx).
# Topic (no page image at all), People/Authors (small portrait next to
# a lot of text — left lazy on purpose) and Opportunities/Jobs (small
# logo only) are deliberately absent: preloading their image would not
# match a real LCP candidate. Each entry's `sizes` mirrors that same
# frontend <img>'s own `sizes` attribute exactly. Resource's own
# gallery defaults to showing `cover_media` first (see
# ResourceGallery's `active` state in ResourceDetailPage.jsx), so that
# is the correct media to preload there too.
_ENTITY_IMAGE_PRELOAD = {
    "series": (lambda e: e.cover_media, "(min-width: 1024px) 45vw, 100vw"),
    "resources": (lambda e: e.cover_media, "(min-width: 640px) 360px, 100vw"),
    "events": (lambda e: e.cover_media, "100vw"),
}

# The 8 list/landing pages that get a 2-level ("Home" > Section)
# BreadcrumbList — a subset of _STATIC_ROUTES's "list"-kind entries:
# circle/newsletter are deliberately excluded (not part of this phase's
# breadcrumb scope — see _render_static_route).
_LIST_PAGE_BREADCRUMB_LABELS = {
    "topics": "Topics",
    "series": "Series",
    "people": "People",
    "authors": "Authors",
    "opportunities": "Opportunities",
    "jobs": "Jobs",
    "resources": "Resources",
    "events": "Events",
}

# First path segment of an already-working SPA route this phase does
# NOT enhance (no vetted public-visibility rule gathered for these yet)
# — matched regardless of total segment count, so this also covers e.g.
# newsletter/unsubscribe/<token>, not just newsletter/<slug>. Checked
# before the final "genuinely unknown -> 404" fallback so none of these
# real, working pages are ever wrongly 404'd.
_UNENHANCED_PREFIXES = {"organizations", "directory", "newsletter", "learning", "shop"}

# The stable keys this app's CMS Page model already uses (see
# app/models/page.py's SYSTEM_PAGE_KEYS) — About/Legal pages fall back to
# page.title/page.subtitle when seo.title/description is blank
# (AboutPage.jsx/LegalPage.jsx); Contact does not (ContactPage.jsx falls
# straight through to the global Site Settings default instead). Only
# About passes its own hero image as the OG-image fallback; the rest
# pass none (so the global default image applies if they have no
# explicit seo.ogImageMediaId... which none of them check either — see
# _render_system_page_shell).
_SYSTEM_PAGE_KEYS = ("about", "contact", "privacy", "terms", "cookies", "editorial-policy")

# Exact-path registry for every other known static/landing/utility route
# this phase covers. Each value is a tuple led by a "kind" tag:
#   ("list", title, description)       — stable list/landing page copy
#   ("noindex", title, description, robots) — auth/private/utility page
#   ("passthrough",)                   — a real, working route with no
#                                         indexable content of its own —
#                                         just the untouched generic shell
# Canonical for "list"/"noindex" entries is always {PUBLIC_SITE_URL}/
# {subpath} — computed once in _render_static_route, not repeated here.
_STATIC_ROUTES = {
    "topics": (
        "list",
        "Stories by Topic | Women Shaping Futures",
        "Explore Women Shaping Futures stories by topic — leadership, careers, entrepreneurship, money, technology, and more.",
    ),
    "series": (
        "list",
        "Editorial Series | Women Shaping Futures",
        "Explore our ongoing editorial series, from Women Doing Incredible Things to Founder Stories.",
    ),
    "people": (
        "list",
        "People Directory | Women Shaping Futures",
        "Discover the women leading business, science, government, and culture around the world.",
    ),
    "authors": ("list", "Authors | Women Shaping Futures", "Meet the editors and writers behind Women Shaping Futures."),
    "opportunities": (
        "list",
        "Opportunities | Women Shaping Futures",
        "Scholarships, fellowships, grants, and accelerators for women worldwide.",
    ),
    "jobs": (
        "list",
        "Jobs for Women | Women Shaping Futures",
        "Curated job openings from employers committed to hiring and advancing women, worldwide and remote.",
    ),
    "events": (
        "list",
        "Events | Women Shaping Futures",
        "WSF conferences, webinars, workshops, and networking events — in person and online, worldwide.",
    ),
    "resources": (
        "list",
        "Resource Library | Women Shaping Futures",
        "Guides, workbooks, templates, and toolkits to help you plan your career, negotiate pay, and grow a business — free, WSF Circle, and premium.",
    ),
    "circle": (
        "list",
        "WSF Circle | Women Shaping Futures",
        "WSF Circle is the premium membership experience for women who want deeper access to learning, career resources, curated opportunities, events and community experiences.",
    ),
    "newsletter": (
        "list",
        "WSF Weekly Newsletter | Women Shaping Futures",
        "Subscribe to WSF Weekly for stories, jobs, and opportunities delivered every Thursday.",
    ),
    "search": (
        "noindex",
        "Search | Women Shaping Futures",
        "Search stories, people, jobs, opportunities, events, resources, and more on Women Shaping Futures.",
        "noindex, follow",
    ),
    "login": ("noindex", "Login | Women Shaping Futures", "Sign in to your Women Shaping Futures account.", "noindex, follow"),
    "register": (
        "noindex",
        "Create Your WSF Account | Women Shaping Futures",
        "Create a free Women Shaping Futures account to save your profile and explore the WSF community.",
        "noindex, follow",
    ),
    "forgot-password": (
        "noindex",
        "Forgot Password | Women Shaping Futures",
        "Request a password reset link for your Women Shaping Futures account.",
        "noindex, nofollow",
    ),
    "change-password": ("noindex", "Change Password | Women Shaping Futures", None, "noindex, nofollow"),
    "reset-password": ("noindex", "Reset Password | Women Shaping Futures", None, "noindex, nofollow"),
    "account": ("noindex", "My Account | Women Shaping Futures", None, "noindex, nofollow"),
    "account/profile": ("noindex", "Profile | Women Shaping Futures", None, "noindex, nofollow"),
    "account/saved": ("noindex", "Saved for later | Women Shaping Futures", None, "noindex, nofollow"),
    "account/events": ("noindex", "My Events | Women Shaping Futures", None, "noindex, nofollow"),
    "account/learning": ("noindex", "My Learning | Women Shaping Futures", None, "noindex, nofollow"),
    "account/community": ("noindex", "My Community | Women Shaping Futures", None, "noindex, nofollow"),
    "account/membership": ("noindex", "WSF Circle | Women Shaping Futures", None, "noindex, nofollow"),
    "account/security": ("noindex", "Security | Women Shaping Futures", None, "noindex, nofollow"),
    # Real, functional payment-callback landing pages — never indexable
    # (there is nothing for a search engine to index, and the raw HTML
    # must never carry a payment/transaction reference, which only ever
    # lives in the query string: Flask's <path:subpath> converter never
    # captures it, so it can't leak into `subpath`-derived title/
    # canonical even by accident). Title only, no description, no
    # canonical-worthy content, no site-wide structured data.
    "resources/checkout/callback": ("noindex", "Resource Payment | Women Shaping Futures", None, "noindex, nofollow"),
    "circle/checkout/callback": ("noindex", "WSF Circle Payment | Women Shaping Futures", None, "noindex, nofollow"),
}
for _key in _SYSTEM_PAGE_KEYS:
    _STATIC_ROUTES[_key] = ("page", _key)
del _key


def _render_system_page_shell(page_key, public_site_url, site_identity, site_name):
    page = Page.query.filter_by(key=page_key, status="published").first()
    canonical = f"{public_site_url.rstrip('/')}/{page_key}"
    default_title = site_identity.get("seo_default_title") or "Women Shaping Futures"
    default_description = site_identity.get("seo_default_description")

    if page is None:
        # No seeded row yet (or it's draft/archived) — never leak that,
        # just fall back to the same global default every other
        # not-yet-customized page already uses. Still a real, always-
        # linked top-level route, so it stays 200, never 404.
        title, description, robots = default_title, default_description, "index, follow"
        image_url, image_alt = _resolve_social_image(None, None, site_identity, public_site_url)
    else:
        seo = page.seo or {}
        robots = seo.get("robots") or "index, follow"
        if page_key == "contact":
            # ContactPage.jsx has no page.title/subtitle fallback of its
            # own — a blank seo.title/description falls straight through
            # to the global default, exactly like this.
            title = seo.get("title") or default_title
            description = seo.get("description") or default_description
            fallback_media = None
        else:
            # AboutPage.jsx/LegalPage.jsx both fall back to page.title/
            # page.subtitle before the global default.
            title = seo.get("title") or page.title
            description = seo.get("description") or page.subtitle
            fallback_media = page.hero_media if page_key == "about" else None
        image_url, image_alt = _resolve_social_image(None, fallback_media, site_identity, public_site_url)

    html_doc = _read_index_html()
    html_doc = _apply_base_seo(
        html_doc,
        title=title,
        description=description,
        canonical=canonical,
        robots=robots,
        og_type="website",
        image_url=image_url,
        image_alt=image_alt,
        site_name=site_name,
    )
    html_doc = _set_structured_data(html_doc, "data-site-structured-data", _build_site_json_ld(site_identity, public_site_url))
    # Breadcrumb uses the real public CMS page display title (page.title
    # — the same string AboutPage.jsx/ContactPage.jsx/LegalPage.jsx show
    # as their H1), never `title` (the resolved <title>/SEO metadata
    # above, which may be an editor-set SEO title or the global default)
    # — "Home > Page title" means the page's own display title, not its
    # meta title. When no published Page row exists, there is no real
    # display title to show, so this falls back to the same safe
    # `title` (== default_title) the metadata above already uses in
    # that case, never a fabricated one.
    breadcrumb_name = page.title if page is not None else title
    breadcrumb = _build_breadcrumb_json_ld(public_site_url, [(breadcrumb_name, canonical)])
    html_doc = _set_structured_data(html_doc, "data-breadcrumb-structured-data", breadcrumb)
    return _html_response(html_doc)


def _render_static_route(subpath, entry):
    kind = entry[0]
    if kind == "passthrough":
        return render_generic_shell()

    public_site_url = current_app.config["PUBLIC_SITE_URL"]
    site_identity = get_site_identity_resolved()
    site_name = site_identity.get("site_name") or "Women Shaping Futures"

    if kind == "page":
        return _render_system_page_shell(entry[1], public_site_url, site_identity, site_name)

    canonical = f"{public_site_url.rstrip('/')}/{subpath}"
    html_doc = _read_index_html()

    if kind == "list":
        _, title, description = entry
        html_doc = _apply_base_seo(
            html_doc,
            title=title,
            description=description,
            canonical=canonical,
            robots="index, follow",
            og_type="website",
            image_url=None,
            image_alt=None,
            site_name=site_name,
        )
        html_doc = _set_structured_data(html_doc, "data-site-structured-data", _build_site_json_ld(site_identity, public_site_url))
        breadcrumb_label = _LIST_PAGE_BREADCRUMB_LABELS.get(subpath)
        if breadcrumb_label is not None:
            breadcrumb = _build_breadcrumb_json_ld(public_site_url, [(breadcrumb_label, canonical)])
            html_doc = _set_structured_data(html_doc, "data-breadcrumb-structured-data", breadcrumb)
        return _html_response(html_doc)

    # kind == "noindex" — a private/auth/utility page. No site-wide
    # structured data: it isn't meant to be indexed anyway.
    _, title, description, robots = entry
    html_doc = _apply_base_seo(
        html_doc,
        title=title,
        description=description,
        canonical=canonical,
        robots=robots,
        og_type="website",
        image_url=None,
        image_alt=None,
        site_name=site_name,
    )
    return _html_response(html_doc)


def _render_entity_detail(prefix, slug):
    lookup, build_meta, section_label, display_name = _ENTITY_DETAIL_PREFIXES[prefix]
    entity = lookup(slug)
    if entity is None:
        # WSF SEO Phase 2B: the live entity always wins over redirect
        # history — this fallback only runs once the lookup above has
        # already missed. Scoped by entity_type so a Job redirect can
        # never answer for an Event (or anything else) whose old slug
        # happens to be the same text — see
        # app/services/entity_redirects.py. The redirect always points
        # at the entity's current slug, which independently re-enforces
        # its own normal visibility on the next request (this fallback
        # never bypasses that), so only a redirect actually created by
        # a publicly-visible-before-and-after slug change is ever
        # followed here.
        redirect_row = EntityRedirect.query.filter_by(
            entity_type=_ENTITY_TYPE_BY_PREFIX[prefix], from_slug=slug
        ).first()
        if redirect_row is not None:
            return redirect(f"/{prefix}/{redirect_row.to_slug}", code=301)
        return _render_404_shell()

    public_site_url = current_app.config["PUBLIC_SITE_URL"]
    site_identity = get_site_identity_resolved()
    site_name = site_identity.get("site_name") or "Women Shaping Futures"
    meta = build_meta(entity, public_site_url, site_identity)

    html_doc = _read_index_html()
    html_doc = _apply_base_seo(
        html_doc,
        title=meta["title"],
        description=meta["description"],
        canonical=meta["canonical"],
        robots=meta["robots"],
        og_type="website",
        image_url=meta["image_url"],
        image_alt=meta["image_alt"],
        site_name=site_name,
    )
    html_doc = _set_structured_data(html_doc, "data-site-structured-data", _build_site_json_ld(site_identity, public_site_url))

    breadcrumb = _build_breadcrumb_json_ld(
        public_site_url,
        [(section_label, f"{public_site_url.rstrip('/')}/{prefix}"), (display_name(entity), meta["canonical"])],
    )
    html_doc = _set_structured_data(html_doc, "data-breadcrumb-structured-data", breadcrumb)

    entity_builder = _ENTITY_STRUCTURED_DATA_BUILDERS.get(prefix)
    if entity_builder is not None:
        attr_name, build_entity_data = entity_builder
        entity_data = build_entity_data(entity, meta["canonical"], public_site_url, site_name)
        html_doc = _set_structured_data(html_doc, attr_name, entity_data)

    image_preload = _ENTITY_IMAGE_PRELOAD.get(prefix)
    if image_preload is not None:
        get_media, sizes = image_preload
        html_doc = _set_image_preload(html_doc, media=get_media(entity), public_site_url=public_site_url, sizes=sizes)

    return _html_response(html_doc)


def is_reserved_path(subpath):
    return subpath in _RESERVED_EXACT or any(subpath.startswith(p) for p in _RESERVED_PREFIXES)


def resolve_spa_response(subpath):
    """The one entry point app/__init__.py's catch-all route calls for
    any path Nginx's own static-file try_files would have missed in
    production. Route classes, checked in this order:

      1. reserved (api/, assets/, media/, sitemap.xml, robots.txt) -> 404
         (unchanged from Phase 0 — these already have their own routes)
      2. legacy /articles/<slug> -> 301 to the flat URL (unchanged)
      3. /admin and /admin/* -> untouched generic shell, 200 (unchanged
         behavior, now made explicit rather than merely "whatever's left
         over" — these are legitimate, auth-gated SPA routes)
      4. an exact match in _STATIC_ROUTES (every other known static/
         list/landing/utility route this phase covers) -> that route's
         own server-rendered metadata, 200
      5. a known entity-detail pattern (/<prefix>/<slug> where prefix is
         one of the 8 in-scope types) -> that entity's real metadata if
         it resolves and is publicly visible, else a real 404 (Phase
         1's fix for the soft-404 the audit found — "nonexistent public
         entity-detail route" no longer returns the generic shell)
      6. a first segment this phase deliberately doesn't enhance
         (_UNENHANCED_PREFIXES: organizations/directory/learning/shop/
         newsletter) -> untouched generic shell, 200 (unchanged —
         expanding these is future work, not touched here)
      7. a single remaining segment -> the EXISTING, unchanged Article
         flow: a published Article at that slug -> its full server SEO;
         a Redirect row for that slug -> 301; otherwise a real 404 (this
         is the one behavior change to the Article-adjacent path: an
         unknown single-segment slug used to fall through to the same
         200 generic shell every other unmatched path got — it's now a
         real 404 with raw noindex metadata, matching every other
         "doesn't exist" case this phase fixes. A DRAFT or ARCHIVED
         article's slug reaches this same 404 branch too — from a public
         visitor's perspective it is indistinguishable from "doesn't
         exist", and its title/excerpt must never be leaked either way)
      8. anything else (a multi-segment path matching none of the
         above) -> genuinely unknown -> the same real 404

    Reserved-path and legacy-article-redirect behavior, and every single
    already-working SPA route's status code, are unchanged. The ONLY new
    404s this introduces are: (a) a known entity-detail slug that
    doesn't resolve, and (b) a path that was never a real route to begin
    with (including an unknown/draft/archived single-segment slug).
    """
    if is_reserved_path(subpath):
        abort(404)

    segments = subpath.split("/")

    if len(segments) == 2 and segments[0] == "articles" and segments[1]:
        # Legacy shape — unconditional rewrite, exactly matching
        # frontend/src/routes/AppRoutes.jsx's ArticleLegacyRedirect
        # (<Navigate to={`/${slug}`} replace />, regardless of whether
        # that slug is still valid) — never resolved through Redirect
        # here either.
        return redirect(f"/{segments[1]}", code=301)

    if subpath == "admin" or subpath.startswith("admin/"):
        return render_generic_shell()

    static_entry = _STATIC_ROUTES.get(subpath)
    if static_entry is not None:
        return _render_static_route(subpath, static_entry)

    if len(segments) == 2 and segments[0] in _ENTITY_DETAIL_PREFIXES and segments[1]:
        return _render_entity_detail(segments[0], segments[1])

    if segments[0] in _UNENHANCED_PREFIXES:
        return render_generic_shell()

    if len(segments) == 1 and segments[0]:
        slug = segments[0]
        article = Article.query.filter_by(slug=slug, status="published").first()
        if article is not None:
            return render_article_shell(article)

        redirect_row = Redirect.query.filter_by(from_slug=slug).first()
        if redirect_row is not None:
            return redirect(f"/{redirect_row.to_slug}", code=301)

        return _render_404_shell()

    return _render_404_shell()
