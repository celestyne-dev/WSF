"""Footer route validation regressions (Part E).

Root cause recorded here: the Page picker listed Pages through the
pages.manage-only API, so a footer manager could not pick a Page, the row was
saved as itemType=page with no pageId (or a stale route URL), and the admin
showed only "Validation failed." Page items now validate only their Page id,
route items validate against the real public routes, and errors name the
exact field."""
import pytest

from tests.conftest import auth_headers
from tests.test_footer_cms import _make_page, _make_series, _make_topic, _register_with_role

ADMIN = {"email": "frv-admin@example.com", "password": "supersecret1", "first_name": "F", "last_name": "A"}
FOOTER_ONLY = {"email": "frv-footer@example.com", "password": "supersecret1", "first_name": "F", "last_name": "M"}


@pytest.fixture()
def admin_token(client, app):
    return _register_with_role(client, app, ADMIN, "admin")


@pytest.fixture()
def footer_manager_token(client, app):
    from app.extensions import db
    from app.models.user import Permission, Role

    with app.app_context():
        perms = []
        for name in ("footer.manage", "footer.publish"):
            perm = Permission.query.filter_by(name=name).first() or Permission(name=name)
            db.session.add(perm)
            perms.append(perm)
        role = Role(name="footer_only_test", permissions=perms)
        db.session.add(role)
        db.session.commit()
    return _register_with_role(client, app, FOOTER_ONLY, "footer_only_test")


def _save(client, token, items, heading="Learning"):
    return client.put(
        "/api/v1/admin/footer",
        json={"groups": [{"heading": heading, "visible": True, "items": items}], "socialLinks": [], "settings": {}},
        headers=auth_headers(token),
    )


def _public_items(client):
    groups = client.get("/api/v1/public/footer").get_json()["data"]["groups"]
    return groups[0]["items"] if groups else []


@pytest.mark.parametrize("url", ["/learning", "/learning/paths", "/lifetime", "/submit", "/career-hub", "/topics"])
def test_real_routes_are_valid(client, admin_token, url):
    resp = _save(client, admin_token, [{"label": "Go", "itemType": "route", "url": url}])
    assert resp.status_code == 200, resp.get_json()
    assert _public_items(client)[0]["url"] == url


def test_unknown_route_is_rejected_with_field_message(client, admin_token):
    resp = _save(client, admin_token, [{"label": "A", "itemType": "route", "url": "/learning"},
                                       {"label": "Foo", "itemType": "route", "url": "/foo"}])
    assert resp.status_code == 422
    message = resp.get_json()["error"]["message"] if "error" in resp.get_json() else resp.get_json()["message"]
    assert 'Footer > Learning > Link 2' in message and '"/foo" is not a valid internal route.' in message


def test_page_slug_route_is_valid(client, admin_token, app):
    _make_page(app, key="about-wsf")
    resp = _save(client, admin_token, [{"label": "About", "itemType": "route", "url": "/about-wsf"}])
    assert resp.status_code == 200, resp.get_json()


def test_published_page_link_resolves(client, admin_token, app):
    page_id = _make_page(app, key="frv-published")
    assert _save(client, admin_token, [{"label": "P", "itemType": "page", "pageId": page_id}], heading="About").status_code == 200
    assert _public_items(client)[0]["url"] == "/frv-published"


def test_draft_page_link_saves_but_is_hidden_publicly(client, admin_token, app):
    page_id = _make_page(app, key="frv-draft", status="draft")
    assert _save(client, admin_token, [{"label": "D", "itemType": "page", "pageId": page_id}]).status_code == 200
    assert _public_items(client) == []


def test_page_item_ignores_stale_route_url(client, admin_token, app):
    # itemType=page with a leftover route URL: only the Page id matters.
    page_id = _make_page(app, key="frv-stale")
    resp = _save(client, admin_token, [{"label": "S", "itemType": "page", "pageId": page_id, "url": "/not-a-route"}])
    assert resp.status_code == 200, resp.get_json()
    assert _public_items(client)[0]["url"] == "/frv-stale"


def test_route_to_page_and_back(client, admin_token, app):
    page_id = _make_page(app, key="frv-switch")
    assert _save(client, admin_token, [{"label": "X", "itemType": "route", "url": "/lifetime"}]).status_code == 200
    assert _save(client, admin_token, [{"label": "X", "itemType": "page", "pageId": page_id}]).status_code == 200
    assert _public_items(client)[0]["url"] == "/frv-switch"
    # Page -> route: a stale pageId must not override the route.
    assert _save(client, admin_token, [{"label": "X", "itemType": "route", "url": "/learning/paths", "pageId": page_id}]).status_code == 200
    assert _public_items(client)[0]["url"] == "/learning/paths"


def test_empty_page_names_the_field(client, admin_token):
    resp = _save(client, admin_token, [{"label": "A", "itemType": "route", "url": "/submit"},
                                       {"label": "B", "itemType": "route", "url": "/learning"},
                                       {"label": "Team", "itemType": "page"}], heading="About")
    assert resp.status_code == 422
    body = resp.get_json()
    text = str(body)
    assert "Footer > About > Link 3" in text and "choose a Page." in text


def test_topic_and_series_and_external(client, admin_token, app):
    topic_id = _make_topic(app, slug="frv-topic")
    series_id = _make_series(app, slug="frv-series")
    resp = _save(client, admin_token, [
        {"label": "T", "itemType": "topic", "topicId": topic_id},
        {"label": "S", "itemType": "series", "seriesId": series_id},
        {"label": "E", "itemType": "external", "url": "https://example.org/x"},
    ])
    assert resp.status_code == 200, resp.get_json()
    assert [i["url"] for i in _public_items(client)] == ["/topics/frv-topic", "/series/frv-series", "https://example.org/x"]
    assert "choose a Topic." in str(_save(client, admin_token, [{"label": "T", "itemType": "topic"}]).get_json())
    assert "choose a Series." in str(_save(client, admin_token, [{"label": "S", "itemType": "series"}]).get_json())


def test_footer_manager_can_list_pages_and_save_page_link(client, footer_manager_token, app):
    page_id = _make_page(app, key="frv-for-footer")
    # The old picker used /api/v1/pages (pages.manage only): the root cause.
    assert client.get("/api/v1/pages", headers=auth_headers(footer_manager_token)).status_code == 403
    resp = client.get("/api/v1/admin/destinations/pages?q=frv", headers=auth_headers(footer_manager_token))
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    items = data if isinstance(data, list) else data["items"]
    assert any(p["id"] == page_id and p["path"] == "/frv-for-footer" for p in items)
    assert _save(client, footer_manager_token, [{"label": "P", "itemType": "page", "pageId": page_id}]).status_code == 200


def test_header_and_footer_share_route_validation(app):
    from app.services.spa_shell import known_internal_route

    with app.app_context():
        _check_known(known_internal_route)


def _check_known(known_internal_route):
    for url in ("/learning", "/learning/paths", "/lifetime", "/submit", "/career-hub", "/learning/paths/x"):
        assert known_internal_route(url), url
    for url in ("/foo", "/admin", "/api/v1/x", "javascript:alert(1)"):
        assert not known_internal_route(url), url


def test_published_general_page_is_served_at_its_slug(client, app):
    import os

    app.config["SPA_INDEX_PATH"] = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
    _make_page(app, key="frv-live")
    resp = client.get("/frv-live")
    assert resp.status_code == 200
    assert "<title>A Page" in resp.get_data(as_text=True)
    data = client.get("/api/v1/pages/public/frv-live").get_json()["data"]
    assert data["page_type"] == "general" and data["title"] == "A Page"
    _make_page(app, key="frv-hidden", status="draft")
    assert client.get("/frv-hidden").status_code == 404
    assert client.get("/api/v1/pages/public/frv-hidden").status_code == 404
