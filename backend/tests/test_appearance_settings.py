"""Studio -> Settings -> Appearance (corner style): enum-only storage,
validation, public exposure, and the server-rendered <html> attribute."""
import os

import pytest

from tests.conftest import auth_headers
from tests.test_site_settings import ADMIN_PAYLOAD, _register_with_role

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


@pytest.fixture()
def admin_token(client, app):
    return _register_with_role(client, app, ADMIN_PAYLOAD, "admin")


def _put(client, token, appearance):
    return client.put("/api/v1/admin/settings", json={"settings": {"appearance": appearance}}, headers=auth_headers(token))


def test_default_is_square_everywhere(client, admin_token):
    assert client.get("/api/v1/public/settings").get_json()["data"]["appearance"] == {"cornerStyle": "square"}
    admin = client.get("/api/v1/admin/settings", headers=auth_headers(admin_token)).get_json()["data"]
    assert admin["appearance"] == {"cornerStyle": "square"}


@pytest.mark.parametrize("style", ["square", "subtle", "soft", "rounded"])
def test_each_preset_saves_and_is_public(client, admin_token, style):
    resp = _put(client, admin_token, {"cornerStyle": style})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["data"]["appearance"] == {"cornerStyle": style}
    assert client.get("/api/v1/public/settings").get_json()["data"]["appearance"] == {"cornerStyle": style}


@pytest.mark.parametrize(
    "payload",
    [{"cornerStyle": "12px"}, {"cornerStyle": "border-radius:99px"}, {"cornerStyle": None}, {"customCss": "x"}, "soft", ["soft"]],
)
def test_invalid_values_are_rejected_and_never_stored(client, admin_token, payload):
    assert _put(client, admin_token, {"cornerStyle": "soft"}).status_code == 200
    resp = _put(client, admin_token, payload)
    assert resp.status_code == 422
    assert client.get("/api/v1/public/settings").get_json()["data"]["appearance"] == {"cornerStyle": "soft"}


def test_unknown_stored_value_falls_back_to_the_default(app, client):
    from app.extensions import db
    from app.models.cms import SiteSetting

    with app.app_context():
        db.session.add(SiteSetting(key="appearance", value={"corner_style": "<script>"}))
        db.session.commit()
    assert client.get("/api/v1/public/settings").get_json()["data"]["appearance"] == {"cornerStyle": "square"}


def test_saving_requires_settings_permission(client):
    resp = client.put("/api/v1/admin/settings", json={"settings": {"appearance": {"cornerStyle": "soft"}}})
    assert resp.status_code in (401, 403)


def test_every_shell_response_carries_the_corner_attribute(client, app, admin_token):
    from app.extensions import db
    from app.models.people import Author

    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    with app.app_context():
        db.session.add(Author(slug="corner-author", name="Corner Author", status="active", bio=[{"type": "paragraph", "text": "Bio."}]))
        db.session.commit()
    paths = ("/", "/corner-author-missing", "/authors/corner-author", "/login", "/admin")
    for path in paths:
        html = client.get(path).get_data(as_text=True)
        assert html.count("data-wsf-corners=") == 1, path
        assert '<html lang="en" data-wsf-corners="square" data-wsf-consent-version="1">' in html, path
    assert _put(client, admin_token, {"cornerStyle": "rounded"}).status_code == 200
    for path in paths:
        html = client.get(path).get_data(as_text=True)
        assert html.count("data-wsf-corners=") == 1 and 'data-wsf-corners="rounded"' in html, path
        assert '<html lang="en" data-wsf-corners="rounded" data-wsf-consent-version="1">' in html, path
