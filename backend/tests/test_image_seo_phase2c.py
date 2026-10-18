"""WSF SEO Phase 2C — "Image SEO, LCP & Core Web Vitals Foundations".
Covers the one new server-side behavior this phase adds to spa_shell.py:
a single managed `<link rel="preload" as="image" ...>` tag for the exact
image each route's OWN frontend page already marks `priority` (Article's
hero, and Series/Resource/Event's cover) — never fabricated, never a
second tag, never a protected filesystem path, and never present on a
route whose frontend has no genuine above-the-fold hero/cover image.

Does not re-test anything from test_spa_shell.py or
test_spa_shell_structured_data_phase2a.py (og:image/structured-data
variant selection is unchanged by this phase — see those files).
"""
import os
import re
from datetime import date

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
DUPLICATES_FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index_duplicates.html")


def _use_fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _use_duplicates_fixture_index(app):
    app.config["SPA_INDEX_PATH"] = DUPLICATES_FIXTURE_INDEX_PATH


def _preload_tags(html):
    return re.findall(r'<link\b[^>]*data-lcp-image-preload="true"[^>]*>', html, re.IGNORECASE)


def _attr(tag, name):
    match = re.search(rf'{name}="([^"]*)"', tag)
    return match.group(1) if match else None


def _make_media(app, alt_text="A group of women at a conference.", public_url="/media/originals/hero.jpg"):
    from app.models.media import Media

    with app.app_context():
        media = Media(
            original_filename="hero.jpg",
            stored_filename="hero.jpg",
            file_path="/var/protected/hero.jpg",
            public_url=public_url,
            mime_type="image/jpeg",
            alt_text=alt_text,
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


def _make_author(app, slug="wsf-editorial", name="WSF Editorial", status="active"):
    from app.models.people import Author

    with app.app_context():
        author = Author(slug=slug, name=name, status=status)
        db.session.add(author)
        db.session.commit()
        return author.id


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


def _make_topic(app, slug, name="Leadership", status="published", **overrides):
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic(slug=slug, name=name, status=status, **overrides)
        db.session.add(topic)
        db.session.commit()
        return topic.id


def _make_series(app, slug, name="Founder Stories", status="published", **overrides):
    from app.models.taxonomy import Series

    with app.app_context():
        series = Series(slug=slug, name=name, status=status, **overrides)
        db.session.add(series)
        db.session.commit()
        return series.id


def _make_person(app, slug, name="Amara Okafor", status="published", **overrides):
    from app.models.people import Person

    with app.app_context():
        person = Person(slug=slug, name=name, status=status, **overrides)
        db.session.add(person)
        db.session.commit()
        return person.id


def _make_opportunity(app, slug, title="Global Fellowship", status="published", **overrides):
    from app.models.opportunity import Opportunity

    with app.app_context():
        opportunity = Opportunity(slug=slug, title=title, status=status, **overrides)
        db.session.add(opportunity)
        db.session.commit()
        return opportunity.id


def _make_job(app, slug, title="Program Manager", company_name="Kaziwave", status="published", **overrides):
    from app.models.opportunity import Job

    with app.app_context():
        job = Job(slug=slug, title=title, company_name=company_name, status=status, **overrides)
        db.session.add(job)
        db.session.commit()
        return job.id


def _make_event(app, slug, title="WSF Summit", status="published", event_date=None, **overrides):
    from app.models.opportunity import Event

    with app.app_context():
        event = Event(slug=slug, title=title, status=status, date=event_date or date(2026, 6, 1), **overrides)
        db.session.add(event)
        db.session.commit()
        return event.id


def _make_resource(app, slug, name="Career Reset Workbook", status="published", **overrides):
    from app.models.resource import Resource

    with app.app_context():
        resource = Resource(slug=slug, name=name, status=status, **overrides)
        db.session.add(resource)
        db.session.commit()
        return resource.id


class TestArticleImagePreload:
    def test_article_prefers_hero_variant_for_preload_href(self, client, app):
        # Route-parity requirement: ArticlePage.jsx's hero <MediaImage>
        # requests variant="hero" — the server preload href must match
        # that exact variant, not simply "widest generated variant"
        # (which would wrongly pick a non-existent wider "large" here).
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "thumbnail", "/media/thumbnail/hero.webp", width=320)
        _add_variant(app, media_id, "card", "/media/card/hero.webp", width=640)
        _add_variant(app, media_id, "large", "/media/large/hero.webp", width=1280)
        _add_variant(app, media_id, "hero", "/media/hero/hero.webp", width=1920)
        _make_article(app, slug="hero-story", title="Hero Story", hero_media_id=media_id)

        html = client.get("/hero-story").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        tag = tags[0]
        assert _attr(tag, "rel") == "preload"
        assert _attr(tag, "as") == "image"
        assert _attr(tag, "fetchpriority") == "high"
        # Prefers the "hero" variant — not "large", even though both exist.
        assert _attr(tag, "href") == "https://womenshapingfutures.org/media/hero/hero.webp"
        srcset = _attr(tag, "imagesrcset")
        assert srcset == (
            "https://womenshapingfutures.org/media/thumbnail/hero.webp 320w, "
            "https://womenshapingfutures.org/media/card/hero.webp 640w, "
            "https://womenshapingfutures.org/media/large/hero.webp 1280w, "
            "https://womenshapingfutures.org/media/hero/hero.webp 1920w"
        )
        assert _attr(tag, "imagesizes") == "(min-width: 1120px) 1120px, 100vw"

    def test_article_falls_back_to_widest_variant_when_hero_absent(self, client, app):
        # No "hero"-named variant exists for this Media, so the fallback
        # rule (widest valid generated candidate) applies — "large" wins.
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/hero.jpg")
        _add_variant(app, media_id, "thumbnail", "/media/thumbnail/hero.webp", width=320)
        _add_variant(app, media_id, "card", "/media/card/hero.webp", width=640)
        _add_variant(app, media_id, "large", "/media/large/hero.webp", width=1280)
        _make_article(app, slug="hero-fallback-story", title="Hero Fallback Story", hero_media_id=media_id)

        html = client.get("/hero-fallback-story").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/large/hero.webp"

    def test_article_with_hero_but_no_variants_preloads_original_with_no_srcset(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/plain-hero.jpg")
        _make_article(app, slug="plain-hero-story", title="Plain Hero Story", hero_media_id=media_id)

        html = client.get("/plain-hero-story").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/originals/plain-hero.jpg"
        assert _attr(tags[0], "imagesrcset") is None
        assert _attr(tags[0], "imagesizes") is None

    def test_article_without_hero_media_has_no_preload(self, client, app):
        _use_fixture_index(app)
        _make_article(app, slug="no-hero-story", title="No Hero Story")

        html = client.get("/no-hero-story").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_variant_missing_width_is_excluded_from_srcset(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/partial-hero.jpg")
        _add_variant(app, media_id, "card", "/media/card/partial-hero.webp", width=None)
        _add_variant(app, media_id, "large", "/media/large/partial-hero.webp", width=1280)
        _make_article(app, slug="partial-variant-story", title="Partial Variant Story", hero_media_id=media_id)

        html = client.get("/partial-variant-story").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        # Only one real-width candidate exists, so no imagesrcset is built
        # (matches resolveMediaImage's own "no invented variants" rule).
        assert _attr(tags[0], "imagesrcset") is None
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/large/partial-hero.webp"

    def test_no_large_or_hero_variant_prefers_widest_available(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/mid-hero.jpg")
        _add_variant(app, media_id, "thumbnail", "/media/thumbnail/mid-hero.webp", width=320)
        _add_variant(app, media_id, "medium", "/media/medium/mid-hero.webp", width=960)
        _make_article(app, slug="mid-variant-story", title="Mid Variant Story", hero_media_id=media_id)

        html = client.get("/mid-variant-story").get_data(as_text=True)
        tags = _preload_tags(html)
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/medium/mid-hero.webp"

    def test_single_variant_preloads_with_no_srcset_or_sizes(self, client, app):
        # imagesizes only means anything paired with imagesrcset — with
        # a single real-width candidate there's nothing to negotiate
        # between, so neither attribute is written (same "don't invent
        # a srcset" rule as the no-variants case).
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/single-variant-hero.jpg")
        _add_variant(app, media_id, "large", "/media/large/single-variant-hero.webp", width=1280)
        _make_article(app, slug="single-variant-story", title="Single Variant Story", hero_media_id=media_id)

        html = client.get("/single-variant-story").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/large/single-variant-hero.webp"
        assert _attr(tags[0], "imagesrcset") is None
        assert _attr(tags[0], "imagesizes") is None

    def test_preload_href_never_exposes_protected_filesystem_path(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/safe-hero.jpg")
        _add_variant(app, media_id, "large", "/media/large/safe-hero.webp", width=1280)
        _make_article(app, slug="safe-path-story", title="Safe Path Story", hero_media_id=media_id)

        html = client.get("/safe-path-story").get_data(as_text=True)
        assert "/var/protected/" not in html

    def test_draft_article_404_has_no_preload(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/draft-hero.jpg")
        _make_article(app, slug="draft-hero-story", title="Draft Hero Story", status="draft", hero_media_id=media_id)

        resp = client.get("/draft-hero-story")
        assert resp.status_code == 404
        assert _preload_tags(resp.get_data(as_text=True)) == []

    def test_rerendering_never_duplicates_the_preload_tag(self, client, app):
        _use_duplicates_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/dup-hero.jpg")
        _add_variant(app, media_id, "large", "/media/large/dup-hero.webp", width=1280)
        _make_article(app, slug="dup-hero-story", title="Dup Hero Story", hero_media_id=media_id)

        html = client.get("/dup-hero-story").get_data(as_text=True)
        assert len(_preload_tags(html)) == 1

    def test_structured_data_and_og_image_unaffected_by_preload(self, client, app):
        # Regression guard: adding the preload tag must never change the
        # pre-existing og:image/JSON-LD variant-selection behavior (those
        # deliberately ignore variants and use the Media's own
        # public_url — see test_spa_shell.py).
        _use_fixture_index(app)
        media_id = _make_media(app, alt_text="Hero alt.", public_url="/media/originals/unaffected-hero.jpg")
        _add_variant(app, media_id, "large", "/media/large/unaffected-hero.webp", width=1280)
        _make_article(app, slug="unaffected-story", title="Unaffected Story", hero_media_id=media_id)

        html = client.get("/unaffected-story").get_data(as_text=True)
        assert 'property="og:image" content="https://womenshapingfutures.org/media/originals/unaffected-hero.jpg"' in html
        assert "data-article-structured-data" in html
        assert len(_preload_tags(html)) == 1


class TestEntityDetailImagePreload:
    def test_series_prefers_hero_variant_for_preload_href(self, client, app):
        # SeriesDetailPage.jsx's cover <MediaImage> requests variant="hero"
        # — the href must match that, not just "widest" (which would
        # wrongly pick "large" here even though "hero" also exists).
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/series-cover.jpg")
        _add_variant(app, media_id, "card", "/media/card/series-cover.webp", width=640)
        _add_variant(app, media_id, "large", "/media/large/series-cover.webp", width=1280)
        _add_variant(app, media_id, "hero", "/media/hero/series-cover.webp", width=1920)
        _make_series(app, "founder-stories", cover_media_id=media_id)

        html = client.get("/series/founder-stories").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/hero/series-cover.webp"
        assert _attr(tags[0], "imagesizes") == "(min-width: 1024px) 45vw, 100vw"

    def test_series_falls_back_to_widest_variant_when_hero_absent(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/series-cover.jpg")
        _add_variant(app, media_id, "card", "/media/card/series-cover.webp", width=640)
        _add_variant(app, media_id, "large", "/media/large/series-cover.webp", width=1280)
        _make_series(app, "founder-stories-fallback", cover_media_id=media_id)

        html = client.get("/series/founder-stories-fallback").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/large/series-cover.webp"

    def test_series_without_cover_media_has_no_preload(self, client, app):
        _use_fixture_index(app)
        _make_series(app, "no-cover-series")

        html = client.get("/series/no-cover-series").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_resource_prefers_medium_variant_for_preload_href(self, client, app):
        # ResourceDetailPage.jsx's cover <MediaImage> requests
        # variant="medium" — NOT "large" and not simply "widest", even
        # though a wider "large" variant also exists here. This is the
        # exact route-parity bug being fixed: the href must be "medium".
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/resource-cover.jpg")
        _add_variant(app, media_id, "card", "/media/card/resource-cover.webp", width=640)
        _add_variant(app, media_id, "medium", "/media/medium/resource-cover.webp", width=960)
        _add_variant(app, media_id, "large", "/media/large/resource-cover.webp", width=1280)
        _make_resource(app, "career-reset-workbook", cover_media_id=media_id)

        html = client.get("/resources/career-reset-workbook").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/medium/resource-cover.webp"
        assert _attr(tags[0], "imagesizes") == "(min-width: 640px) 360px, 100vw"

    def test_resource_falls_back_to_widest_variant_when_medium_absent(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/resource-cover.jpg")
        _add_variant(app, media_id, "card", "/media/card/resource-cover.webp", width=640)
        _add_variant(app, media_id, "large", "/media/large/resource-cover.webp", width=1280)
        _make_resource(app, "career-reset-workbook-fallback", cover_media_id=media_id)

        html = client.get("/resources/career-reset-workbook-fallback").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/large/resource-cover.webp"

    def test_event_prefers_hero_variant_for_preload_href(self, client, app):
        # EventDetailPage.jsx's cover <MediaImage> requests variant="hero".
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/event-cover.jpg")
        _add_variant(app, media_id, "card", "/media/card/event-cover.webp", width=640)
        _add_variant(app, media_id, "large", "/media/large/event-cover.webp", width=1280)
        _add_variant(app, media_id, "hero", "/media/hero/event-cover.webp", width=1920)
        _make_event(app, "wsf-summit", cover_media_id=media_id)

        html = client.get("/events/wsf-summit").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/hero/event-cover.webp"
        assert _attr(tags[0], "imagesizes") == "100vw"

    def test_event_falls_back_to_widest_variant_when_hero_absent(self, client, app):
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/event-cover.jpg")
        _add_variant(app, media_id, "card", "/media/card/event-cover.webp", width=640)
        _add_variant(app, media_id, "large", "/media/large/event-cover.webp", width=1280)
        _make_event(app, "wsf-summit-fallback", cover_media_id=media_id)

        html = client.get("/events/wsf-summit-fallback").get_data(as_text=True)
        tags = _preload_tags(html)
        assert len(tags) == 1
        assert _attr(tags[0], "href") == "https://womenshapingfutures.org/media/large/event-cover.webp"

    def test_event_without_cover_media_has_no_preload(self, client, app):
        _use_fixture_index(app)
        _make_event(app, "no-cover-event")

        html = client.get("/events/no-cover-event").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_topic_detail_never_gets_a_preload(self, client, app):
        # TopicDetailPage has no page-level hero image at all, so no
        # entry exists for it in _ENTITY_IMAGE_PRELOAD.
        _use_fixture_index(app)
        _make_topic(app, "leadership")

        html = client.get("/topics/leadership").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_person_detail_never_gets_a_preload(self, client, app):
        # Person's portrait is a small avatar next to a lot of text, not
        # a genuine LCP candidate — deliberately excluded.
        _use_fixture_index(app)
        media_id = _make_media(app, public_url="/media/originals/portrait.jpg")
        _make_person(app, "amara-okafor", photo_media_id=media_id)

        html = client.get("/people/amara-okafor").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_opportunity_detail_never_gets_a_preload(self, client, app):
        # Only a small organization logo, never a hero image.
        _use_fixture_index(app)
        _make_opportunity(app, "global-fellowship")

        html = client.get("/opportunities/global-fellowship").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_job_detail_never_gets_a_preload(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "program-manager")

        html = client.get("/jobs/program-manager").get_data(as_text=True)
        assert _preload_tags(html) == []


class TestPreloadExcludedRoutes:
    def test_unknown_route_404_has_no_preload(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/this-does-not-exist")
        assert resp.status_code == 404
        assert _preload_tags(resp.get_data(as_text=True)) == []

    def test_homepage_has_no_preload(self, client, app):
        # Section 15: render_homepage_shell resolves no module/article
        # data today, so adding homepage preload would require building
        # exactly the new data-fetch graph this phase forbids. Verify
        # it is (deliberately) still absent.
        _use_fixture_index(app)
        html = client.get("/").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_login_noindex_route_has_no_preload(self, client, app):
        _use_fixture_index(app)
        html = client.get("/login").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_resources_checkout_callback_has_no_preload(self, client, app):
        _use_fixture_index(app)
        html = client.get("/resources/checkout/callback").get_data(as_text=True)
        assert _preload_tags(html) == []

    def test_topics_list_page_has_no_preload(self, client, app):
        _use_fixture_index(app)
        _make_topic(app, "leadership")
        html = client.get("/topics").get_data(as_text=True)
        assert _preload_tags(html) == []
