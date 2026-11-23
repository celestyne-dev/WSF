"""Studio -> Integrations: GA4 Measurement ID (app/services/tracking_settings.py)."""
from tests.conftest import auth_headers
from tests.test_footer_cms import _register_with_role

ADMIN = {"email": "trk-admin@example.com", "password": "supersecret1", "first_name": "T", "last_name": "A"}


def _put(client, token, body):
    return client.put("/api/v1/admin/settings", json={"settings": {"tracking": body}}, headers=auth_headers(token))


def test_inactive_by_default_nothing_public(client):
    data = client.get("/api/v1/public/settings").get_json()["data"]
    assert data["tracking"] == {}


def test_valid_id_is_saved_normalised_audited_and_public(client, app):
    token = _register_with_role(client, app, ADMIN, "admin")
    res = _put(client, token, {"ga4MeasurementId": "  g-abc123xyz9 "})
    assert res.status_code == 200
    assert res.get_json()["data"]["tracking"]["ga4MeasurementId"] == "G-ABC123XYZ9"
    assert client.get("/api/v1/public/settings").get_json()["data"]["tracking"] == {"ga4MeasurementId": "G-ABC123XYZ9"}
    with app.app_context():
        from app.models.audit import AuditLog

        assert AuditLog.query.filter_by(action="settings.update", entity_id="tracking").count() == 1
    # Clearing it switches GA4 off again.
    assert _put(client, token, {"ga4MeasurementId": ""}).status_code == 200
    assert client.get("/api/v1/public/settings").get_json()["data"]["tracking"] == {}


def test_only_a_bare_id_is_accepted(client, app):
    token = _register_with_role(client, app, ADMIN, "admin")
    for bad in ["UA-12345-1", "<script>alert(1)</script>", "https://www.googletagmanager.com/gtag/js?id=G-1234",
                "G-12", "G-ABC 123", 42]:
        res = _put(client, token, {"ga4MeasurementId": bad})
        assert res.status_code == 422, bad
    assert _put(client, token, {"unknownTag": "x"}).status_code == 422


def test_non_admins_cannot_change_it(client):
    res = client.post("/api/v1/auth/register", json={"email": "trk-m@example.com", "password": "supersecret1",
                                                      "first_name": "M", "last_name": "M"})
    token = res.get_json()["data"]["access_token"]
    assert _put(client, token, {"ga4MeasurementId": "G-ABC123XYZ9"}).status_code == 403


def test_linkedin_and_meta_ids(client, app):
    token = _register_with_role(client, app, ADMIN, "admin")
    assert _put(client, token, {"linkedinPartnerId": " 1234567 ", "metaPixelId": "123456789012345"}).status_code == 200
    assert client.get("/api/v1/public/settings").get_json()["data"]["tracking"] == {
        "linkedinPartnerId": "1234567", "metaPixelId": "123456789012345"}
    for key, bad in [("linkedinPartnerId", "li-123"), ("linkedinPartnerId", "<img src=x>"),
                     ("metaPixelId", "12345"), ("metaPixelId", "https://connect.facebook.net/x")]:
        assert _put(client, token, {key: bad}).status_code == 422, (key, bad)


def test_audit_cli_reports_configuration(client, app):
    token = _register_with_role(client, app, ADMIN, "admin")
    out = app.test_cli_runner().invoke(args=["legal-pages-audit"]).output
    assert "Google Analytics 4 (_ga, _ga_<container-id> cookies): not configured (inactive)" in out
    _put(client, token, {"metaPixelId": "123456789012345"})
    out = app.test_cli_runner().invoke(args=["legal-pages-audit"]).output
    assert "Meta Pixel (_fbp, _fbc cookies): CONFIGURED (runs only with consent)" in out
    assert "LinkedIn Insight Tag: not configured (inactive)" in out
