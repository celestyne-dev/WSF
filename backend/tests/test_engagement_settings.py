"""Studio settings for the newsletter popup and cookie consent: validated
plain text and bounded numbers, no script fields, public payload."""
from tests.conftest import auth_headers
from tests.test_footer_cms import _register_with_role

ADMIN = {"email": "eng-admin@example.com", "password": "supersecret1", "first_name": "E", "last_name": "A"}


def _put(client, token, body):
    return client.put("/api/v1/admin/settings", json={"settings": body}, headers=auth_headers(token))


def test_defaults_are_public(client):
    data = client.get("/api/v1/public/settings").get_json()["data"]
    assert data["newsletterPopup"]["delaySeconds"] == 15 and data["newsletterPopup"]["scrollPercent"] == 45
    assert data["newsletterPopup"]["enabled"] is True
    assert data["cookieConsent"]["version"] == "1" and data["cookieConsent"]["bannerEnabled"] is True


def test_save_and_read_back(client, app):
    token = _register_with_role(client, app, ADMIN, "admin")
    resp = _put(client, token, {"newsletter_popup": {"delaySeconds": 30, "scrollPercent": 60, "dismissDays": 7,
                                                     "title": "WSF Weekly", "ctaLabel": "Subscribe"},
                                "cookie_consent": {"version": "2026-11", "bannerEnabled": True}})
    assert resp.status_code == 200, resp.get_json()
    data = client.get("/api/v1/public/settings").get_json()["data"]
    assert data["newsletterPopup"]["delaySeconds"] == 30 and data["newsletterPopup"]["ctaLabel"] == "Subscribe"
    assert data["cookieConsent"]["version"] == "2026-11"


def test_invalid_values_rejected(client, app):
    token = _register_with_role(client, app, ADMIN, "admin")
    for body in (
        {"newsletter_popup": {"delaySeconds": -1}},
        {"newsletter_popup": {"scrollPercent": 150}},
        {"newsletter_popup": {"title": "<script>alert(1)</script>"}},
        {"newsletter_popup": {"body": 'Click <a href="x">here</a>'}},
        {"newsletter_popup": {"snippet": "gtag('config')"}},
        {"cookie_consent": {"essential": False}},
        {"cookie_consent": {"analyticsScript": "<script src=x>"}},
        {"cookie_consent": {"version": "has spaces!"}},
    ):
        assert _put(client, token, body).status_code == 422, body
