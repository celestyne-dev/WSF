import io

import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {
    "email": "settingsadmin@example.com",
    "password": "supersecret1",
    "first_name": "Ada",
    "last_name": "Min",
}


def _register_with_role(client, app, payload, role_name):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        if role_name:
            role = Role.query.filter_by(name=role_name).first()
            user.roles.append(role)
            db.session.commit()

    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def admin_token(client, app):
    return _register_with_role(client, app, ADMIN_PAYLOAD, "admin")


def _tiny_png():
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload_media(client, admin_token, filename="logo.png"):
    resp = client.post(
        "/api/v1/media/upload",
        data={"file": (io.BytesIO(_tiny_png()), filename), "alt_text": "Test image"},
        content_type="multipart/form-data",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]["id"]


def _put_identity(client, admin_token, **fields):
    return client.put(
        "/api/v1/admin/settings",
        json={"settings": {"site_identity": fields}},
        headers=auth_headers(admin_token),
    )


class TestPublicAndAdminRetrieval:
    def test_public_settings_default_before_any_save(self, client):
        resp = client.get("/api/v1/public/settings")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        # Site name has a real, non-fake structural default; every other
        # field is None (never a fabricated contact/social/SEO value).
        assert body["site"]["name"] == "Women Shaping Futures"
        assert body["contact"]["email"] is None
        assert body["seo"]["defaultTitle"] is None
        assert body["branding"]["logo"] is None

    def test_admin_get_requires_settings_manage(self, client, admin_token):
        resp = client.get("/api/v1/admin/settings", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        assert "site_identity" in resp.get_json()["data"]
        assert "audience_stats" in resp.get_json()["data"]


class TestSiteIdentityUpdate:
    def test_update_round_trips_through_public_and_admin(self, client, admin_token):
        saved = _put_identity(
            client,
            admin_token,
            siteName="WSF Test",
            shortName="WSFT",
            tagline="A test tagline",
            contactEmail="hello@example.com",
            seoDefaultTitle="WSF Test Title",
            seoDefaultDescription="A description under the limit.",
        )
        assert saved.status_code == 200
        identity = saved.get_json()["data"]["site_identity"]
        assert identity["siteName"] == "WSF Test"
        assert identity["shortName"] == "WSFT"
        assert identity["contactEmail"] == "hello@example.com"

        public = client.get("/api/v1/public/settings").get_json()["data"]
        assert public["site"]["name"] == "WSF Test"
        assert public["site"]["tagline"] == "A test tagline"
        assert public["contact"]["email"] == "hello@example.com"
        assert public["seo"]["defaultTitle"] == "WSF Test Title"

    def test_singleton_repeated_saves_do_not_duplicate(self, client, admin_token, app):
        from app.models.cms import SiteSetting

        _put_identity(client, admin_token, siteName="First Save")
        _put_identity(client, admin_token, siteName="Second Save")
        _put_identity(client, admin_token, siteName="Third Save")

        with app.app_context():
            rows = SiteSetting.query.filter_by(key="site_identity").all()
            assert len(rows) == 1
            assert rows[0].value["site_name"] == "Third Save"

    def test_updating_site_identity_does_not_touch_audience_stats(self, client, admin_token):
        client.put(
            "/api/v1/admin/settings",
            json={"settings": {"audience_stats": {"linkedinFollowers": 500}}},
            headers=auth_headers(admin_token),
        )
        _put_identity(client, admin_token, siteName="Only Identity Changed")

        data = client.get("/api/v1/admin/settings", headers=auth_headers(admin_token)).get_json()["data"]
        assert data["site_identity"]["siteName"] == "Only Identity Changed"
        assert data["audience_stats"]["linkedinFollowers"] == 500

    def test_updating_audience_stats_does_not_touch_site_identity(self, client, admin_token):
        _put_identity(client, admin_token, siteName="Stable Identity")
        client.put(
            "/api/v1/admin/settings",
            json={"settings": {"audience_stats": {"linkedinFollowers": 999}}},
            headers=auth_headers(admin_token),
        )
        data = client.get("/api/v1/admin/settings", headers=auth_headers(admin_token)).get_json()["data"]
        assert data["site_identity"]["siteName"] == "Stable Identity"


class TestValidation:
    def test_site_name_is_required(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/settings",
            json={"settings": {"site_identity": {"tagline": "No name given"}}},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_site_name_rejects_html(self, client, admin_token):
        resp = _put_identity(client, admin_token, siteName="<script>alert(1)</script>")
        assert resp.status_code == 422

    def test_tagline_over_max_length_rejected(self, client, admin_token):
        resp = _put_identity(client, admin_token, siteName="WSF", tagline="x" * 161)
        assert resp.status_code == 422

    def test_invalid_email_rejected(self, client, admin_token):
        resp = _put_identity(client, admin_token, siteName="WSF", contactEmail="not-an-email")
        assert resp.status_code == 422

    def test_unknown_field_rejected(self, client, admin_token):
        # Includes an attempt to sneak in a domain-controlling field —
        # the canonical site URL is deliberately not editable here (see
        # SiteSettingsResource's docstring in api/v1/public.py), so an
        # admin can never accidentally break routing/CORS by editing it.
        resp = client.put(
            "/api/v1/admin/settings",
            json={"settings": {"site_identity": {"siteName": "WSF", "siteUrl": "https://evil.example.com"}}},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_unknown_top_level_settings_key_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/settings",
            json={"settings": {"site_nmae": {"siteName": "Typo"}}},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_nonexistent_logo_media_id_rejected(self, client, admin_token):
        resp = _put_identity(client, admin_token, siteName="WSF", logoMediaId=999999)
        assert resp.status_code == 422


class TestMediaReferences:
    def test_logo_and_og_image_resolve_to_real_media(self, client, admin_token):
        logo_id = _upload_media(client, admin_token, "logo.png")
        og_id = _upload_media(client, admin_token, "og.png")

        saved = _put_identity(client, admin_token, siteName="WSF", logoMediaId=logo_id, ogImageMediaId=og_id)
        assert saved.status_code == 200
        identity = saved.get_json()["data"]["site_identity"]
        assert identity["logo"]["id"] == logo_id
        assert "publicUrl" in identity["logo"] or "public_url" in identity["logo"]
        assert identity["ogImage"]["id"] == og_id

        public = client.get("/api/v1/public/settings").get_json()["data"]
        assert public["branding"]["logo"]["id"] == logo_id
        assert public["seo"]["defaultOgImage"]["id"] == og_id

    def test_clearing_logo_does_not_delete_the_media_record(self, client, admin_token, app):
        from app.models.media import Media

        logo_id = _upload_media(client, admin_token, "logo2.png")
        _put_identity(client, admin_token, siteName="WSF", logoMediaId=logo_id)
        _put_identity(client, admin_token, siteName="WSF")  # omit logoMediaId -> cleared

        public = client.get("/api/v1/public/settings").get_json()["data"]
        assert public["branding"]["logo"] is None

        with app.app_context():
            assert Media.query.get(logo_id) is not None


class TestSocialProfilesReadThrough:
    """Social profile URLs stay owned by Footer CMS (see
    app/services/site_settings.py's module docstring) — Site Settings
    only reads the same real SocialLink rows for its public payload, so
    there is exactly one editable copy of each URL.
    """

    def test_public_social_reflects_footer_owned_links_and_visibility(self, client, admin_token):
        footer_payload = {
            "groups": [],
            "socialLinks": [
                {"platform": "linkedin", "url": "https://linkedin.com/company/wsf-test", "visible": True},
                {"platform": "instagram", "url": "https://instagram.com/wsf-test", "visible": False},
            ],
            "settings": {},
        }
        put = client.put("/api/v1/admin/footer", json=footer_payload, headers=auth_headers(admin_token))
        assert put.status_code == 200

        public = client.get("/api/v1/public/settings").get_json()["data"]
        platforms = [s["platform"] for s in public["social"]]
        assert platforms == ["linkedin"]
        assert public["social"][0]["url"] == "https://linkedin.com/company/wsf-test"

        _put_identity(client, admin_token, siteName="Unrelated Save")
        public_after = client.get("/api/v1/public/settings").get_json()["data"]
        assert [s["platform"] for s in public_after["social"]] == ["linkedin"]


class TestPublicSerializerMinimization:
    def test_public_payload_has_no_admin_or_internal_fields(self, client, admin_token):
        _put_identity(client, admin_token, siteName="WSF", contactEmail="hello@example.com")
        public = client.get("/api/v1/public/settings").get_json()["data"]

        assert "audience_stats" not in public
        assert set(public.keys()) == {"site", "branding", "contact", "social", "seo"}
        # Media is dumped through the same public-safe schema every other
        # public endpoint already uses — never a raw filesystem path.
        logo_id = _upload_media(client, admin_token, "logo3.png")
        _put_identity(client, admin_token, siteName="WSF", logoMediaId=logo_id)
        public_with_logo = client.get("/api/v1/public/settings").get_json()["data"]
        assert "file_path" not in public_with_logo["branding"]["logo"]
        assert "filePath" not in public_with_logo["branding"]["logo"]

    def test_no_secret_or_environment_exposure(self, client):
        public = client.get("/api/v1/public/settings").get_json()["data"]
        dumped = str(public)
        assert "SECRET" not in dumped.upper() or "secret" not in public.get("site", {}).get("name", "")
        assert "JWT_SECRET_KEY" not in dumped
        assert "DATABASE_URL" not in dumped


class TestRBAC:
    def test_no_permission_role_denied_get_and_put(self, client, app):
        token = _register_with_role(
            client, app, {"email": "member@example.com", "password": "supersecret1", "first_name": "M", "last_name": "B"}, None
        )
        assert client.get("/api/v1/admin/settings", headers=auth_headers(token)).status_code == 403
        assert (
            client.put(
                "/api/v1/admin/settings",
                json={"settings": {"site_identity": {"siteName": "Hacked"}}},
                headers=auth_headers(token),
            ).status_code
            == 403
        )

    def test_editor_without_settings_manage_denied(self, client, app):
        # editor already has several .manage permissions but not
        # settings.manage (see app/services/rbac.py) — global identity
        # stays admin/super_admin only, as this task requires.
        token = _register_with_role(
            client, app, {"email": "editor@example.com", "password": "supersecret1", "first_name": "E", "last_name": "D"}, "editor"
        )
        assert client.get("/api/v1/admin/settings", headers=auth_headers(token)).status_code == 403

    def test_super_admin_can_manage_settings(self, client, app):
        token = _register_with_role(
            client, app, {"email": "super@example.com", "password": "supersecret1", "first_name": "S", "last_name": "A"}, "super_admin"
        )
        resp = client.put(
            "/api/v1/admin/settings",
            json={"settings": {"site_identity": {"siteName": "Super Admin Edit"}}},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    def test_missing_token_returns_401(self, client):
        assert client.get("/api/v1/admin/settings").status_code == 401


class TestAuditLogging:
    def test_update_writes_audit_log_entry_without_secrets(self, client, admin_token, app):
        from app.models.audit import AuditLog

        _put_identity(client, admin_token, siteName="Audited Name", contactEmail="hello@example.com")

        with app.app_context():
            entry = AuditLog.query.filter_by(action="settings.update").order_by(AuditLog.id.desc()).first()
            assert entry is not None
            assert entry.changes.get("site_name") == "Audited Name"
            assert "contactEmail" not in str(entry.changes)


class TestSeedIdempotency:
    def test_reseeding_never_overwrites_an_admin_edit(self, client, admin_token, app):
        from app.services.demo_seed import seed_demo_content

        _put_identity(client, admin_token, siteName="Admin Chose This Name")

        with app.app_context():
            seed_demo_content()
            seed_demo_content()

        data = client.get("/api/v1/admin/settings", headers=auth_headers(admin_token)).get_json()["data"]
        assert data["site_identity"]["siteName"] == "Admin Chose This Name"

    def test_seeding_on_an_empty_db_creates_the_real_wsf_identity(self, app):
        from app.models.cms import SiteSetting
        from app.services.demo_seed import seed_demo_content

        with app.app_context():
            seed_demo_content()
            setting = SiteSetting.query.filter_by(key="site_identity").first()
            assert setting is not None
            assert setting.value["site_name"] == "Women Shaping Futures"
            assert setting.value["contact_email"] == "hello@womenshapingfutures.org"
