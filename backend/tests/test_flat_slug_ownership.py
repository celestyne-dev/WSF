"""Flat public namespace (/<slug>): one owner per slug across Articles,
general Pages, Article Redirects and reserved routes
(app/services/flat_slugs.py)."""
import pytest

from tests.conftest import auth_headers
from tests.test_footer_cms import _register_with_role

EDITOR = {"email": "flat-editor@example.com", "password": "supersecret1", "first_name": "F", "last_name": "E"}


@pytest.fixture()
def token(client, app):
    return _register_with_role(client, app, EDITOR, "editor")


@pytest.fixture()
def author(client, token):
    return client.post("/api/v1/authors", json={"name": "Flat Author"}, headers=auth_headers(token)).get_json()["data"]["slug"]


def _article(client, token, author, title, slug=None):
    body = {"title": title, "authorSlug": author}
    if slug:
        body["slug"] = slug
    return client.post("/api/v1/articles", json=body, headers=auth_headers(token))


def _page(client, token, title, slug=None):
    body = {"title": title}
    if slug:
        body["slug"] = slug
    return client.post("/api/v1/pages", json=body, headers=auth_headers(token))


def _code(resp):
    return resp.get_json()["error"]["code"]


def _redirect(app, from_slug, to_slug="new-home"):
    from app.extensions import db
    from app.models.article import Redirect

    with app.app_context():
        db.session.add(Redirect(from_slug=from_slug, to_slug=to_slug))
        db.session.commit()


# --- Page exists first ------------------------------------------------------------------

def test_article_explicit_slug_owned_by_page_is_rejected(client, token, author):
    assert _page(client, token, "Press Kit", slug="press-kit").status_code == 201
    resp = _article(client, token, author, "Anything", slug="press-kit")
    assert resp.status_code == 409 and _code(resp) == "slug_taken"
    assert "a page" in resp.get_json()["error"]["message"]


def test_article_generated_slug_steps_past_page(client, token, author):
    assert _page(client, token, "Press Kit", slug="press-kit").status_code == 201
    resp = _article(client, token, author, "Press Kit")
    assert resp.status_code == 201 and resp.get_json()["data"]["slug"] == "press-kit-2"


def test_article_rename_to_page_slug_is_rejected(client, token, author):
    assert _page(client, token, "Press Kit", slug="press-kit").status_code == 201
    slug = _article(client, token, author, "Movable").get_json()["data"]["slug"]
    resp = client.put(f"/api/v1/articles/{slug}", json={"title": "Movable", "authorSlug": author, "slug": "press-kit"},
                      headers=auth_headers(token))
    assert resp.status_code == 409 and _code(resp) == "slug_taken"


# --- Article exists first ---------------------------------------------------------------

def test_page_explicit_slug_owned_by_article_is_rejected(client, token, author):
    assert _article(client, token, author, "Press Kit", slug="press-kit").status_code == 201
    resp = _page(client, token, "Media", slug="press-kit")
    assert resp.status_code == 409 and _code(resp) == "slug_taken"
    assert "an article" in resp.get_json()["error"]["message"]


def test_page_generated_slug_steps_past_article(client, token, author):
    assert _article(client, token, author, "Press Kit", slug="press-kit").status_code == 201
    resp = _page(client, token, "Press Kit")
    assert resp.status_code == 201 and resp.get_json()["data"]["slug"] == "press-kit-2"


def test_page_rename_to_article_slug_is_rejected(client, token, author):
    assert _article(client, token, author, "Press Kit", slug="press-kit").status_code == 201
    page = _page(client, token, "Media").get_json()["data"]
    resp = client.put(f"/api/v1/pages/{page['id']}", json={"slug": "press-kit"}, headers=auth_headers(token))
    assert resp.status_code == 409 and _code(resp) == "slug_taken"


# --- Article Redirect owns the slug -----------------------------------------------------

def test_page_cannot_claim_a_redirect_slug(client, app, token):
    _redirect(app, "old-story")
    resp = _page(client, token, "Old Story", slug="old-story")
    assert resp.status_code == 409 and _code(resp) == "slug_taken"
    assert "redirects" in resp.get_json()["error"]["message"]
    generated = _page(client, token, "Old Story")
    assert generated.status_code == 201 and generated.get_json()["data"]["slug"] == "old-story-2"


def test_generated_article_slug_does_not_hijack_a_redirect(client, app, token, author):
    _redirect(app, "old-story")
    resp = _article(client, token, author, "Old Story")
    assert resp.status_code == 201 and resp.get_json()["data"]["slug"] == "old-story-2"


def test_article_may_deliberately_reclaim_a_redirect_slug(client, app, token, author):
    from app.models.article import Redirect

    _redirect(app, "old-story")
    resp = _article(client, token, author, "Old Story Returns", slug="old-story")
    assert resp.status_code == 201 and resp.get_json()["data"]["slug"] == "old-story"
    with app.app_context():
        assert Redirect.query.filter_by(from_slug="old-story").first() is None  # one owner only


def test_article_rename_back_to_its_own_old_slug(client, app, token, author):
    from app.models.article import Redirect

    _article(client, token, author, "Round Trip", slug="round-trip")
    body = {"title": "Round Trip", "authorSlug": author}
    assert client.put("/api/v1/articles/round-trip", json={**body, "slug": "round-trip-new"}, headers=auth_headers(token)).status_code == 200
    resp = client.put("/api/v1/articles/round-trip-new", json={**body, "slug": "round-trip"}, headers=auth_headers(token))
    assert resp.status_code == 200
    with app.app_context():
        assert Redirect.query.filter_by(from_slug="round-trip").first() is None
        assert Redirect.query.filter_by(from_slug="round-trip-new").first().to_slug == "round-trip"


# --- Reserved and unrelated ----------------------------------------------------------------

@pytest.mark.parametrize("make", ["article", "page"])
def test_reserved_route_lifetime_is_rejected(client, token, author, make):
    resp = _article(client, token, author, "X", slug="lifetime") if make == "article" else _page(client, token, "X", slug="lifetime")
    assert resp.status_code == 400 and _code(resp) == "reserved_slug"
    generated = _article(client, token, author, "Lifetime") if make == "article" else _page(client, token, "Lifetime")
    assert generated.get_json()["data"]["slug"] == "lifetime-2"


def test_unrelated_slugs_work(client, token, author):
    assert _article(client, token, author, "A Fine Story", slug="a-fine-story").status_code == 201
    assert _page(client, token, "Our Mission", slug="our-mission").status_code == 201
    assert _article(client, token, author, "Second Story").get_json()["data"]["slug"] == "second-story"
    assert _page(client, token, "Press Room").get_json()["data"]["slug"] == "press-room"


def test_owner_helper_only_covers_the_flat_namespace(app):
    from app.services.flat_slugs import flat_public_slug_owner

    with app.app_context():
        assert flat_public_slug_owner("lifetime") == "reserved"
        assert flat_public_slug_owner("nobody-owns-this") is None
