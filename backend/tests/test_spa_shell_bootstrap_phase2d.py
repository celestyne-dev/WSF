"""WSF SEO Phase 2D — "Measured Mobile Performance Correction". Covers the
two new server-side behaviors spa_shell.py adds on top of Phase 1/2A/2C's
metadata/structured-data/preload coverage:

  - a `<script type="application/json" data-wsf-bootstrap="article">` tag
    on a published Article's flat /<slug> route, carrying the exact same
    public_article_schema() dump that Article's own GET /api/v1/articles/
    {slug} already returns to an anonymous reader (see
    _safe_public_article_payload) — so the frontend's first client-side
    fetch for that same Article can be skipped on a matching hard load
    (see frontend/src/utils/bootstrap.js, pages/ArticlePage.jsx);

  - a `<script type="application/json" data-wsf-bootstrap="homepage">` tag
    on "/", carrying the enabled HomepageModule rows (the exact same
    HomepageModuleSchema dump GET /api/v1/public/homepage already returns)
    plus, when the one possible "hero" module has a selected lead Article,
    that Article's own public_article_schema() dump too (see
    get_enabled_homepage_modules/resolve_hero_lead_article in
    services/homepage.py, store/index.js, components/home/HeroModule.jsx);

  - a homepage LCP `<link rel=preload as=image>` (previously always
    absent — see test_image_seo_phase2c.py's test_homepage_has_no_preload,
    unaffected here since it creates no homepage modules at all) for
    whichever image HomePage.jsx's Hero module would mark `priority` for
    this exact resolved state (_resolve_homepage_hero_preload).

Both bootstrap tags reuse `_redact_internal_media_fields` to strip any
nested Media's `file_path`/`stored_filename`/`uploaded_by_id` before this
same API data reaches raw, crawlable HTML — tested here directly rather
than re-testing the live (unchanged) article/homepage JSON APIs themselves.

Does not re-test anything from test_spa_shell.py, test_spa_shell_
structured_data_phase2a.py, or test_image_seo_phase2c.py — this file only
covers the two bootstrap tags and the new homepage preload behavior.
"""
import json
import os
import re

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


def _use_fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


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
            stored_filename="hero_stored_internal.jpg",
            file_path="/var/protected/media/hero_internal_path.jpg",
            public_url=public_url,
            mime_type="image/jpeg",
            alt_text=alt_text,
            uploaded_by_id=None,
        )
        db.session.add(media)
        db.session.commit()
        return media.id


def _add_variant(app, media_id, variant_name, public_url, width=None, height=None):
    from app.models.media import MediaVariant

    with app.app_context():
        variant = MediaVariant(
            media_id=media_id,
            variant=variant_name,
            file_path=f"/var/protected/{variant_name}.webp",
            public_url=public_url,
            width=width,
            height=height,
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


def _make_homepage_module(app, type="hero", enabled=True, sort_order=0, heading=None, config=None, media_id=None, **overrides):
    from app.models.cms import HomepageModule

    with app.app_context():
        module = HomepageModule(
            type=type,
            enabled=enabled,
            sort_order=sort_order,
            heading=heading,
            config=config or {},
            media_id=media_id,
            **overrides,
        )
        db.session.add(module)
        db.session.commit()
        return module.id


def _bootstrap_tags(html, bootstrap_type):
    return re.findall(
        rf'<script\b[^>]*data-wsf-bootstrap="{bootstrap_type}"[^>]*>.*?</script>', html, re.IGNORECASE | re.DOTALL
    )


def _bootstrap_json(html, bootstrap_type):
    tags = _bootstrap_tags(html, bootstrap_type)
    assert len(tags) == 1, f"expected exactly one {bootstrap_type!r} bootstrap tag, found {len(tags)}"
    match = re.search(r">(.*)</script>", tags[0], re.DOTALL)
    return json.loads(match.group(1))


def _preload_tags(html):
    return re.findall(r'<link\b[^>]*data-lcp-image-preload="true"[^>]*>', html, re.IGNORECASE)


def _attr(tag, name):
    match = re.search(rf'{name}="([^"]*)"', tag)
    return match.group(1) if match else None


class TestArticleBootstrap:
    def test_published_article_hard_load_has_bootstrap_matching_public_schema(self, client, app):
        _use_fixture_index(app)
        author_id = _make_author(app, slug="amara-okafor", name="Amara Okafor")
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "large", "/media/large/hero.webp", width=1280)
        _make_article(
            app,
            slug="rising-voices",
            title="Rising Voices",
            excerpt="Stories from women reshaping their industries.",
            author_id=author_id,
            hero_media_id=media_id,
        )

        html = client.get("/rising-voices").get_data(as_text=True)
        payload = _bootstrap_json(html, "article")

        assert payload["key"] == "rising-voices"
        data = payload["data"]
        assert data["slug"] == "rising-voices"
        assert data["title"] == "Rising Voices"
        assert data["excerpt"] == "Stories from women reshaping their industries."
        assert data["author"]["name"] == "Amara Okafor"
        assert data["hero_media"]["public_url"] == "/media/originals/hero.jpg"

    def test_article_bootstrap_excludes_ai_editorial_notes_and_workflow_fields(self, client, app):
        _use_fixture_index(app)
        _make_article(
            app,
            slug="no-internal-notes",
            title="No Internal Notes",
            ai_editorial_notes="Private editor note: drafted with AI assistance, verify quotes before next edit.",
        )

        html = client.get("/no-internal-notes").get_data(as_text=True)
        payload = _bootstrap_json(html, "article")

        assert "ai_editorial_notes" not in payload["data"]
        assert "scheduled_at" not in payload["data"]
        assert "approved_at" not in payload["data"]
        assert "approved_by" not in payload["data"]
        # Belt-and-suspenders: the private note's own text must never
        # appear anywhere in the raw HTML, bootstrap or otherwise.
        assert "Private editor note" not in html

    def test_article_bootstrap_redacts_internal_media_fields(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "large", "/media/large/hero.webp", width=1280)
        _make_article(app, slug="redacted-media-story", hero_media_id=media_id)

        html = client.get("/redacted-media-story").get_data(as_text=True)
        payload = _bootstrap_json(html, "article")

        media = payload["data"]["hero_media"]
        assert media["public_url"] == "/media/originals/hero.jpg"
        assert "file_path" not in media
        assert "stored_filename" not in media
        assert "uploaded_by_id" not in media
        # Also never leaked as raw text anywhere else on the page.
        assert "/var/protected/media/hero_internal_path.jpg" not in html
        assert "hero_stored_internal.jpg" not in html

    def test_article_bootstrap_survives_script_breakout_and_special_chars(self, client, app):
        _use_fixture_index(app)
        dangerous_title = 'Breakout</script><script>alert(1)</script> & "quoted" <tag> café'
        _make_article(app, slug="xss-safe-story", title=dangerous_title, excerpt=dangerous_title)

        resp = client.get("/xss-safe-story")
        html = resp.get_data(as_text=True)

        # A real break-out would either corrupt the regex match (giving
        # more or fewer than one tag) or make json.loads fail/round-trip
        # incorrectly — either failure mode is caught by _bootstrap_json
        # itself and by the exact equality check below.
        payload = _bootstrap_json(html, "article")
        assert payload["data"]["title"] == dangerous_title
        assert payload["data"]["excerpt"] == dangerous_title
        # The literal, unescaped sequence must never appear in the raw
        # document — only the </ -> <\/ escaped form inside the tag.
        assert "</script><script>alert(1)</script>" not in html

    def test_article_bootstrap_absent_on_login_route(self, client, app):
        _use_fixture_index(app)
        html = client.get("/login").get_data(as_text=True)
        assert _bootstrap_tags(html, "article") == []
        assert _bootstrap_tags(html, "homepage") == []

    def test_article_bootstrap_absent_for_draft_article(self, client, app):
        _use_fixture_index(app)
        _make_article(app, slug="still-drafting", title="Still Drafting Internal Title", status="draft")

        resp = client.get("/still-drafting")
        assert resp.status_code == 404
        html = resp.get_data(as_text=True)
        assert _bootstrap_tags(html, "article") == []
        assert "Still Drafting Internal Title" not in html

    def test_article_bootstrap_absent_on_legacy_redirect(self, client, app):
        _use_fixture_index(app)
        _make_redirect(app, from_slug="old-slug", to_slug="new-slug")

        resp = client.get("/old-slug")
        assert resp.status_code == 301
        html = resp.get_data(as_text=True)
        assert _bootstrap_tags(html, "article") == []

    def test_article_bootstrap_coexists_exactly_once_with_existing_metadata(self, client, app):
        # Regression: Phase 2D's bootstrap tag must never replace or
        # duplicate any of Phase 1/2A/2C's existing managed tags.
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "hero", "/media/hero/hero.webp", width=1920)
        _make_article(app, slug="both-old-and-new", title="Both Old And New", hero_media_id=media_id)

        html = client.get("/both-old-and-new").get_data(as_text=True)

        assert len(re.findall(r"data-article-structured-data", html, re.IGNORECASE)) == 1
        assert len(re.findall(r"data-site-structured-data", html, re.IGNORECASE)) == 1
        assert len(re.findall(r"data-breadcrumb-structured-data", html, re.IGNORECASE)) == 1
        assert len(_preload_tags(html)) == 1
        assert len(_bootstrap_tags(html, "article")) == 1


class TestHomepageBootstrap:
    def test_homepage_bootstrap_includes_only_enabled_modules_in_sort_order(self, client, app):
        _use_fixture_index(app)
        hero_id = _make_homepage_module(app, type="hero", enabled=True, sort_order=0, heading="Welcome")
        latest_id = _make_homepage_module(app, type="latest_stories", enabled=True, sort_order=1, config={"itemCount": 6})
        _make_homepage_module(app, type="featured_woman", enabled=False, sort_order=2)

        html = client.get("/").get_data(as_text=True)
        payload = _bootstrap_json(html, "homepage")

        module_ids = [m["id"] for m in payload["modules"]]
        assert module_ids == [hero_id, latest_id]

    def test_homepage_bootstrap_module_shape_matches_public_schema_columns(self, client, app):
        _use_fixture_index(app)
        _make_homepage_module(
            app, type="latest_stories", enabled=True, sort_order=0, heading="Latest", config={"itemCount": 6}
        )

        html = client.get("/").get_data(as_text=True)
        payload = _bootstrap_json(html, "homepage")

        module = payload["modules"][0]
        assert module["type"] == "latest_stories"
        assert module["heading"] == "Latest"
        assert module["config"] == {"itemCount": 6}
        # Never a hand-built second shape carrying nested article data —
        # HomepageModuleSchema has no such field for any module type.
        assert "articles" not in module
        assert "article" not in module

    def test_homepage_bootstrap_includes_published_lead_article(self, client, app):
        _use_fixture_index(app)
        article_id = _make_article(app, slug="lead-story", title="Lead Story", status="published")
        _make_homepage_module(app, type="hero", enabled=True, heading="Welcome", config={"leadArticleSlug": "lead-story"})

        html = client.get("/").get_data(as_text=True)
        payload = _bootstrap_json(html, "homepage")

        assert payload["leadArticle"] is not None
        assert payload["leadArticle"]["slug"] == "lead-story"
        assert payload["leadArticle"]["title"] == "Lead Story"
        assert article_id  # created successfully, used only for slug above

    def test_homepage_bootstrap_lead_article_null_when_lead_slug_is_draft(self, client, app):
        _use_fixture_index(app)
        _make_article(app, slug="not-yet-public", title="Internal Draft Title Only", status="draft")
        _make_homepage_module(app, type="hero", enabled=True, heading="Welcome", config={"leadArticleSlug": "not-yet-public"})

        html = client.get("/").get_data(as_text=True)
        payload = _bootstrap_json(html, "homepage")

        assert payload["leadArticle"] is None
        assert "Internal Draft Title Only" not in html

    def test_homepage_bootstrap_lead_article_null_with_no_hero_module(self, client, app):
        _use_fixture_index(app)
        _make_homepage_module(app, type="latest_stories", enabled=True, config={"itemCount": 6})

        html = client.get("/").get_data(as_text=True)
        payload = _bootstrap_json(html, "homepage")

        assert payload["leadArticle"] is None
        assert len(payload["modules"]) == 1

    def test_homepage_bootstrap_redacts_internal_media_fields(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "hero", "/media/hero/hero.webp", width=1920)
        _make_homepage_module(app, type="hero", enabled=True, heading="Welcome", media_id=media_id)

        html = client.get("/").get_data(as_text=True)
        payload = _bootstrap_json(html, "homepage")

        media = payload["modules"][0]["media"]
        assert media["public_url"] == "/media/originals/hero.jpg"
        assert "file_path" not in media
        assert "stored_filename" not in media
        assert "uploaded_by_id" not in media

    def test_homepage_bootstrap_absent_on_login_route(self, client, app):
        _use_fixture_index(app)
        html = client.get("/login").get_data(as_text=True)
        assert _bootstrap_tags(html, "homepage") == []


class TestHomepageHeroPreload:
    def test_manual_hero_with_heading_and_media_gets_preload(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "card", "/media/card/hero.webp", width=640)
        _add_variant(app, media_id, "hero", "/media/hero/hero.webp", width=1920)
        _make_homepage_module(app, type="hero", enabled=True, heading="Welcome", media_id=media_id)

        html = client.get("/").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/hero/hero.webp"
        assert _attr(tags[0], "imagesizes") == "(min-width: 1024px) 50vw, 100vw"

    def test_manual_hero_with_media_but_no_heading_gets_no_preload(self, client, app):
        # Mirrors HeroModule.jsx's own guard: `if (!module.heading) return
        # null` comes before the manual `module.media` branch, so a media
        # row with no heading renders nothing client-side at all.
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "hero", "/media/hero/hero.webp", width=1920)
        _make_homepage_module(app, type="hero", enabled=True, heading=None, media_id=media_id)

        html = client.get("/").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_lead_article_hero_preload_uses_lead_articles_own_hero_media(self, client, app):
        _use_fixture_index(app)
        article_media_id = _make_media(app, public_url="/media/originals/article-hero.jpg")
        _add_variant(app, article_media_id, "card", "/media/card/article-hero.webp", width=640)
        _add_variant(app, article_media_id, "large", "/media/large/article-hero.webp", width=1280)
        _make_article(app, slug="lead-story", title="Lead Story", status="published", hero_media_id=article_media_id)

        # A manual media on the module itself must never be preferred
        # over the lead Article's own hero_media once one is selected.
        module_media_id = _make_media(app, public_url="/media/originals/module-media.jpg")
        _add_variant(app, module_media_id, "hero", "/media/hero/module-media.webp", width=1920)
        _make_homepage_module(
            app, type="hero", enabled=True, heading="Welcome", media_id=module_media_id, config={"leadArticleSlug": "lead-story"}
        )

        html = client.get("/").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/large/article-hero.webp"
        assert _attr(tags[0], "imagesizes") == "(min-width: 1024px) 66vw, 100vw"

    def test_no_hero_module_gives_no_homepage_preload(self, client, app):
        _use_fixture_index(app)
        _make_homepage_module(app, type="latest_stories", enabled=True, config={"itemCount": 6})

        html = client.get("/").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_hero_with_no_media_and_no_lead_article_gives_no_preload(self, client, app):
        _use_fixture_index(app)
        _make_homepage_module(app, type="hero", enabled=True, heading="Welcome", media_id=None)

        html = client.get("/").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_disabled_hero_module_never_preloaded(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "hero", "/media/hero/hero.webp", width=1920)
        _make_homepage_module(app, type="hero", enabled=False, heading="Welcome", media_id=media_id)

        html = client.get("/").get_data(as_text=True)
        assert _preload_tags(html) == []
        assert _bootstrap_json(html, "homepage")["modules"] == []

    def test_non_hero_module_media_never_preloaded(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/sponsor-logo.jpg")
        _add_variant(app, media_id, "large", "/media/large/sponsor-logo.webp", width=1280)
        _make_homepage_module(app, type="sponsor_placement", enabled=True, media_id=media_id)

        html = client.get("/").get_data(as_text=True)
        assert _preload_tags(html) == []
