"""AI Search / GEO Phase 2 — IndexNow (app/services/indexnow.py).

The outbound HTTP layer (`indexnow._post_json`) is always replaced here;
these tests never contact the real IndexNow API.
"""
import logging
import socket
from datetime import date, datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.services import indexnow
from tests.conftest import auth_headers

KEY = "test-indexnow-key-1234"
SITE = "https://womenshapingfutures.org"


class Recorder:
    def __init__(self, status=200, exc=None):
        self.calls, self.status, self.exc = [], status, exc

    def __call__(self, url, payload, timeout):
        self.calls.append({"url": url, "payload": payload, "timeout": timeout})
        if self.exc is not None:
            raise self.exc
        return self.status

    @property
    def urls(self):
        return [u for call in self.calls for u in call["payload"]["urlList"]]


@pytest.fixture()
def sent(app, monkeypatch):
    app.config.update(INDEXNOW_ENABLED=True, INDEXNOW_KEY=KEY, PUBLIC_SITE_URL=SITE, INDEXNOW_TIMEOUT_SECONDS=3)
    recorder = Recorder()
    monkeypatch.setattr(indexnow, "_post_json", recorder)
    return recorder


@pytest.fixture()
def admin_token(client, app):
    from app.models.user import Role, User

    payload = {"email": "indexnow-admin@example.com", "password": "supersecret1", "first_name": "Ida",
               "last_name": "Nowak", "country_code": "US"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.commit()
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


# --- service ----------------------------------------------------------------


def test_disabled_sends_nothing(app, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(indexnow, "_post_json", recorder)
    app.config.update(INDEXNOW_ENABLED=False, INDEXNOW_KEY=KEY)
    result = indexnow.submit_indexnow_urls(["/people/a"])
    assert result["skipped"] == "disabled" and recorder.calls == []


@pytest.mark.parametrize("bad_key", [None, "", "short", "has space in it", "under_score_key", "x" * 129, "ünïcode-key"])
def test_enabled_with_malformed_key_sends_nothing(app, monkeypatch, bad_key):
    recorder = Recorder()
    monkeypatch.setattr(indexnow, "_post_json", recorder)
    app.config.update(INDEXNOW_ENABLED=True, INDEXNOW_KEY=bad_key)
    assert indexnow.submit_indexnow_urls(["/people/a"])["skipped"] == "disabled"
    assert recorder.calls == []


def test_payload_shape_and_normalization(app, sent):
    result = indexnow.submit_indexnow_urls(["/people/a", f"{SITE}/people/a", "/jobs/b", "", None, "/jobs/b"])
    assert result == {"submitted": 2, "accepted": True, "status": 200, "skipped": None}
    (call,) = sent.calls
    assert call["url"] == "https://api.indexnow.org/indexnow"
    assert call["timeout"] == 3
    assert call["payload"] == {
        "host": "womenshapingfutures.org",
        "key": KEY,
        "keyLocation": f"{SITE}/{KEY}.txt",
        "urlList": [f"{SITE}/people/a", f"{SITE}/jobs/b"],
    }


@pytest.mark.parametrize("url", [
    "https://evil.example.com/people/a", "http://womenshapingfutures.org/people/a",
    "https://www.womenshapingfutures.org/x", "/people/a?token=secret", "/people/a#frag", "people/no-slash",
    "/admin", "/admin/articles/1", "/account/profile", "/login", "/register", "/forgot-password",
    "/reset-password", "/change-password", "/api/v1/people", "/media/originals/x.jpg",
    "/newsletter/unsubscribe/tok", "/resources/checkout/callback", "/circle/checkout/callback", "/search",
])
def test_private_and_foreign_urls_are_rejected(app, sent, url):
    assert indexnow.submit_indexnow_urls([url])["skipped"] == "no_public_urls"
    assert sent.calls == []


def test_batches_respect_protocol_maximum(app, sent):
    result = indexnow.submit_indexnow_urls([f"/people/p{i}" for i in range(10_005)])
    assert result["submitted"] == 10_005
    assert [len(c["payload"]["urlList"]) for c in sent.calls] == [10_000, 5]


@pytest.mark.parametrize("status,accepted", [(200, True), (202, True), (400, False), (403, False), (422, False), (429, False)])
def test_http_statuses(app, sent, status, accepted, caplog):
    sent.status = status
    with caplog.at_level(logging.WARNING):
        result = indexnow.submit_indexnow_urls(["/people/a"])
    assert result["accepted"] is accepted and result["status"] == status
    assert KEY not in caplog.text
    if not accepted:
        assert str(status) in caplog.text


@pytest.mark.parametrize("exc", [socket.timeout("timed out"), TimeoutError(), ConnectionError("boom"), OSError(f"failed {KEY}")])
def test_network_failures_are_safe_and_never_log_the_key(app, sent, exc, caplog):
    sent.exc = exc
    with caplog.at_level(logging.WARNING):
        result = indexnow.submit_indexnow_urls(["/people/a"])
    assert result["accepted"] is False
    assert KEY not in caplog.text
    assert "keyLocation" not in caplog.text


def test_notify_public_change_rules(app, sent):
    from app.models.people import Person

    def person(slug, status):
        return Person(slug=slug, name="P", status=status)

    # not public -> public: URL + parent listing
    indexnow.notify_public_change({}, person("a", "published"))
    # public -> public same path: URL only
    indexnow.notify_public_change({"/people/a": "/people"}, person("a", "published"))
    # public slug change: old + new + parent
    indexnow.notify_public_change({"/people/a": "/people"}, person("b", "published"))
    # public -> private: old URL + parent
    indexnow.notify_public_change({"/people/a": "/people"}, person("a", "archived"))
    # deleted
    indexnow.notify_public_change({"/people/a": "/people"}, None)
    # never public
    indexnow.notify_public_change({}, person("a", "draft"))
    assert [c["payload"]["urlList"] for c in sent.calls] == [
        [f"{SITE}/people/a", f"{SITE}/people"],
        [f"{SITE}/people/a"],
        [f"{SITE}/people/b", f"{SITE}/people", f"{SITE}/people/a"],
        [f"{SITE}/people/a", f"{SITE}/people"],
        [f"{SITE}/people/a", f"{SITE}/people"],
    ]


def test_notify_never_raises(app, monkeypatch):
    def boom(_entity):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(indexnow, "public_urls_for", boom)
    assert indexnow.notify_public_change({}, object()) is None
    assert indexnow.capture_public_urls(object()) == {}


# --- key verification route ---------------------------------------------------


def test_key_file_served_only_for_exact_configured_key(app, client):
    app.config.update(INDEXNOW_ENABLED=True, INDEXNOW_KEY=KEY)
    resp = client.get(f"/{KEY}.txt")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert resp.get_data(as_text=True) == KEY
    for path in ("/wrong-key-12345678.txt", f"/{KEY}x.txt", f"/{KEY.upper()}.txt"):
        other = client.get(path)
        assert other.status_code == 404
        assert KEY not in other.get_data(as_text=True)


@pytest.mark.parametrize("enabled,key", [(False, KEY), (True, None), (True, "bad key!")])
def test_key_file_404_when_disabled_or_invalid(app, client, enabled, key):
    app.config.update(INDEXNOW_ENABLED=enabled, INDEXNOW_KEY=key)
    resp = client.get(f"/{KEY}.txt")
    assert resp.status_code == 404
    assert KEY not in resp.get_data(as_text=True)


def test_txt_names_never_reach_article_lookup(app, client):
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author(slug="kf-author", name="KF", status="active")
        db.session.add(author)
        db.session.flush()
        db.session.add(Article(slug="notes", title="Notes Article", status="published", author_id=author.id, content=[]))
        db.session.commit()
    resp = client.get("/notes.txt")
    assert resp.status_code == 404
    assert "Notes Article" not in resp.get_data(as_text=True)
    # robots.txt is unaffected.
    assert client.get("/robots.txt").status_code == 200


# --- Article workflow ---------------------------------------------------------------


@pytest.fixture()
def author_slug(client, admin_token):
    resp = client.post("/api/v1/authors", json={"name": "Index Author", "status": "draft"}, headers=auth_headers(admin_token))
    return resp.get_json()["data"]["slug"]


def _create_article(client, token, author_slug, title, status="draft"):
    resp = client.post("/api/v1/articles", json={
        "title": title, "authorSlug": author_slug, "status": status,
        "content": [{"type": "paragraph", "text": "Body."}],
    }, headers=auth_headers(token))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["data"]["slug"]


def _update_article(client, token, author_slug, slug, status, new_slug=None, title="Edited"):
    return client.put(f"/api/v1/articles/{slug}", json={
        "title": title, "slug": new_slug or slug, "authorSlug": author_slug, "status": status,
        "content": [{"type": "paragraph", "text": "Edited body."}],
    }, headers=auth_headers(token))


def test_article_create_edit_slug_change_archive(client, admin_token, author_slug, sent):
    sent.calls.clear()
    draft = _create_article(client, admin_token, author_slug, "Draft Story")
    assert sent.calls == []  # draft create
    assert _update_article(client, admin_token, author_slug, draft, "draft").status_code == 200
    assert sent.calls == []  # draft edit

    live = _create_article(client, admin_token, author_slug, "Live Story", status="published")
    assert sent.urls == [f"{SITE}/{live}"]  # no article index page as parent

    sent.calls.clear()
    assert _update_article(client, admin_token, author_slug, live, "published").status_code == 200
    assert sent.urls == [f"{SITE}/{live}"]

    sent.calls.clear()
    assert _update_article(client, admin_token, author_slug, live, "published", new_slug="live-story-renamed").status_code == 200
    assert sent.urls == [f"{SITE}/live-story-renamed", f"{SITE}/{live}"]

    sent.calls.clear()
    assert client.post("/api/v1/articles/live-story-renamed/archive", headers=auth_headers(admin_token)).status_code == 200
    assert sent.urls == [f"{SITE}/live-story-renamed"]


def test_article_manual_publish_and_workflow_steps(client, admin_token, author_slug, sent):
    slug = _create_article(client, admin_token, author_slug, "Workflow Story")
    for step in ("submit-review", "approve"):
        assert client.post(f"/api/v1/articles/{slug}/{step}", headers=auth_headers(admin_token)).status_code == 200
    assert sent.calls == []  # non-public transitions notify nothing
    assert client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(admin_token)).status_code == 200
    assert sent.urls == [f"{SITE}/{slug}"]


def _scheduled_article(app, slug):
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="sched-author").first() or Author(slug="sched-author", name="S", status="active")
        db.session.add(author)
        db.session.flush()
        db.session.add(Article(slug=slug, title=slug, status="scheduled", author_id=author.id,
                               content=[{"type": "paragraph", "text": "x"}],
                               scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
        db.session.commit()


def test_scheduled_publish_notifies(app, sent):
    from app.services.articles_workflow import publish_due_articles

    _scheduled_article(app, "due-one")
    _scheduled_article(app, "due-two")
    result = publish_due_articles()
    assert len(result["published"]) == 2 and result["failed"] == []
    assert sorted(sent.urls) == [f"{SITE}/due-one", f"{SITE}/due-two"]


@pytest.mark.parametrize("failure", ["exception", "http_500"])
def test_indexnow_failure_never_fails_publishing(app, client, admin_token, author_slug, sent, failure):
    from app.models.article import Article
    from app.services.articles_workflow import publish_due_articles

    if failure == "exception":
        sent.exc = ConnectionError("search engine down")
    else:
        sent.status = 500

    # Scheduled publish: committed and counted as published, never failed.
    _scheduled_article(app, "due-despite-outage")
    result = publish_due_articles()
    assert result["failed"] == [] and len(result["published"]) == 1

    # Manual create-as-published still succeeds.
    slug = _create_article(client, admin_token, author_slug, "Outage Story", status="published")
    with app.app_context():
        assert Article.query.filter_by(slug="due-despite-outage").first().status == "published"
        assert Article.query.filter_by(slug=slug).first().status == "published"
    assert sent.calls  # it was attempted


def test_notifier_crash_does_not_fail_scheduler(app, monkeypatch, sent):
    from app.models.article import Article
    from app.services.articles_workflow import publish_due_articles

    def explode(*_a, **_k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(indexnow, "submit_indexnow_urls", explode)
    _scheduled_article(app, "due-crash")
    result = publish_due_articles()
    assert result["failed"] == [] and len(result["published"]) == 1
    with app.app_context():
        assert Article.query.filter_by(slug="due-crash").first().status == "published"


def test_no_request_time_notifications(client, app, admin_token, author_slug, sent):
    slug = _create_article(client, admin_token, author_slug, "Read Only Story", status="published")
    sent.calls.clear()
    for path in (f"/{slug}", f"/api/v1/articles/{slug}", "/", "/api/v1/articles", "/sitemap.xml", "/people"):
        client.get(path)
    assert sent.calls == []


# --- People ---------------------------------------------------------------------


def _person_payload(**overrides):
    payload = {"name": "Index Person", "shortBio": "Intro.", "status": "published"}
    payload.update(overrides)
    return payload


def test_person_lifecycle(client, admin_token, sent):
    h = auth_headers(admin_token)
    client.post("/api/v1/people", json=_person_payload(name="Draft Person", status="draft"), headers=h)
    assert sent.calls == []

    client.post("/api/v1/people", json=_person_payload(), headers=h)
    assert sent.urls == [f"{SITE}/people/index-person", f"{SITE}/people"]

    sent.calls.clear()
    client.put("/api/v1/people/index-person", json=_person_payload(shortBio="Edited."), headers=h)
    assert sent.urls == [f"{SITE}/people/index-person"]

    sent.calls.clear()
    client.put("/api/v1/people/index-person", json=_person_payload(slug="renamed-person"), headers=h)
    assert sent.urls == [f"{SITE}/people/renamed-person", f"{SITE}/people", f"{SITE}/people/index-person"]

    sent.calls.clear()
    client.put("/api/v1/people/renamed-person", json=_person_payload(slug="renamed-person", status="archived"), headers=h)
    assert sent.urls == [f"{SITE}/people/renamed-person", f"{SITE}/people"]

    sent.calls.clear()
    client.put("/api/v1/people/draft-person", json=_person_payload(name="Draft Person", status="published"), headers=h)
    assert sent.urls == [f"{SITE}/people/draft-person", f"{SITE}/people"]

    sent.calls.clear()
    assert client.delete("/api/v1/people/draft-person", headers=h).status_code == 200
    assert sent.urls == [f"{SITE}/people/draft-person", f"{SITE}/people"]


# --- other entity families ----------------------------------------------------------


def test_organization_and_directory_urls(client, app, admin_token, sent):
    from app.models.directory import DirectoryListing

    h = auth_headers(admin_token)
    org = {"name": "Kaziwave", "shortDescription": "A lab.", "status": "draft"}
    client.post("/api/v1/organizations", json=org, headers=h)
    assert sent.calls == []
    with app.app_context():
        from app.models.people import Organization

        org_id = Organization.query.filter_by(slug="kaziwave").first().id
        db.session.add(DirectoryListing(organization_id=org_id, status="published", listing_type="business",
                                        ownership_classification="women_owned", classification_provenance="self_attested",
                                        verification_status="unverified"))
        db.session.commit()
    # Publishing the Organization makes BOTH its profile and its (already
    # published) directory listing public.
    client.put("/api/v1/organizations/kaziwave", json={**org, "status": "published"}, headers=h)
    assert sent.urls == [f"{SITE}/organizations/kaziwave", f"{SITE}/organizations", f"{SITE}/directory/kaziwave", f"{SITE}/directory"]

    sent.calls.clear()
    client.put("/api/v1/organizations/kaziwave", json={**org, "status": "archived"}, headers=h)
    assert sorted(sent.urls) == sorted([f"{SITE}/organizations/kaziwave", f"{SITE}/organizations", f"{SITE}/directory/kaziwave", f"{SITE}/directory"])


def test_product_lifecycle(client, admin_token, sent):
    h = auth_headers(admin_token)
    base = {"name": "Workbook", "type": "digital", "price": 100, "description": []}
    resp = client.post("/api/v1/products", json={**base, "status": "draft"}, headers=h)
    assert resp.status_code == 201, resp.get_json()
    assert sent.calls == []
    client.put("/api/v1/products/workbook", json={**base, "status": "active"}, headers=h)
    assert sent.urls == [f"{SITE}/shop/workbook", f"{SITE}/shop"]
    sent.calls.clear()
    client.put("/api/v1/products/workbook", json={**base, "status": "unavailable"}, headers=h)
    assert sent.urls == [f"{SITE}/shop/workbook"]  # still public
    sent.calls.clear()
    client.put("/api/v1/products/workbook", json={**base, "status": "archived"}, headers=h)
    assert sent.urls == [f"{SITE}/shop/workbook", f"{SITE}/shop"]


def test_topic_status_and_slug_change(client, app, admin_token, sent):
    from app.models.taxonomy import Topic

    h = auth_headers(admin_token)
    resp = client.post("/api/v1/admin/taxonomy/topics", json={"name": "Money", "status": "published"}, headers=h)
    assert resp.status_code == 201, resp.get_json()
    topic_id = resp.get_json()["data"]["id"]
    assert sent.urls == [f"{SITE}/topics/money", f"{SITE}/topics"]
    sent.calls.clear()
    client.put(f"/api/v1/admin/taxonomy/topics/{topic_id}", json={"slug": "money-matters"}, headers=h)
    assert sent.urls == [f"{SITE}/topics/money-matters", f"{SITE}/topics", f"{SITE}/topics/money"]
    sent.calls.clear()
    client.put(f"/api/v1/admin/taxonomy/topics/{topic_id}/status", json={"status": "archived"}, headers=h)
    assert sent.urls == [f"{SITE}/topics/money-matters", f"{SITE}/topics"]
    with app.app_context():
        assert db.session.get(Topic, topic_id).status == "archived"


def test_newsletter_issue_mark_sent_and_archive(client, app, admin_token, sent):
    from app.models.newsletter import NewsletterIssue

    with app.app_context():
        db.session.add(NewsletterIssue(slug="jan", title="Jan", subject="Jan", status="draft",
                                       content=[{"type": "paragraph", "text": "Hello."}]))
        db.session.commit()
    h = auth_headers(admin_token)
    assert client.post("/api/v1/newsletter/issues/jan/mark-sent", headers=h).status_code == 200
    assert sent.urls == [f"{SITE}/newsletter/jan", f"{SITE}/newsletter"]
    sent.calls.clear()
    assert client.post("/api/v1/newsletter/issues/jan/archive", headers=h).status_code == 200
    assert sent.urls == [f"{SITE}/newsletter/jan", f"{SITE}/newsletter"]


@pytest.mark.parametrize("make,public,expected", [
    ("author", "active", {"/authors/s": "/authors"}),
    ("author", "draft", {}),
    ("series", "published", {"/series/s": "/series"}),
    ("series", "archived", {}),
    ("learning", "published", {"/learning/s": "/learning"}),
    ("learning", "draft", {}),
    ("opportunity", "published", {"/opportunities/s": "/opportunities"}),
    ("opportunity", "expired", {}),
    ("page_about", "published", {"/about": None}),
    ("page_about", "draft", {}),
    ("page_general", "published", {}),
    ("advertise", "published", {"/advertise": None}),
    ("community", "draft", {}),
])
def test_public_url_registry_matches_sitemap_rules(app, make, public, expected):
    from app.models.cms import AdvertisePage
    from app.models.community import CommunityPage
    from app.models.learning import LearningProgram
    from app.models.opportunity import Opportunity
    from app.models.page import Page
    from app.models.people import Author
    from app.models.taxonomy import Series

    if make == "author":
        entity = Author(slug="s", name="A", status=public)
    elif make == "series":
        entity = Series(slug="s", name="S", status=public)
    elif make == "learning":
        entity = LearningProgram(slug="s", title="L", status=public)
    elif make == "opportunity":
        expired = public == "expired"
        entity = Opportunity(slug="s", title="O", status="published",
                             expiry_date=date.today() - timedelta(days=1) if expired else None)
    elif make == "page_about":
        entity = Page(key="about", slug="about", title="About", status=public, page_type="system")
    elif make == "page_general":
        entity = Page(key="landing", slug="landing", title="L", status=public, page_type="general")
    elif make == "advertise":
        entity = AdvertisePage(status=public)
    else:
        entity = CommunityPage(status=public)
    assert indexnow.public_urls_for(entity) == expected


def test_job_event_resource_reuse_their_visibility_predicates(app, monkeypatch):
    from app.models.opportunity import Event, Job
    from app.models.resource import Resource

    import app.services.event_registrations as event_svc
    import app.services.job_access as job_svc

    monkeypatch.setattr(job_svc, "is_job_publicly_visible", lambda _j: True)
    monkeypatch.setattr(event_svc, "is_event_publicly_visible", lambda _e: False)
    assert indexnow.public_urls_for(Job(slug="j", title="J")) == {"/jobs/j": "/jobs"}
    assert indexnow.public_urls_for(Event(slug="e", title="E")) == {}
    resource = Resource(slug="r", name="R")
    monkeypatch.setattr(Resource, "is_publicly_visible", lambda self: True)
    assert indexnow.public_urls_for(resource) == {"/resources/r": "/resources"}
