"""Homepage Builder: career_pathways + content_collection modules —
write-time validation/normalization, GET→PUT→GET round-trip, public
resolution (endpoint, SPA bootstrap, prerender), Studio warnings,
backward compatibility of the 16 existing types, and the constraint-only
migration."""
import datetime
import importlib
import json
import os
import re

import pytest
import sqlalchemy as sa

from app.extensions import db
from tests.conftest import auth_headers

TODAY = datetime.date.today()
FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


def _admin_token(client, app):
    from app.models.user import Role, User

    payload = {"email": "hpc-admin@example.com", "password": "supersecret1", "first_name": "A", "last_name": "B"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="admin").first())
        db.session.commit()
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def admin(client, app):
    return auth_headers(_admin_token(client, app))


def _add(app, row):
    with app.app_context():
        db.session.add(row)
        db.session.commit()
        return row.id


def _author(app):
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="hpc-editorial").first()
        if author is None:
            author = Author(slug="hpc-editorial", name="HPC Editorial")
            db.session.add(author)
            db.session.commit()
        return author.id


def _article(app, slug, status="published", days_ago=0, featured=False, topic_id=None, series_id=None):
    from app.models.article import Article
    from app.models.taxonomy import Topic

    author_id = _author(app)
    with app.app_context():
        article = Article(
            title=f"Story {slug}", slug=slug, status=status, content=[], author_id=author_id, featured=featured,
            publish_date=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago),
            series_id=series_id,
        )
        if topic_id:
            article.topics.append(db.session.get(Topic, topic_id))
        db.session.add(article)
        db.session.commit()
        return article.id


def _topic(app, slug="careers", status="published"):
    from app.models.taxonomy import Topic

    return _add(app, Topic(slug=slug, name=slug.title(), status=status))


def _series(app, slug="leaders", status="published"):
    from app.models.taxonomy import Series

    return _add(app, Series(slug=slug, name=slug.title(), status=status))


def _page(app, slug="start-here", status="published"):
    from app.models.page import Page

    return _add(app, Page(key=slug, slug=slug, title=slug.title(), status=status, content=[]))


def _media(app):
    from app.models.media import Media

    return _add(app, Media(
        original_filename="p.png", stored_filename="p-stored.png", file_path="/tmp/p-stored.png",
        public_url="https://cdn.example.com/p-stored.png", mime_type="image/png", alt_text="Pathway image",
    ))


def _job(app, slug, status="published", deadline=None, expiry=None, published_days_ago=1):
    from app.models.opportunity import Job

    return _add(app, Job(
        slug=slug, title=f"Job {slug}", status=status, company_name="Co", description=[], deadline=deadline,
        expiry_date=expiry, published_date=TODAY - datetime.timedelta(days=published_days_ago),
    ))


def _opportunity(app, slug, status="published", deadline=None, expiry=None, published_days_ago=1):
    from app.models.opportunity import Opportunity

    return _add(app, Opportunity(
        slug=slug, title=f"Opp {slug}", status=status, description=[], deadline=deadline, expiry_date=expiry,
        published_date=TODAY - datetime.timedelta(days=published_days_ago),
    ))


def _event(app, slug, days_from_now, status="published"):
    from app.models.opportunity import Event

    return _add(app, Event(slug=slug, title=f"Event {slug}", status=status, description=[],
                           date=TODAY + datetime.timedelta(days=days_from_now)))


def _resource(app, slug, access_type="direct_download", status="published", featured=False):
    from app.models.resource import Resource

    return _add(app, Resource(slug=slug, name=f"Resource {slug}", status=status, description=[],
                              access_type=access_type, featured=featured, published_date=TODAY))


def _learning(app, slug, program_type="course", status="published", featured=False):
    from app.models.learning import LearningProgram

    return _add(app, LearningProgram(slug=slug, title=f"Program {slug}", status=status,
                                     program_type=program_type, featured=featured))


def _person(app, slug, status="published", featured=False):
    from app.models.people import Person

    return _add(app, Person(slug=slug, name=f"Person {slug}", bio="Bio.", status=status, featured=featured))


def _card(title, **dest):
    card = {"title": title, "description": f"About {title}"}
    # A real public route: route destinations are validated against the
    # site's actual routes (spa_shell.known_internal_route).
    card.update(dest or {"destinationType": "route", "url": "/learning"})
    return card


def _pathways(cards, **extra):
    module = {"type": "career_pathways", "heading": "Start here", "subheading": "Pick a path.",
              "config": {"eyebrow": "New here?", "cards": cards}}
    module.update(extra)
    return module


def _collection(config, mode="automatic", **extra):
    module = {"type": "content_collection", "heading": "Collection", "selectionMode": mode, "config": config}
    module.update(extra)
    return module


def _put(client, admin, *modules):
    return client.put("/api/v1/admin/homepage", json={"modules": list(modules)}, headers=admin)


def _admin_modules(client, admin):
    return client.get("/api/v1/admin/homepage", headers=admin).get_json()["data"]


def _public(client):
    return client.get("/api/v1/public/homepage").get_json()["data"]


def _error_text(resp):
    return json.dumps(resp.get_json())


def _bootstrap(html):
    tag = re.search(r'<script\b[^>]*data-wsf-bootstrap="homepage"[^>]*>(.*?)</script>', html, re.DOTALL)
    return json.loads(tag.group(1))


# --- registry / compatibility -----------------------------------------------------


class TestRegistry:
    def test_both_types_registered_and_existing_sixteen_kept(self):
        from app.models.cms import HOMEPAGE_MODULE_TYPES

        assert "career_pathways" in HOMEPAGE_MODULE_TYPES and "content_collection" in HOMEPAGE_MODULE_TYPES
        assert len(HOMEPAGE_MODULE_TYPES) == 18
        for legacy in ("hero", "featured_stories", "latest_stories", "featured_woman", "series_feature",
                       "topic_collection", "opportunities", "jobs", "events", "resources", "newsletter",
                       "partners", "community_cta", "mentorship_cta", "editorial_callout", "sponsor_placement"):
            assert legacy in HOMEPAGE_MODULE_TYPES

    def test_existing_module_types_still_save_unchanged(self, client, app, admin):
        modules = [
            {"type": "hero", "heading": "Welcome", "config": {}},
            {"type": "latest_stories", "config": {"itemCount": 6}},
            {"type": "jobs", "config": {"itemCount": 4}},
            {"type": "community_cta", "heading": "Join", "ctaLabel": "Join", "ctaUrl": "/circle", "config": {}},
            {"type": "sponsor_placement", "config": {"placementKey": "homepage_featured"}},
        ]
        assert _put(client, admin, *modules).status_code == 200
        saved = _admin_modules(client, admin)
        assert [m["type"] for m in saved] == [m["type"] for m in modules]
        assert saved[1]["config"] == {"itemCount": 6}
        assert saved[3]["cta_url"] == "/circle"


# --- career pathways: validation -----------------------------------------------------


class TestPathwaysValidation:
    def test_valid_cards_round_trip_get_put_get(self, client, app, admin):
        page_id, topic_id, series_id = _page(app), _topic(app), _series(app)
        media_id = _media(app)
        cards = [
            _card("Find a job", destinationType="route", url="/jobs", icon="briefcase", eyebrow="Careers"),
            _card("Read the guide", destinationType="page", pageId=page_id, mediaId=media_id, ariaLabel="Read our guide"),
            _card("Topic", destinationType="topic", topicId=topic_id),
            _card("Series", destinationType="series", seriesId=series_id),
            _card("Partner", destinationType="external", url="https://partner.example.org", openNewTab=True),
        ]
        resp = _put(client, admin, _pathways(cards, ctaLabel="See all", ctaUrl="/learning"))
        assert resp.status_code == 200, _error_text(resp)
        first = _admin_modules(client, admin)
        echo = [{"type": m["type"], "enabled": m["enabled"], "heading": m["heading"], "subheading": m["subheading"],
                 "selectionMode": m["selection_mode"], "config": m["config"], "ctaLabel": m["cta_label"],
                 "ctaUrl": m["cta_url"]} for m in first]
        assert _put(client, admin, *echo).status_code == 200
        second = _admin_modules(client, admin)
        assert second[0]["config"] == first[0]["config"]
        saved_cards = first[0]["config"]["cards"]
        assert [c["title"] for c in saved_cards] == ["Find a job", "Read the guide", "Topic", "Series", "Partner"]
        assert saved_cards[0]["icon"] == "briefcase" and saved_cards[0]["mediaId"] is None
        assert saved_cards[1]["mediaId"] == media_id and saved_cards[1]["ariaLabel"] == "Read our guide"
        assert saved_cards[4]["openNewTab"] is True

    def test_stale_destination_fields_are_cleared(self, client, app, admin):
        page_id = _page(app)
        cards = [
            {"title": "A", "destinationType": "route", "url": "/topics", "pageId": page_id, "openNewTab": True},
            {"title": "B", "destinationType": "page", "pageId": page_id, "url": "/stale"},
        ]
        assert _put(client, admin, _pathways(cards)).status_code == 200
        saved = _admin_modules(client, admin)[0]["config"]["cards"]
        assert saved[0]["pageId"] is None and saved[0]["url"] == "/topics" and saved[0]["openNewTab"] is False
        assert saved[1]["url"] is None and saved[1]["pageId"] == page_id

    @pytest.mark.parametrize("bad_card, message", [
        ({"title": "No dest"}, "needs a destination"),
        ({"title": "Group", "destinationType": "group"}, "needs a destination"),
        ({"title": "Blank", "destinationType": "route", "url": ""}, "internal path is required"),
        ({"title": "Admin", "destinationType": "route", "url": "/admin/users"}, "admin or API"),
        ({"title": "Proto", "destinationType": "route", "url": "//evil.example"}, "real path"),
        ({"title": "JS", "destinationType": "external", "url": "javascript:alert(1)"}, "http"),
        ({"title": "Page", "destinationType": "page", "pageId": 999999}, "does not exist"),
        ({"title": "Topic", "destinationType": "topic"}, "choose a Topic."),
        ({"title": "", "destinationType": "route", "url": "/resources"}, "title is required"),
        ({"title": "<b>x</b>", "destinationType": "route", "url": "/resources"}, "plain text"),
        ({"title": "Icon", "destinationType": "route", "url": "/resources", "icon": "skull"}, "unknown icon"),
        ({"title": "Extra", "destinationType": "route", "url": "/resources", "onclick": "x"}, "unknown field"),
    ])
    def test_invalid_cards_rejected(self, client, app, admin, bad_card, message):
        resp = _put(client, admin, _pathways([_card("Good one"), bad_card]))
        assert resp.status_code == 422
        assert message in _error_text(resp)

    def test_icon_and_media_are_mutually_exclusive(self, client, app, admin):
        media_id = _media(app)
        resp = _put(client, admin, _pathways([_card("A"), {**_card("B"), "icon": "users", "mediaId": media_id}]))
        assert resp.status_code == 422 and "icon or an image" in _error_text(resp)

    def test_card_count_bounds(self, client, app, admin):
        assert _put(client, admin, _pathways([_card("Only one")])).status_code == 422
        too_many = [_card(f"Card {i}") for i in range(9)]
        assert _put(client, admin, _pathways(too_many)).status_code == 422
        assert _put(client, admin, _pathways([_card(f"Card {i}") for i in range(8)])).status_code == 200
        # A disabled draft may be saved with fewer cards.
        assert _put(client, admin, _pathways([], enabled=False)).status_code == 200

    def test_section_cta_needs_label_and_safe_destination(self, client, app, admin):
        cards = [_card("A"), _card("B")]
        assert _put(client, admin, _pathways(cards, ctaLabel="See all")).status_code == 422
        assert _put(client, admin, _pathways(cards, ctaLabel="x", ctaUrl="/api/v1/secret")).status_code == 422
        assert _put(client, admin, _pathways(cards, ctaLabel="x", ctaUrl="javascript:alert(1)")).status_code == 422

    def test_example_titles_are_not_hardcoded(self, client, app, admin):
        cards = [_card("Completely custom alpha"), _card("Completely custom beta")]
        assert _put(client, admin, _pathways(cards)).status_code == 200
        public = _public(client)[0]
        assert [c["title"] for c in public["resolved"]["cards"]] == ["Completely custom alpha", "Completely custom beta"]


# --- career pathways: public -----------------------------------------------------------


class TestPathwaysPublic:
    def test_resolves_hrefs_and_omits_unpublished_destinations(self, client, app, admin):
        live_page, draft_page = _page(app, "live-page"), _page(app, "draft-page", status="draft")
        topic_id = _topic(app, "money")
        cards = [
            _card("Live", destinationType="page", pageId=live_page),
            _card("Draft", destinationType="page", pageId=draft_page),
            _card("Topic", destinationType="topic", topicId=topic_id),
            _card("External", destinationType="external", url="https://ex.example.org", openNewTab=True),
        ]
        assert _put(client, admin, _pathways(cards)).status_code == 200
        module = _public(client)[0]
        resolved = module["resolved"]["cards"]
        assert [c["title"] for c in resolved] == ["Live", "Topic", "External"]
        assert resolved[0]["href"] == "/live-page" and resolved[0]["linkType"] == "internal"
        assert resolved[1]["href"] == "/topics/money"
        assert resolved[2] == {**resolved[2], "href": "https://ex.example.org", "linkType": "external", "openNewTab": True}
        assert all(c["href"] != "/" for c in resolved)
        # Raw destination ids never reach the public payload.
        assert module["config"] == {"eyebrow": "New here?"}

    def test_all_destinations_gone_hides_section_everywhere(self, client, app, admin):
        p1, p2 = _page(app, "p-one"), _page(app, "p-two")
        cards = [_card("One", destinationType="page", pageId=p1), _card("Two", destinationType="page", pageId=p2)]
        assert _put(client, admin, _pathways(cards)).status_code == 200
        from app.models.page import Page

        with app.app_context():
            for page in Page.query.all():
                page.status = "draft"
            db.session.commit()
        assert _public(client)[0]["resolved"]["cards"] == []
        warnings = _admin_modules(client, admin)[0]["warnings"]
        assert any("hidden" in w for w in warnings)

    def test_media_card_exposes_only_public_image_fields(self, client, app, admin):
        media_id = _media(app)
        assert _put(client, admin, _pathways([_card("A", destinationType="route", url="/topics", mediaId=media_id), _card("B")])).status_code == 200
        image = _public(client)[0]["resolved"]["cards"][0]["image"]
        assert image["url"] == "https://cdn.example.com/p-stored.png" and image["alt"] == "Pathway image"
        assert "file_path" not in json.dumps(image)


# --- content collection: validation ----------------------------------------------------


class TestCollectionValidation:
    def test_manual_stores_slugs_in_order_and_round_trips(self, client, app, admin):
        for slug in ("c", "a", "b"):
            _article(app, slug)
        resp = _put(client, admin, _collection({"entityType": "articles", "slugs": ["c", "a", "b"], "layout": "compact"}, mode="manual"))
        assert resp.status_code == 200, _error_text(resp)
        first = _admin_modules(client, admin)[0]
        assert first["selection_mode"] == "manual"
        assert first["config"] == {"eyebrow": None, "entityType": "articles", "layout": "compact", "slugs": ["c", "a", "b"]}
        echo = {"type": first["type"], "heading": first["heading"], "selectionMode": first["selection_mode"], "config": first["config"]}
        assert _put(client, admin, echo).status_code == 200
        assert _admin_modules(client, admin)[0]["config"] == first["config"]
        assert [i["slug"] for i in _public(client)[0]["resolved"]["items"]] == ["c", "a", "b"]

    def test_mode_switch_clears_stale_config(self, client, app, admin):
        _article(app, "x")
        # Manual payload still carrying automatic-mode keys: those are dropped.
        resp = _put(client, admin, _collection(
            {"entityType": "articles", "slugs": ["x"], "sort": "featured", "filters": {"topic": "nope"}, "itemCount": 3},
            mode="manual"))
        assert resp.status_code == 200, _error_text(resp)
        assert _admin_modules(client, admin)[0]["config"] == {"eyebrow": None, "entityType": "articles", "layout": "grid", "slugs": ["x"]}
        # Automatic payload still carrying manual slugs: slugs dropped.
        resp = _put(client, admin, _collection({"entityType": "articles", "slugs": ["x"], "itemCount": 3}))
        assert resp.status_code == 200
        assert _admin_modules(client, admin)[0]["config"] == {
            "eyebrow": None, "entityType": "articles", "layout": "grid", "itemCount": 3, "sort": "latest", "filters": {}}

    @pytest.mark.parametrize("config, mode, message", [
        ({"entityType": "products"}, "automatic", "Choose what this collection shows"),
        ({"entityType": "articles"}, None, "manual or automatic"),
        ({"entityType": "articles", "sort": "most_read"}, "automatic", "can be sorted by"),
        ({"entityType": "jobs", "sort": "featured"}, "automatic", "can be sorted by"),
        ({"entityType": "events", "filters": {"topic": "x"}}, "automatic", "can't be filtered by"),
        ({"entityType": "resources", "filters": {"accessType": "free"}}, "automatic", "must be one of"),
        ({"entityType": "learning", "filters": {"programType": "webinar"}}, "automatic", "must be one of"),
        ({"entityType": "articles", "filters": {"topic": "missing-topic"}}, "automatic", "doesn't exist"),
        ({"entityType": "articles", "itemCount": 9}, "automatic", "between 1 and 8"),
        ({"entityType": "articles", "itemCount": 0}, "automatic", "between 1 and 8"),
        ({"entityType": "articles", "layout": "carousel"}, "automatic", "Layout must be"),
        ({"entityType": "articles", "slugs": []}, "manual", "Pick at least one"),
        ({"entityType": "articles", "slugs": ["ghost"]}, "manual", "don't exist"),
        ({"entityType": "articles", "bogus": 1}, "automatic", "Unknown setting"),
    ])
    def test_invalid_config_rejected(self, client, app, admin, config, mode, message):
        resp = _put(client, admin, _collection(config, mode=mode))
        assert resp.status_code == 422
        assert message in _error_text(resp)

    def test_manual_duplicates_and_too_many_rejected(self, client, app, admin):
        for i in range(9):
            _article(app, f"s{i}")
        assert "only be picked once" in _error_text(
            _put(client, admin, _collection({"entityType": "articles", "slugs": ["s1", "s1"]}, mode="manual")))
        assert "at most 8" in _error_text(
            _put(client, admin, _collection({"entityType": "articles", "slugs": [f"s{i}" for i in range(9)]}, mode="manual")))


# --- content collection: public resolution --------------------------------------------


def _resolved(client, admin, config, mode="automatic"):
    resp = _put(client, admin, _collection(config, mode=mode))
    assert resp.status_code == 200, _error_text(resp)
    return _public(client)[0]["resolved"]


class TestCollectionResolution:
    def test_articles_latest_featured_topic_series(self, client, app, admin):
        topic_id, series_id = _topic(app, "lead"), _series(app, "voices")
        _article(app, "old", days_ago=5)
        _article(app, "new", days_ago=1, featured=True, topic_id=topic_id)
        _article(app, "mid", days_ago=3, series_id=series_id)
        _article(app, "draft", status="draft")
        latest = _resolved(client, admin, {"entityType": "articles", "itemCount": 8})
        assert [i["slug"] for i in latest["items"]] == ["new", "mid", "old"]
        assert latest["entityType"] == "articles"
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "articles", "sort": "featured"})["items"]] == ["new"]
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "articles", "filters": {"topic": "lead"}})["items"]] == ["new"]
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "articles", "filters": {"series": "voices"}})["items"]] == ["mid"]
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "articles", "itemCount": 1})["items"]] == ["new"]

    def test_jobs_closing_soon_excludes_expired_and_undated(self, client, app, admin):
        _job(app, "soon", deadline=TODAY + datetime.timedelta(days=2))
        _job(app, "later", deadline=TODAY + datetime.timedelta(days=20))
        _job(app, "undated")
        _job(app, "past-deadline", deadline=TODAY - datetime.timedelta(days=1))
        _job(app, "expired", expiry=TODAY - datetime.timedelta(days=1))
        _job(app, "draft", status="draft", deadline=TODAY + datetime.timedelta(days=1))
        closing = _resolved(client, admin, {"entityType": "jobs", "sort": "closing_soon", "itemCount": 8})
        assert [i["slug"] for i in closing["items"]] == ["soon", "later"]
        newest = _resolved(client, admin, {"entityType": "jobs", "sort": "newest", "itemCount": 8})
        assert set(i["slug"] for i in newest["items"]) == {"soon", "later", "undated"}

    def test_opportunities_exclude_expired(self, client, app, admin):
        _opportunity(app, "open", deadline=TODAY + datetime.timedelta(days=5), published_days_ago=3)
        _opportunity(app, "rolling", published_days_ago=1)
        _opportunity(app, "closed", deadline=TODAY - datetime.timedelta(days=2))
        _opportunity(app, "expired", expiry=TODAY - datetime.timedelta(days=2))
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "opportunities", "itemCount": 8})["items"]] == ["rolling", "open"]
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "opportunities", "sort": "closing_soon"})["items"]] == ["open"]

    def test_events_upcoming_only_in_date_order(self, client, app, admin):
        _event(app, "next-month", 30)
        _event(app, "tomorrow", 1)
        _event(app, "last-week", -7)
        _event(app, "draft", 3, status="draft")
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "events"})["items"]] == ["tomorrow", "next-month"]

    def test_resources_access_type_filter_and_no_delivery_data(self, client, app, admin):
        _resource(app, "free-guide", access_type="direct_download")
        _resource(app, "members", access_type="member_only")
        _resource(app, "hidden", status="draft")
        items = _resolved(client, admin, {"entityType": "resources", "filters": {"accessType": "member_only"}})["items"]
        assert [i["slug"] for i in items] == ["members"]
        assert "protected_file_path" not in json.dumps(items)

    def test_learning_program_type_and_featured(self, client, app, admin):
        _learning(app, "course-a", "course")
        _learning(app, "master-b", "masterclass", featured=True)
        _learning(app, "draft-c", "course", status="draft")
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "learning", "filters": {"programType": "course"}})["items"]] == ["course-a"]
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "learning", "sort": "featured"})["items"]] == ["master-b"]

    def test_people_published_only(self, client, app, admin):
        _person(app, "pub", featured=True)
        _person(app, "draft", status="draft")
        assert [i["slug"] for i in _resolved(client, admin, {"entityType": "people", "sort": "featured"})["items"]] == ["pub"]

    def test_manual_omits_unpublished_and_expired_keeping_order(self, client, app, admin):
        _job(app, "j-open", deadline=TODAY + datetime.timedelta(days=3))
        _job(app, "j-closed", deadline=TODAY - datetime.timedelta(days=3))
        _job(app, "j-draft", status="draft")
        _job(app, "j-two")
        resolved = _resolved(client, admin, {"entityType": "jobs", "slugs": ["j-two", "j-closed", "j-draft", "j-open"]}, mode="manual")
        assert [i["slug"] for i in resolved["items"]] == ["j-two", "j-open"]
        warnings = _admin_modules(client, admin)[0]["warnings"]
        assert any("2 selected item(s)" in w for w in warnings)

    def test_empty_collection_resolves_to_no_items_with_warning(self, client, app, admin):
        assert _resolved(client, admin, {"entityType": "events"})["items"] == []
        assert any("no public items" in w for w in _admin_modules(client, admin)[0]["warnings"])

    def test_public_config_hides_manual_slugs(self, client, app, admin):
        _article(app, "visible")
        _article(app, "secret-draft", status="draft")
        _put(client, admin, _collection({"entityType": "articles", "slugs": ["visible", "secret-draft"]}, mode="manual"))
        body = json.dumps(_public(client))
        assert "secret-draft" not in body
        assert _public(client)[0]["config"] == {"eyebrow": None, "entityType": "articles", "layout": "grid"}


# --- bootstrap + prerender --------------------------------------------------------------


class TestShellIntegration:
    def test_bootstrap_and_prerender_share_resolution(self, client, app, admin):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        page_id = _page(app, "guide-page")
        _article(app, "shell-story")
        _put(client, admin,
             _pathways([_card("Custom path one", destinationType="page", pageId=page_id), _card("Custom path two")]),
             _collection({"entityType": "articles", "itemCount": 2}, heading="Fresh reads"),
             _collection({"entityType": "events"}, heading="Nothing here"))
        html = client.get("/").get_data(as_text=True)
        modules = _bootstrap(html)["modules"]
        assert [c["href"] for c in modules[0]["resolved"]["cards"]] == ["/guide-page", "/learning"]
        assert [i["slug"] for i in modules[1]["resolved"]["items"]] == ["shell-story"]
        assert modules == _public(client)
        prerender = html.split('data-wsf-prerender="home"', 1)[1].split("</main>", 1)[0]
        assert 'href="/guide-page"' in prerender and "Custom path one" in prerender
        assert "Fresh reads" in prerender and "/shell-story" in prerender
        # An empty collection never renders an empty shell.
        assert "Nothing here" not in prerender

    def test_public_homepage_query_count_is_bounded(self, client, app, admin):
        for i in range(4):
            _article(app, f"q{i}")
        _put(client, admin, _collection({"entityType": "articles", "itemCount": 4}),
             _collection({"entityType": "articles", "sort": "featured"}),
             _pathways([_card("A"), _card("B")]))
        from sqlalchemy import event

        with app.app_context():
            statements = []
            engine = db.engine
            listener = lambda *args: statements.append(args[2])  # noqa: E731
            event.listen(engine, "before_cursor_execute", listener)
            try:
                assert client.get("/api/v1/public/homepage").status_code == 200
            finally:
                event.remove(engine, "before_cursor_execute", listener)
        assert len(statements) < 40


# --- migration ---------------------------------------------------------------------------


def _migration():
    return importlib.import_module("migrations.versions.c5e2a9d4f1b8_homepage_pathways_collections")


class TestMigration:
    def test_single_head_on_top_of_checkout_phase1(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        module = _migration()
        assert module.down_revision == "a8d3f1c7e2b5"
        config = Config()
        config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
        script = ScriptDirectory.from_config(config)
        # Still one linear head; later work (Career Hub / Lifetime Circle)
        # builds on this revision, so it must remain an ancestor.
        heads = script.get_heads()
        assert len(heads) == 1
        assert "c5e2a9d4f1b8" in {rev.revision for rev in script.iterate_revisions(heads[0], "base")}

    def test_upgrade_widens_check_and_downgrade_restores_it(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module = _migration()
        engine = sa.create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(sa.text(
                "CREATE TABLE homepage_modules (id INTEGER PRIMARY KEY, type VARCHAR(50) NOT NULL, "
                "CONSTRAINT ck_homepage_modules_type CHECK (" + module._check(module._PREVIOUS_TYPES) + "))"
            ))
            conn.execute(sa.text("INSERT INTO homepage_modules (type) VALUES ('hero')"))
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()
            conn.execute(sa.text("INSERT INTO homepage_modules (type) VALUES ('career_pathways')"))
            with pytest.raises(RuntimeError):
                with Operations.context(MigrationContext.configure(conn)):
                    module.downgrade()
            conn.execute(sa.text("DELETE FROM homepage_modules WHERE type = 'career_pathways'"))
            with Operations.context(MigrationContext.configure(conn)):
                module.downgrade()
            assert conn.execute(sa.text("SELECT type FROM homepage_modules")).scalars().all() == ["hero"]
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(sa.text("INSERT INTO homepage_modules (type) VALUES ('content_collection')"))


# --- query behaviour / manual integrity ------------------------------------------------


def _count_statements(app, fn):
    from sqlalchemy import event

    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(db.engine, "before_cursor_execute", listener)
    try:
        result = fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", listener)
    return result, len(statements)


class TestCollectionQueries:
    @pytest.mark.parametrize("entity, sort, factory", [
        ("articles", "latest", lambda app, i: _article(app, f"qa{i}", days_ago=i)),
        ("people", "newest", lambda app, i: _person(app, f"qp{i}")),
        ("opportunities", "closing_soon", lambda app, i: _opportunity(app, f"qo{i}", deadline=TODAY + datetime.timedelta(days=i + 1))),
        ("jobs", "closing_soon", lambda app, i: _job(app, f"qj{i}", deadline=TODAY + datetime.timedelta(days=i + 1))),
        ("events", "upcoming", lambda app, i: _event(app, f"qe{i}", i + 1)),
        ("resources", "newest", lambda app, i: _resource(app, f"qr{i}")),
        ("learning", "newest", lambda app, i: _learning(app, f"ql{i}")),
    ])
    def test_query_count_does_not_grow_with_card_count(self, app, entity, sort, factory):
        """No per-card queries: resolving 8 cards costs the same number of
        statements as resolving 2 (a fixed handful of batched loads)."""
        from app.models.cms import HomepageModule
        from app.services.homepage_collections import resolve_collection

        for i in range(10):
            factory(app, i)
        with app.app_context():
            counts = {}
            for n in (2, 8):
                module = HomepageModule(type="content_collection", selection_mode="automatic",
                                        config={"entityType": entity, "itemCount": n, "sort": sort, "filters": {}})
                db.session.expire_all()
                result, counts[n] = _count_statements(app, lambda: resolve_collection(module))
                assert len(result["items"]) == n
            assert counts[2] == counts[8], counts
            assert counts[8] <= 6, counts

    def test_resource_linked_product_prefetch_matches_single_lookup(self, app):
        from app.api.v1.resources import build_public_resource_payload, prefetch_linked_products
        from app.models.commerce import Product
        from app.models.resource import Resource

        rid = _resource(app, "with-product")
        _resource(app, "without-product")
        with app.app_context():
            db.session.add(Product(slug="wb-product", name="Workbook", resource_id=rid, status="active"))
            db.session.commit()
            rows = Resource.query.order_by(Resource.id).all()
            products = prefetch_linked_products(rows)
            for row in rows:
                assert build_public_resource_payload(row, None, linked_products=products) == build_public_resource_payload(row, None)


class TestManualIntegrity:
    def test_manual_never_substitutes_or_falls_back_to_automatic(self, client, app, admin):
        _article(app, "gone-later")
        _article(app, "other-published")  # must never be substituted in
        resp = _put(client, admin, _collection({"entityType": "articles", "slugs": ["gone-later"]}, mode="manual"))
        assert resp.status_code == 200
        from app.models.article import Article

        with app.app_context():
            Article.query.filter_by(slug="gone-later").first().status = "draft"
            db.session.commit()
        assert _public(client)[0]["resolved"]["items"] == []
        with app.app_context():
            db.session.delete(Article.query.filter_by(slug="gone-later").first())
            db.session.commit()
        assert _public(client)[0]["resolved"]["items"] == []
        assert _admin_modules(client, admin)[0]["selection_mode"] == "manual"
