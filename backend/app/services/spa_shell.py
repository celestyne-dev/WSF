"""Module 12B: crawler-readable initial HTML for public ARTICLE pages,
served through a Flask SPA-shell fallback (see app/__init__.py's
catch-all route, and deploy/nginx/*.conf.example's `@spa_shell` named
location that proxies a static-file miss here in production).

Reads the CURRENT built frontend/dist/index.html fresh on every request
(see config.SPA_INDEX_PATH — never cached across requests, so a later
`npm run build` is picked up with no backend restart or code change) and
returns that SAME file, byte-for-byte, for every route except a flat
/<slug> that matches a PUBLISHED Article — there, it injects the exact
title/description/canonical/robots/OpenGraph/Twitter metadata and
Article JSON-LD that ArticlePage's own useSeo()/useArticleStructuredData()
hooks would apply client-side (see frontend/src/hooks/useSeo.js and
frontend/src/utils/articleStructuredData.js), so a crawler that never
executes JS ends up seeing the same metadata a real visitor's browser
does. Every visitor — human or crawler — receives this SAME initial
HTML; nothing here ever special-cases a request by User-Agent.

Deliberately NOT Next.js, a Node SSR server, or a separate prerender
service — this stays a small, stdlib-only (no HTML-parsing dependency)
rewrite of a handful of <head> tags over Vite's own static build output.
"""
import json
import re
from html import escape as _escape

from flask import Response, abort, current_app, redirect

from app.extensions import db
from app.models.article import Article, Redirect
from app.models.media import Media
from app.services.site_settings import get_site_identity_resolved

_HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
_TITLE_RE = re.compile(r"<title\b[^>]*>.*?</title>", re.IGNORECASE | re.DOTALL)
_CANONICAL_RE = re.compile(r'<link\s+(?:[^>]*?\s)?rel=["\']canonical["\'][^>]*>', re.IGNORECASE)
_STRUCTURED_DATA_RE = re.compile(
    r"<script\b[^>]*data-article-structured-data[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL
)

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


def _set_structured_data(html_doc, data):
    html_doc = _STRUCTURED_DATA_RE.sub("", html_doc)
    if data:
        tag = f'<script type="application/ld+json" data-article-structured-data="true">{_safe_json_ld(data)}</script>'
        html_doc = _insert_before_head_close(html_doc, tag + "\n")
    return html_doc


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
    isn't a published Article's own flat URL (including a slug that's
    draft/scheduled/archived/unknown) gets exactly this, same as Nginx's
    own previous `try_files ... /index.html` fallback already did.
    """
    return _html_response(_read_index_html())


def _resolve_social_image(article, site_identity, public_site_url):
    """Mirrors ArticlePage.jsx's own hasExplicitOgImage/socialImagePath/
    socialImageAlt priority exactly: an explicit SEO/OG image's alt text
    is used only with that SAME image, never cross-matched with the hero
    image's alt — and the global Site Settings default image (used only
    when NEITHER an explicit OG image NOR a hero image exists) never
    carries an alt either, matching useSeo.js's own resolvedImage
    computation, which only ever pulls a URL from seoDefaults.defaultOgImage,
    never its alt text (even though the underlying Media row has one).

    The explicit article OG image and the hero image both use the
    original/public_url straight off the Media row — unchanged from
    before. Only the GLOBAL default image follows useSeo.js's own
    resolveMediaImage(..., {variant: 'large'}) call for
    seoDefaults.defaultOgImage: the generated `large` MediaVariant when
    one exists, falling back to public_url when it doesn't (e.g. an
    older upload from before variant generation existed).
    """
    og_image_media_id = (article.seo or {}).get("ogImageMediaId")
    if og_image_media_id:
        media = db.session.get(Media, og_image_media_id)
        if media is not None:
            return _absolute_url(media.public_url, public_site_url), media.alt_text or None

    if article.hero_media is not None:
        return _absolute_url(article.hero_media.public_url, public_site_url), article.hero_media.alt_text or None

    default_image = site_identity.get("og_image")
    if default_image is not None:
        image_path = default_image.variant_url("large") or default_image.public_url
        return _absolute_url(image_path, public_site_url), None

    return None, None


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
    status itself.
    """
    public_site_url = current_app.config["PUBLIC_SITE_URL"]
    site_identity = get_site_identity_resolved()
    seo = article.seo or {}

    title = seo.get("title") or article.title or site_identity.get("seo_default_title")
    meta_description = seo.get("description") or article.excerpt or site_identity.get("seo_default_description")
    canonical_url = seo.get("canonical") or f"{public_site_url.rstrip('/')}/{article.slug}"
    robots = seo.get("robots") or "index, follow"
    image_url, image_alt = _resolve_social_image(article, site_identity, public_site_url)

    html_doc = _read_index_html()
    html_doc = _set_title(html_doc, title)
    html_doc = _set_meta(html_doc, "name", "description", meta_description)
    html_doc = _set_meta(html_doc, "name", "robots", robots)
    html_doc = _set_canonical(html_doc, canonical_url)
    html_doc = _set_meta(html_doc, "property", "og:title", title)
    html_doc = _set_meta(html_doc, "property", "og:description", meta_description)
    html_doc = _set_meta(html_doc, "property", "og:url", canonical_url)
    html_doc = _set_meta(html_doc, "property", "og:type", "article")
    html_doc = _set_meta(html_doc, "property", "og:image", image_url)
    html_doc = _set_meta(html_doc, "property", "og:image:alt", image_alt if image_url else None)
    html_doc = _set_meta(html_doc, "name", "twitter:card", "summary_large_image")
    html_doc = _set_meta(html_doc, "name", "twitter:title", title)
    html_doc = _set_meta(html_doc, "name", "twitter:description", meta_description)
    html_doc = _set_meta(html_doc, "name", "twitter:image", image_url)
    html_doc = _set_meta(html_doc, "name", "twitter:image:alt", image_alt if image_url else None)

    structured_data = _build_article_json_ld(article, canonical_url, image_url, site_identity, public_site_url)
    html_doc = _set_structured_data(html_doc, structured_data)

    return _html_response(html_doc)


def is_reserved_path(subpath):
    return subpath in _RESERVED_EXACT or any(subpath.startswith(p) for p in _RESERVED_PREFIXES)


def resolve_spa_response(subpath):
    """The one entry point app/__init__.py's catch-all route calls for
    any path Nginx's own static-file try_files would have missed in
    production. See this module's own docstring for the overall
    architecture and behavior.
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

    if len(segments) == 1 and segments[0]:
        slug = segments[0]
        article = Article.query.filter_by(slug=slug, status="published").first()
        if article is not None:
            return render_article_shell(article)

        redirect_row = Redirect.query.filter_by(from_slug=slug).first()
        if redirect_row is not None:
            return redirect(f"/{redirect_row.to_slug}", code=301)

    return render_generic_shell()
