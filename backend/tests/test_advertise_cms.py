import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "advertise-manager@example.com",
    "password": "supersecret1",
    "first_name": "Diana",
    "last_name": "Kioko",
    "country_code": "KE",
}

NO_PERMISSION_PAYLOAD = {
    "email": "advertise-nobody@example.com",
    "password": "supersecret1",
    "first_name": "No",
    "last_name": "Permission",
    "country_code": "US",
}


def _register_with_role(client, app, payload, role_name):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        role = Role.query.filter_by(name=role_name).first()
        user.roles.append(role)
        db.session.commit()

    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def manager_token(client, app):
    return _register_with_role(client, app, MANAGER_PAYLOAD, "partnerships_manager")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


def _make_page(app, status="draft", **overrides):
    from app.extensions import db
    from app.models.cms import AdvertisePage

    with app.app_context():
        page = db.session.get(AdvertisePage, 1)
        if page is None:
            page = AdvertisePage(id=1)
            db.session.add(page)
        page.hero_heading = overrides.get("hero_heading", "Advertise With Us")
        page.hero_description = overrides.get("hero_description", "Reach our audience.")
        page.status = status
        for key, value in overrides.items():
            setattr(page, key, value)
        db.session.commit()


def _make_metric(app, label="LinkedIn followers", value="132,000+", public_visible=True, order=0):
    from app.extensions import db
    from app.models.cms import AdvertiseMetric

    with app.app_context():
        metric = AdvertiseMetric(
            label=label, value=value, source_note="Pulled from LinkedIn analytics dashboard.",
            public_visible=public_visible, display_order=order,
        )
        db.session.add(metric)
        db.session.commit()
        return metric.id


def _make_offering(app, name="Newsletter Sponsorship", status="active", pricing_mode="contact", **overrides):
    from app.extensions import db
    from app.models.cms import AdvertiseOffering

    with app.app_context():
        offering = AdvertiseOffering(name=name, status=status, pricing_mode=pricing_mode, **overrides)
        db.session.add(offering)
        db.session.commit()
        return offering.id


class TestPublicAdvertisePage:
    def test_404_when_page_not_published(self, client, app):
        resp = client.get("/api/v1/advertise/public")
        assert resp.status_code == 404

    def test_404_when_page_draft(self, client, app):
        _make_page(app, status="draft")
        resp = client.get("/api/v1/advertise/public")
        assert resp.status_code == 404

    def test_returns_published_page_with_metrics_and_offerings(self, client, app):
        _make_page(app, status="published")
        _make_metric(app, label="Newsletter subscribers", value="34,210+", public_visible=True)
        _make_metric(app, label="Internal only metric", value="7", public_visible=False)
        _make_offering(app, name="Newsletter Sponsorship", status="active")
        _make_offering(app, name="Draft Offering", status="hidden")

        resp = client.get("/api/v1/advertise/public")
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert data["page"]["hero"]["heading"] == "Advertise With Us"
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["label"] == "Newsletter subscribers"
        assert "sourceNote" not in data["metrics"][0]

        assert len(data["offerings"]) == 1
        assert data["offerings"][0]["name"] == "Newsletter Sponsorship"

    def test_pricing_mode_hidden_excludes_price_and_note(self, client, app):
        _make_page(app, status="published")
        _make_offering(
            app, name="Custom Package", pricing_mode="hidden", price_amount=5000, currency="USD",
            pricing_note="Internal target price",
        )
        resp = client.get("/api/v1/advertise/public")
        offering = resp.get_json()["data"]["offerings"][0]
        assert "priceAmount" not in offering
        assert "currency" not in offering
        assert "pricingNote" not in offering

    def test_pricing_mode_fixed_includes_price(self, client, app):
        _make_page(app, status="published")
        _make_offering(
            app, name="Sidebar Package", pricing_mode="fixed", price_amount=1200, currency="EUR",
            pricing_note="Billed monthly",
        )
        resp = client.get("/api/v1/advertise/public")
        offering = resp.get_json()["data"]["offerings"][0]
        assert offering["priceAmount"] == 1200
        assert offering["currency"] == "EUR"
        assert offering["pricingNote"] == "Billed monthly"

    def test_media_kit_omitted_when_no_url(self, client, app):
        _make_page(app, status="published")
        resp = client.get("/api/v1/advertise/public")
        assert resp.get_json()["data"]["page"]["mediaKit"] is None

    def test_media_kit_present_when_url_set(self, client, app):
        _make_page(app, status="published", media_kit_url="https://cdn.example.com/media-kit.pdf", media_kit_title="2026 Media Kit")
        resp = client.get("/api/v1/advertise/public")
        media_kit = resp.get_json()["data"]["page"]["mediaKit"]
        assert media_kit["url"] == "https://cdn.example.com/media-kit.pdf"
        assert media_kit["title"] == "2026 Media Kit"


class TestAdminAdvertisePage:
    def test_get_requires_permission(self, client, app, no_permission_token):
        _make_page(app)
        resp = client.get("/api/v1/advertise/page", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

    def test_get_page(self, client, app, manager_token):
        _make_page(app)
        resp = client.get("/api/v1/advertise/page", headers=auth_headers(manager_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "draft"

    def test_patch_updates_fields(self, client, app, manager_token):
        _make_page(app)
        resp = client.patch(
            "/api/v1/advertise/page",
            json={"heroHeading": "New Heading", "audienceOverview": "Global reach."},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["hero_heading"] == "New Heading"
        assert resp.get_json()["data"]["audience_overview"] == "Global reach."

    def test_patch_does_not_reset_untouched_fields(self, client, app, manager_token):
        _make_page(app, hero_description="Original description")
        client.patch(
            "/api/v1/advertise/page", json={"heroHeading": "Only heading changes"},
            headers=auth_headers(manager_token),
        )
        resp = client.get("/api/v1/advertise/page", headers=auth_headers(manager_token))
        assert resp.get_json()["data"]["hero_description"] == "Original description"

    def test_patch_cannot_set_status(self, client, app, manager_token):
        _make_page(app, status="draft")
        client.patch("/api/v1/advertise/page", json={"status": "published"}, headers=auth_headers(manager_token))
        resp = client.get("/api/v1/advertise/page", headers=auth_headers(manager_token))
        assert resp.get_json()["data"]["status"] == "draft"

    def test_patch_sanitizes_content_blocks(self, client, app, manager_token):
        _make_page(app)
        resp = client.patch(
            "/api/v1/advertise/page",
            json={"introContent": [{"type": "paragraph", "text": "<script>alert(1)</script>Hello"}]},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        block = resp.get_json()["data"]["intro_content"][0]
        assert "<script>" not in block["text"]

    def test_status_action_publishes(self, client, app, manager_token):
        _make_page(app, status="draft")
        resp = client.patch(
            "/api/v1/advertise/page/status", json={"status": "published"}, headers=auth_headers(manager_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "published"

    def test_status_action_rejects_invalid_value(self, client, app, manager_token):
        _make_page(app)
        resp = client.patch(
            "/api/v1/advertise/page/status", json={"status": "not-a-status"}, headers=auth_headers(manager_token)
        )
        assert resp.status_code == 422


class TestAdvertiseMetrics:
    def test_create_metric(self, client, app, manager_token):
        resp = client.post(
            "/api/v1/advertise/metrics",
            json={"label": "Podcast downloads", "value": "18,400+", "unit": "downloads", "displayOrder": 5},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["label"] == "Podcast downloads"
        assert resp.get_json()["data"]["public_visible"] is True

    def test_create_metric_requires_permission(self, client, app, no_permission_token):
        resp = client.post(
            "/api/v1/advertise/metrics", json={"label": "X", "value": "1"},
            headers=auth_headers(no_permission_token),
        )
        assert resp.status_code == 403

    def test_update_metric_partial_preserves_other_fields(self, client, app, manager_token):
        metric_id = _make_metric(app, label="Countries reached", value="42")
        resp = client.patch(
            f"/api/v1/advertise/metrics/{metric_id}", json={"publicVisible": False},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["public_visible"] is False
        assert data["label"] == "Countries reached"
        assert data["value"] == "42"

    def test_delete_metric(self, client, app, manager_token):
        metric_id = _make_metric(app)
        resp = client.delete(f"/api/v1/advertise/metrics/{metric_id}", headers=auth_headers(manager_token))
        assert resp.status_code == 204
        resp = client.get("/api/v1/advertise/metrics", headers=auth_headers(manager_token))
        assert resp.get_json()["data"] == []

    def test_update_missing_metric_404(self, client, app, manager_token):
        resp = client.patch("/api/v1/advertise/metrics/999", json={"label": "X"}, headers=auth_headers(manager_token))
        assert resp.status_code == 404


class TestAdvertiseOfferings:
    def test_create_offering(self, client, app, manager_token):
        resp = client.post(
            "/api/v1/advertise/offerings",
            json={"name": "Homepage Takeover", "pricingMode": "starting_from", "priceAmount": 2000, "currency": "USD"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["name"] == "Homepage Takeover"

    def test_create_offering_requires_price_for_starting_from(self, client, app, manager_token):
        resp = client.post(
            "/api/v1/advertise/offerings", json={"name": "No Price", "pricingMode": "starting_from"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_create_offering_allows_no_price_for_contact_mode(self, client, app, manager_token):
        resp = client.post(
            "/api/v1/advertise/offerings", json={"name": "Contact Us", "pricingMode": "contact"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201

    def test_update_offering_partial_preserves_pricing(self, client, app, manager_token):
        offering_id = _make_offering(app, name="Sidebar", pricing_mode="fixed", price_amount=500, currency="GBP")
        resp = client.patch(
            f"/api/v1/advertise/offerings/{offering_id}", json={"featured": True},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["featured"] is True
        assert data["price_amount"] == 500
        assert data["currency"] == "GBP"

    def test_update_offering_status(self, client, app, manager_token):
        offering_id = _make_offering(app, status="active")
        resp = client.patch(
            f"/api/v1/advertise/offerings/{offering_id}", json={"status": "hidden"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "hidden"

    def test_delete_offering(self, client, app, manager_token):
        offering_id = _make_offering(app)
        resp = client.delete(f"/api/v1/advertise/offerings/{offering_id}", headers=auth_headers(manager_token))
        assert resp.status_code == 204


class TestAdvertiseHistory:
    def test_history_records_page_and_metric_actions(self, client, app, manager_token):
        _make_page(app)
        client.patch("/api/v1/advertise/page", json={"heroHeading": "Updated"}, headers=auth_headers(manager_token))
        client.post(
            "/api/v1/advertise/metrics", json={"label": "X", "value": "1"}, headers=auth_headers(manager_token)
        )
        resp = client.get("/api/v1/advertise/history", headers=auth_headers(manager_token))
        assert resp.status_code == 200
        actions = {entry["action"] for entry in resp.get_json()["data"]}
        assert "advertise.page_update" in actions
        assert "advertise.metric_create" in actions


class TestAdvertisingInquiryReusesPartnerships:
    """The public Advertise inquiry form posts to the existing
    partnerships endpoint with partnershipType=Advertising — no new
    inquiry route or model.
    """

    def test_advertising_inquiry_accepted(self, client, app):
        payload = {
            "contactName": "Amara Diallo",
            "email": "amara@brandco.com",
            "company": "Brand Co",
            "partnershipType": "Advertising",
            "subject": "Interested in Newsletter Sponsorship",
            "message": "We'd like to discuss the newsletter sponsorship package.",
            "consentGiven": True,
        }
        resp = client.post("/api/v1/partnerships/inquiries", json=payload)
        assert resp.status_code == 201

    def test_advertising_inquiry_listed_and_filterable_by_admin(self, client, app, manager_token):
        payload = {
            "contactName": "Amara Diallo", "email": "amara@brandco.com", "company": "Brand Co",
            "partnershipType": "Advertising", "consentGiven": True,
        }
        client.post("/api/v1/partnerships/inquiries", json=payload)
        resp = client.get(
            "/api/v1/partnerships/inquiries?partnershipType=Advertising", headers=auth_headers(manager_token)
        )
        assert resp.status_code == 200
        assert len(resp.get_json()["data"]) == 1
        assert resp.get_json()["data"][0]["partnership_type"] == "Advertising"

    def test_invalid_partnership_type_still_rejected(self, client, app):
        payload = {
            "contactName": "Amara Diallo", "email": "amara@brandco.com", "company": "Brand Co",
            "partnershipType": "Not A Real Type", "consentGiven": True,
        }
        resp = client.post("/api/v1/partnerships/inquiries", json=payload)
        assert resp.status_code == 422
