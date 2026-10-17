"""Module 12B — the Flask SPA-shell fallback (app/__init__.py's catch-all
routes, delegating to app/services/spa_shell.py). Covers: a published
Article's flat /<slug> route gets crawler-readable metadata injected
into the SAME built index.html every other route also receives; a CMS
canonical override; the 3-tier social image priority (explicit SEO image
-> hero image -> global default) and its alt-text fidelity; that no
draft/unpublished article's metadata is ever exposed; the legacy
/articles/<slug> and Redirect 301s; HTML/JSON-LD escaping safety; no
duplicate managed tags; the generic shell for unknown routes; and that
reserved prefixes (api/, assets/, media/, sitemap.xml, robots.txt) are
never swallowed by the catch-all.
"""
import os
import re

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
DUPLICATES_FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index_duplicates.html")


def _use_fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _use_duplicates_fixture_index(app):
    # A baseline index.html that already carries two of every managed
    # tag (two <title>s, two canonicals, two of each OG/Twitter tag, two
    # structured-data scripts) — proves dedup collapses pre-existing
    # duplicates, not just the clean single-tag fixture used elsewhere.
    app.config["SPA_INDEX_PATH"] = DUPLICATES_FIXTURE_INDEX_PATH


def _make_author(app, slug="wsf-editorial", name="WSF Editorial", status="active"):
    from app.models.people import Author

    with app.app_context():
        author = Author(slug=slug, name=name, status=status)
        db.session.add(author)
        db.session.commit()
        return author.id


def _make_media(app, alt_text="A group of women at a conference.", public_url="/media/originals/hero.jpg"):
    from app.models.media import Media

    with app.app_context():
        media = Media(
            original_filename="hero.jpg",
            stored_filename="hero.jpg",
            file_path="/tmp/hero.jpg",
            public_url=public_url,
            mime_type="image/jpeg",
            alt_text=alt_text,
        )
        db.session.add(media)
        db.session.commit()
        return media.id


def _add_variant(app, media_id, variant_name, public_url):
    from app.models.media import MediaVariant

    with app.app_context():
        variant = MediaVariant(
            media_id=media_id,
            variant=variant_name,
            file_path=f"/tmp/{variant_name}.webp",
            public_url=public_url,
        )
        db.session.add(variant)
        db.session.commit()
        return variant.id


def _make_article(app, slug, title="A Story", status="published", author_id=None, **overrides):
    from app.models.article import Article

    with app.app_context():
        article = Article(
            slug=slug,
            title=title,
            status=status,
            author_id=author_id or _make_author(app),
            publish_date=db.func.now(),
            content=[],
            **overrides,
        )
        db.session.add(article)
        db.session.commit()
        return article.id


def _make_redirect(app, from_slug, to_slug):
    from app.models.article import Redirect

    with app.app_context():
        redirect_row = Redirect(from_slug=from_slug, to_slug=to_slug)
        db.session.add(redirect_row)
        db.session.commit()
        return redirect_row.id


def _set_site_identity(app, **overrides):
    from app.services.site_settings import save_site_identity

    with app.app_context():
        save_site_identity({"site_name": "Women Shaping Futures", **overrides})
        db.session.commit()


def _count(pattern, html):
    return len(re.findall(pattern, html, re.IGNORECASE))


def _meta_content(html, attr, key):
    match = re.search(rf'<meta\s+(?:[^>]*?\s)?{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(rf'<meta\s+content=["\']([^"\']*)["\']\s+{attr}=["\']{re.escape(key)}["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _canonical_href(html):
    match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _structured_data_json(html):
    return _structured_data_json_by_attr(html, "data-article-structured-data")


def _structured_data_json_by_attr(html, attr_name):
    import json

    match = re.search(rf"<script\b[^>]*{re.escape(attr_name)}[^>]*>(.*?)</script>", html, re.IGNORECASE | re.DOTALL)
    assert match is not None, f"expected a {attr_name} script tag"
    return json.loads(match.group(1))


class TestPublishedArticleShell:
    def test_published_article_has_full_metadata_in_raw_html(self, client, app):
        _use_fixture_index(app)
        author_id = _make_author(app, slug="amara-okafor", name="Amara Okafor")
        _make_article(
            app,
            slug="rising-voices",
            title="Rising Voices",
            excerpt="Stories from women reshaping their industries.",
            author_id=author_id,
        )

        resp = client.get("/rising-voices")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        assert "<title>Rising Voices</title>" in html
        assert _meta_content(html, "name", "description") == "Stories from women reshaping their industries."
        assert _canonical_href(html) == "https://womenshapingfutures.org/rising-voices"
        assert _meta_content(html, "name", "robots") == "index, follow"
        assert _meta_content(html, "property", "og:type") == "article"
        assert _meta_content(html, "property", "og:title") == "Rising Voices"
        assert _meta_content(html, "property", "og:description") == "Stories from women reshaping their industries."
        assert _meta_content(html, "property", "og:url") == "https://womenshapingfutures.org/rising-voices"
        assert _meta_content(html, "name", "twitter:card") == "summary_large_image"
        assert _meta_content(html, "name", "twitter:title") == "Rising Voices"
        assert _meta_content(html, "name", "twitter:description") == "Stories from women reshaping their industries."

        data = _structured_data_json(html)
        assert data["@type"] == "Article"
        assert data["headline"] == "Rising Voices"
        assert data["description"] == "Stories from women reshaping their industries."
        assert data["url"] == "https://womenshapingfutures.org/rising-voices"
        assert data["mainEntityOfPage"]["@id"] == "https://womenshapingfutures.org/rising-voices"
        assert data["author"]["name"] == "Amara Okafor"
        assert data["publisher"]["name"] == "Women Shaping Futures"

    def test_article_also_carries_sitewide_website_and_organization_json_ld(self, client, app):
        # The Article page's own JSON-LD (data-article-structured-data)
        # must never be replaced or merged away — the site-wide
        # WebSite+Organization block (data-site-structured-data) is
        # added alongside it, under its own attribute, exactly like
        # every other server-rendered page gets.
        _use_fixture_index(app)
        _make_article(app, slug="both-schemas-story", title="Both Schemas Story", excerpt="Has both JSON-LD blocks.")

        resp = client.get("/both-schemas-story")
        html = resp.get_data(as_text=True)

        assert _count(r"data-article-structured-data", html) == 1
        assert _count(r"data-site-structured-data", html) == 1

        article_data = _structured_data_json_by_attr(html, "data-article-structured-data")
        assert article_data["@type"] == "Article"
        assert article_data["headline"] == "Both Schemas Story"

        site_data = _structured_data_json_by_attr(html, "data-site-structured-data")
        site_types = {d["@type"] for d in site_data}
        assert site_types == {"WebSite", "Organization"}
        for d in site_data:
            assert d["name"] == "Women Shaping Futures"

    def test_cms_canonical_override_is_used_everywhere(self, client, app):
        _use_fixture_index(app)
        _make_article(
            app,
            slug="override-story",
            title="Override Story",
            seo={"canonical": "https://womenshapingfutures.org/features/override-story"},
        )

        resp = client.get("/override-story")
        html = resp.get_data(as_text=True)

        expected = "https://womenshapingfutures.org/features/override-story"
        assert _canonical_href(html) == expected
        assert _meta_content(html, "property", "og:url") == expected
        data = _structured_data_json(html)
        assert data["url"] == expected
        assert data["mainEntityOfPage"]["@id"] == expected


class TestSocialImagePriority:
    def test_explicit_og_image_wins_with_its_own_alt(self, client, app):
        _use_fixture_index(app)
        hero_media_id = _make_media(app, alt_text="Hero alt text — must not be used.", public_url="/media/originals/hero.jpg")
        explicit_media_id = _make_media(app, alt_text="Explicit OG image alt text.", public_url="/media/originals/og.jpg")
        _make_article(
            app,
            slug="explicit-image-story",
            title="Explicit Image Story",
            hero_media_id=hero_media_id,
            seo={"ogImageMediaId": explicit_media_id},
        )

        resp = client.get("/explicit-image-story")
        html = resp.get_data(as_text=True)

        assert _meta_content(html, "property", "og:image") == "https://womenshapingfutures.org/media/originals/og.jpg"
        assert _meta_content(html, "property", "og:image:alt") == "Explicit OG image alt text."
        assert _meta_content(html, "name", "twitter:image") == "https://womenshapingfutures.org/media/originals/og.jpg"
        assert _meta_content(html, "name", "twitter:image:alt") == "Explicit OG image alt text."
        data = _structured_data_json(html)
        assert data["image"] == "https://womenshapingfutures.org/media/originals/og.jpg"

    def test_hero_image_used_when_no_explicit_og_image(self, client, app):
        _use_fixture_index(app)
        hero_media_id = _make_media(app, alt_text="Hero image alt text.", public_url="/media/originals/hero2.jpg")
        _make_article(
            app,
            slug="hero-fallback-story",
            title="Hero Fallback Story",
            hero_media_id=hero_media_id,
        )

        resp = client.get("/hero-fallback-story")
        html = resp.get_data(as_text=True)

        assert _meta_content(html, "property", "og:image") == "https://womenshapingfutures.org/media/originals/hero2.jpg"
        assert _meta_content(html, "property", "og:image:alt") == "Hero image alt text."

    def test_global_default_og_image_used_with_no_alt(self, client, app):
        _use_fixture_index(app)
        default_media_id = _make_media(app, alt_text="This alt must never surface.", public_url="/media/originals/default-og.jpg")
        _set_site_identity(app, og_image_media_id=default_media_id)
        _make_article(app, slug="no-image-story", title="No Image Story")

        resp = client.get("/no-image-story")
        html = resp.get_data(as_text=True)

        assert _meta_content(html, "property", "og:image") == "https://womenshapingfutures.org/media/originals/default-og.jpg"
        # Faithfully mirrors useSeo.js's own resolvedImage gap: the global
        # default image never carries alt text, even though the underlying
        # Media row has one.
        assert "og:image:alt" not in html
        assert "twitter:image:alt" not in html
        # No `large` MediaVariant row exists for this Media — proves the
        # safe fallback to the original public_url when one is unavailable.

    def test_global_default_og_image_uses_large_variant_when_available(self, client, app):
        _use_fixture_index(app)
        default_media_id = _make_media(app, alt_text="Must never surface.", public_url="/media/originals/default-og.jpg")
        _add_variant(app, default_media_id, "large", "/media/large/default-og.webp")
        _add_variant(app, default_media_id, "thumbnail", "/media/thumbnail/default-og.webp")
        _set_site_identity(app, og_image_media_id=default_media_id)
        _make_article(app, slug="variant-og-story", title="Variant OG Story")

        resp = client.get("/variant-og-story")
        html = resp.get_data(as_text=True)

        # Uses the generated `large` variant, not the original public_url
        # and not any other variant that happens to exist.
        assert _meta_content(html, "property", "og:image") == "https://womenshapingfutures.org/media/large/default-og.webp"
        assert _meta_content(html, "name", "twitter:image") == "https://womenshapingfutures.org/media/large/default-og.webp"
        data = _structured_data_json(html)
        assert data["image"] == "https://womenshapingfutures.org/media/large/default-og.webp"

    def test_explicit_og_image_ignores_variants_and_uses_public_url(self, client, app):
        # Explicit article OG-image behavior is unchanged: it must keep
        # using the Media row's own public_url even when a `large`
        # variant also exists for it.
        _use_fixture_index(app)
        explicit_media_id = _make_media(app, alt_text="Explicit alt.", public_url="/media/originals/og.jpg")
        _add_variant(app, explicit_media_id, "large", "/media/large/og.webp")
        _make_article(
            app,
            slug="explicit-image-with-variant-story",
            title="Explicit Image With Variant",
            seo={"ogImageMediaId": explicit_media_id},
        )

        resp = client.get("/explicit-image-with-variant-story")
        html = resp.get_data(as_text=True)
        assert _meta_content(html, "property", "og:image") == "https://womenshapingfutures.org/media/originals/og.jpg"

    def test_hero_image_ignores_variants_and_uses_public_url(self, client, app):
        # Article hero-image behavior is unchanged too.
        _use_fixture_index(app)
        hero_media_id = _make_media(app, alt_text="Hero alt.", public_url="/media/originals/hero3.jpg")
        _add_variant(app, hero_media_id, "large", "/media/large/hero3.webp")
        _make_article(app, slug="hero-with-variant-story", title="Hero With Variant", hero_media_id=hero_media_id)

        resp = client.get("/hero-with-variant-story")
        html = resp.get_data(as_text=True)
        assert _meta_content(html, "property", "og:image") == "https://womenshapingfutures.org/media/originals/hero3.jpg"


class TestPublisherLogoVariant:
    def test_publisher_logo_uses_card_variant_when_available(self, client, app):
        _use_fixture_index(app)
        logo_media_id = _make_media(app, alt_text="WSF logo.", public_url="/media/originals/logo.png")
        _add_variant(app, logo_media_id, "card", "/media/card/logo.webp")
        _add_variant(app, logo_media_id, "large", "/media/large/logo.webp")
        _set_site_identity(app, logo_media_id=logo_media_id)
        _make_article(app, slug="logo-card-variant-story", title="Logo Card Variant Story")

        resp = client.get("/logo-card-variant-story")
        html = resp.get_data(as_text=True)
        data = _structured_data_json(html)

        # Uses the generated `card` variant, not the original public_url
        # and not any other variant that happens to exist.
        assert data["publisher"]["logo"]["url"] == "https://womenshapingfutures.org/media/card/logo.webp"

    def test_publisher_logo_falls_back_to_public_url_without_card_variant(self, client, app):
        _use_fixture_index(app)
        logo_media_id = _make_media(app, alt_text="WSF logo.", public_url="/media/originals/logo2.png")
        _set_site_identity(app, logo_media_id=logo_media_id)
        _make_article(app, slug="logo-no-variant-story", title="Logo No Variant Story")

        resp = client.get("/logo-no-variant-story")
        html = resp.get_data(as_text=True)
        data = _structured_data_json(html)

        # No `card` MediaVariant row exists — falls back safely to the
        # Media row's own public_url.
        assert data["publisher"]["logo"]["url"] == "https://womenshapingfutures.org/media/originals/logo2.png"


class TestVisibilityAndRedirects:
    def test_draft_article_metadata_is_never_leaked(self, client, app):
        # SEO Phase 1: a draft article's slug is, to a public visitor,
        # indistinguishable from "doesn't exist" — it now gets the same
        # real 404 an unknown slug gets (see
        # test_unknown_slug_now_returns_a_real_404_with_noindex_metadata),
        # not the old 200 soft-404. The content-safety guarantee this
        # test exists for — title/excerpt never leaked — is unchanged.
        _use_fixture_index(app)
        _make_article(
            app,
            slug="still-a-draft",
            title="Secret Draft Title",
            status="draft",
            excerpt="This must never reach a crawler.",
        )

        resp = client.get("/still-a-draft")
        assert resp.status_code == 404
        html = resp.get_data(as_text=True)

        assert "Secret Draft Title" not in html
        assert "This must never reach a crawler." not in html
        assert "data-article-structured-data" not in html
        assert "<title>Page Not Found | Women Shaping Futures</title>" in html

    def test_archived_article_metadata_is_never_leaked(self, client, app):
        _use_fixture_index(app)
        _make_article(app, slug="old-news", title="Archived Title", status="archived")

        resp = client.get("/old-news")
        assert resp.status_code == 404
        html = resp.get_data(as_text=True)
        assert "Archived Title" not in html

    def test_article_slug_redirect_returns_301_to_new_flat_url(self, client, app):
        _use_fixture_index(app)
        _make_redirect(app, from_slug="old-slug", to_slug="new-slug")

        resp = client.get("/old-slug")
        assert resp.status_code == 301
        assert resp.headers["Location"] == "/new-slug"

    def test_legacy_articles_prefix_redirects_301_to_flat_url(self, client, app):
        _use_fixture_index(app)
        _make_article(app, slug="legacy-story", title="Legacy Story")

        resp = client.get("/articles/legacy-story")
        assert resp.status_code == 301
        assert resp.headers["Location"] == "/legacy-story"

    def test_legacy_articles_prefix_redirects_even_for_unknown_slug(self, client, app):
        # Matches the frontend's own ArticleLegacyRedirect exactly: a pure
        # URL-shape rewrite, no DB lookup.
        _use_fixture_index(app)
        resp = client.get("/articles/whatever-this-is")
        assert resp.status_code == 301
        assert resp.headers["Location"] == "/whatever-this-is"


class TestEscapingSafety:
    def test_special_characters_are_html_escaped_and_json_ld_is_breakout_safe(self, client, app):
        _use_fixture_index(app)
        dangerous_title = 'Breaking <script>alert(1)</script> & "Quotes"'
        dangerous_excerpt = 'Ends with </script><img src=x onerror=alert(1)>'
        _make_article(
            app,
            slug="dangerous-story",
            title=dangerous_title,
            excerpt=dangerous_excerpt,
        )

        resp = client.get("/dangerous-story")
        html = resp.get_data(as_text=True)

        # The raw, unescaped payload must never appear verbatim anywhere.
        assert "<script>alert(1)</script>" not in html
        assert "</script><img src=x onerror=alert(1)>" not in html

        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "&quot;Quotes&quot;" in html

        # The JSON-LD payload still parses and round-trips the real text,
        # but the serialized </script> sequence must be escaped in the
        # document so the tokenizer can't be tricked into closing the tag.
        data = _structured_data_json(html)
        assert data["headline"] == dangerous_title
        assert data["description"] == dangerous_excerpt

        match = re.search(
            r'<script\b[^>]*data-article-structured-data[^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL
        )
        raw_payload = match.group(1)
        assert "</script" not in raw_payload.lower()
        assert "<\\/script" in raw_payload.lower()


class TestNoDuplicateTags:
    def test_published_article_has_no_duplicate_managed_tags(self, client, app):
        _use_fixture_index(app)
        _make_article(app, slug="single-tags-story", title="Single Tags Story", excerpt="Only one of each tag.")

        resp = client.get("/single-tags-story")
        html = resp.get_data(as_text=True)

        assert _count(r"<title\b", html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?name=["\']description["\']', html) == 1
        assert _count(r'<link\s+rel=["\']canonical["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?property=["\']og:title["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?property=["\']og:description["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?property=["\']og:url["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?property=["\']og:type["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?name=["\']twitter:card["\']', html) == 1
        assert _count(r"data-article-structured-data", html) == 1

    def test_dedupes_pre_existing_duplicate_tags_in_baseline_index_html(self, client, app):
        # Unlike the clean fixture above, this baseline index.html already
        # has two of every managed tag before the shell ever touches it
        # (see fixtures/spa_index_duplicates.html) — proves the dedup
        # logic actually collapses real duplicates rather than merely
        # never introducing new ones.
        _use_duplicates_fixture_index(app)
        _make_article(
            app,
            slug="dedupe-story",
            title="Dedupe Story",
            excerpt="Collapsed to exactly one of each tag.",
        )

        resp = client.get("/dedupe-story")
        html = resp.get_data(as_text=True)

        assert _count(r"<title\b", html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?name=["\']description["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?name=["\']robots["\']', html) == 1
        assert _count(r'<link\s+rel=["\']canonical["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?property=["\']og:title["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?property=["\']og:description["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?property=["\']og:url["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?property=["\']og:type["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?name=["\']twitter:card["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?name=["\']twitter:title["\']', html) == 1
        assert _count(r'<meta\s+(?:[^>]*?\s)?name=["\']twitter:description["\']', html) == 1
        assert _count(r"data-article-structured-data", html) == 1

        # The single surviving tag must be the freshly injected value, not
        # either stale duplicate the baseline fixture started with.
        assert "<title>Dedupe Story</title>" in html
        assert "Old Stale Title" not in html
        assert _meta_content(html, "name", "description") == "Collapsed to exactly one of each tag."
        assert "stale duplicate" not in html
        assert _meta_content(html, "name", "robots") == "index, follow"
        assert "noindex" not in html
        assert _canonical_href(html) == "https://womenshapingfutures.org/dedupe-story"
        assert "example.com/stale" not in html
        assert _meta_content(html, "property", "og:title") == "Dedupe Story"
        assert "Stale OG Title" not in html
        assert _meta_content(html, "property", "og:type") == "article"
        assert _meta_content(html, "name", "twitter:card") == "summary_large_image"
        assert "Stale Twitter Title" not in html
        data = _structured_data_json(html)
        assert data["headline"] == "Dedupe Story"
        assert "stale" not in html


class TestGenericShellAndReservedPrefixes:
    def test_unknown_slug_now_returns_a_real_404_with_noindex_metadata(self, app, client):
        # SEO Phase 1: a single-segment slug that resolves to neither a
        # published Article nor a Redirect alias used to fall through to
        # the same 200 generic shell every other unmatched path got (the
        # soft-404 the SEO audit flagged). It now gets a real 404 with
        # raw, crawler-visible noindex metadata — see
        # spa_shell.py's resolve_spa_response()/_render_404_shell().
        _use_fixture_index(app)
        resp = client.get("/this-slug-does-not-exist")
        assert resp.status_code == 404
        html = resp.get_data(as_text=True)
        assert "<title>Page Not Found | Women Shaping Futures</title>" in html
        assert _meta_content(html, "name", "robots") == "noindex, follow"
        assert "data-article-structured-data" not in html
        assert '<link rel="canonical"' not in html

    def test_nested_spa_route_gets_generic_untouched_shell(self, client, app):
        # /admin/* is a real, auth-gated SPA route this phase leaves
        # exactly as it already behaved — never 404, never rewritten.
        _use_fixture_index(app)
        resp = client.get("/admin/articles")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>Women Shaping Futures</title>" in html
        assert "data-article-structured-data" not in html

    def test_root_path_gets_real_homepage_seo(self, client, app):
        # SEO Phase 1: the homepage now gets its own server-rendered
        # metadata (see spa_shell.py's render_homepage_shell()) instead
        # of the untouched generic shell.
        _use_fixture_index(app)
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>Women Shaping Futures — Stories, Opportunity &amp; Growth for Women Worldwide</title>" in html
        assert _canonical_href(html) == "https://womenshapingfutures.org/"
        assert _meta_content(html, "property", "og:site_name") == "Women Shaping Futures"
        assert _meta_content(html, "property", "og:type") == "website"
        data = _structured_data_json_by_attr(html, "data-site-structured-data")
        assert {d["@type"] for d in data} == {"WebSite", "Organization"}

    def test_unknown_api_path_is_not_swallowed_into_html(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/api/v1/totally-made-up-endpoint")
        assert resp.status_code == 404
        assert resp.content_type != "text/html; charset=utf-8"

    def test_bare_assets_path_is_not_swallowed_into_html(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/assets/does-not-exist.js")
        assert resp.status_code == 404

    def test_bare_media_path_is_not_swallowed_into_html(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/media/does-not-exist.jpg")
        assert resp.status_code == 404

    def test_sitemap_xml_still_served_by_its_own_route(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200
        assert resp.content_type.startswith("application/xml")

    def test_robots_txt_still_served_by_its_own_route(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/robots.txt")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/plain")
