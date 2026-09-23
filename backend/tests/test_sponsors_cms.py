import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "sponsors-manager@example.com",
    "password": "supersecret1",
    "first_name": "Diana",
    "last_name": "Kioko",
    "country_code": "KE",
}

NO_PERMISSION_PAYLOAD = {
    "email": "sponsors-nobody@example.com",
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


def _make_organization(app, slug="brand-co", name="Brand Co"):
    from app.extensions import db
    from app.models.people import Organization

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if org is None:
            org = Organization(slug=slug, name=name, country_code="US")
            db.session.add(org)
            db.session.commit()
        return org.slug


def _base_payload(**overrides):
    payload = {
        "campaignName": "Q1 Brand Sponsorship",
        "organizationSlug": "brand-co",
        "sponsorshipType": "Brand Sponsor",
    }
    payload.update(overrides)
    return payload


def _create_sponsor(client, token, app, **overrides):
    _make_organization(app)
    resp = client.post("/api/v1/sponsors/", json=_base_payload(**overrides), headers=auth_headers(token))
    return resp


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------

def test_create_sponsor(client, manager_token, app):
    resp = _create_sponsor(client, manager_token, app)
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["campaign_name"] == "Q1 Brand Sponsorship"
    assert data["status"] == "draft"
    assert data["public_visible"] is False
    assert data["organization"]["slug"] == "brand-co"


def test_create_requires_organization(client, manager_token, app):
    resp = client.post(
        "/api/v1/sponsors/", json={"campaignName": "No org"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_create_unknown_organization_404s(client, manager_token, app):
    resp = client.post(
        "/api/v1/sponsors/",
        json={"campaignName": "X", "organizationSlug": "does-not-exist"},
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 404


def test_update_sponsor_partial_save_preserves_untouched_fields(client, manager_token, app):
    created = _create_sponsor(client, manager_token, app, publicVisible=True, disclosureLabel="Presented by")
    sid = created.get_json()["data"]["id"]

    updated = client.patch(
        f"/api/v1/sponsors/{sid}", json={"publicDescription": "Updated copy"}, headers=auth_headers(manager_token)
    )
    assert updated.status_code == 200
    data = updated.get_json()["data"]
    assert data["public_description"] == "Updated copy"
    # A partial save must not silently reset these back to their create-time defaults.
    assert data["public_visible"] is True
    assert data["disclosure_label"] == "Presented by"


def test_sponsorship_type_validation(client, manager_token, app):
    resp = client.post(
        "/api/v1/sponsors/",
        json={"campaignName": "X", "organizationSlug": _make_organization(app), "sponsorshipType": "Not A Real Type"},
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_end_date_before_start_date_rejected(client, manager_token, app):
    resp = client.post(
        "/api/v1/sponsors/",
        json=_base_payload(startsAt="2026-06-01", endsAt="2026-01-01"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_negative_commercial_value_rejected(client, manager_token, app):
    resp = client.post(
        "/api/v1/sponsors/", json=_base_payload(estimatedValue=-10), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_sponsor_url_validation(client, manager_token, app):
    resp = client.post(
        "/api/v1/sponsors/", json=_base_payload(sponsorUrl="javascript:alert(1)"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Organization / Partnership relationship
# ---------------------------------------------------------------------------

def test_optional_partnership_link(client, manager_token, app):
    from app.extensions import db
    from app.models.commerce import PartnershipInquiry

    with app.app_context():
        inquiry = PartnershipInquiry(
            contact_name="Jane", email="jane@brandco.com", company="Brand Co", consent_given=True
        )
        db.session.add(inquiry)
        db.session.commit()
        partnership_id = inquiry.id

    resp = _create_sponsor(client, manager_token, app, partnershipId=partnership_id)
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["partnership"]["id"] == partnership_id
    assert data["partnership"]["company"] == "Brand Co"


def test_sponsor_without_partnership_is_fine(client, manager_token, app):
    resp = _create_sponsor(client, manager_token, app)
    assert resp.status_code == 201
    assert resp.get_json()["data"]["partnership"] is None


# ---------------------------------------------------------------------------
# Status transitions / archive / safe delete
# ---------------------------------------------------------------------------

def test_status_transition_lifecycle(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]

    for status in ("scheduled", "active", "paused", "active", "completed", "archived"):
        resp = client.patch(
            f"/api/v1/sponsors/{sid}/status", json={"status": status}, headers=auth_headers(manager_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == status


def test_invalid_status_rejected(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    resp = client.patch(
        f"/api/v1/sponsors/{sid}/status", json={"status": "cancelled"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_archive_preserves_record(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    client.patch(f"/api/v1/sponsors/{sid}/status", json={"status": "archived"}, headers=auth_headers(manager_token))
    fetched = client.get(f"/api/v1/sponsors/{sid}", headers=auth_headers(manager_token))
    assert fetched.status_code == 200
    assert fetched.get_json()["data"]["status"] == "archived"
    assert fetched.get_json()["data"]["organization"]["slug"] == "brand-co"


def test_delete_blocked_for_non_draft(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    client.patch(f"/api/v1/sponsors/{sid}/status", json={"status": "active"}, headers=auth_headers(manager_token))
    resp = client.delete(f"/api/v1/sponsors/{sid}", headers=auth_headers(manager_token))
    assert resp.status_code == 409


def test_delete_allowed_for_unreferenced_draft(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    resp = client.delete(f"/api/v1/sponsors/{sid}", headers=auth_headers(manager_token))
    assert resp.status_code == 204
    assert client.get(f"/api/v1/sponsors/{sid}", headers=auth_headers(manager_token)).status_code == 404


def test_delete_blocked_when_referenced_by_job(client, manager_token, app):
    from app.extensions import db
    from app.models.opportunity import Job

    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    with app.app_context():
        from app.models.people import Organization

        org = Organization.query.filter_by(slug="brand-co").first()
        job = Job(
            slug="sponsored-role", title="Sponsored Role", organization_id=org.id, company_name=org.name,
            sponsor_id=sid, sponsored=True,
        )
        db.session.add(job)
        db.session.commit()

    resp = client.delete(f"/api/v1/sponsors/{sid}", headers=auth_headers(manager_token))
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Placements
# ---------------------------------------------------------------------------

def test_placement_creation_and_invalid_key(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    ok = client.post(
        f"/api/v1/sponsors/{sid}/placements", json={"placementKey": "homepage_featured"}, headers=auth_headers(manager_token)
    )
    assert ok.status_code == 201
    assert len(ok.get_json()["data"]["placements"]) == 1

    bad = client.post(
        f"/api/v1/sponsors/{sid}/placements", json={"placementKey": "sidebar_ad_slot_3"}, headers=auth_headers(manager_token)
    )
    assert bad.status_code == 422


def test_placement_ordering(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    client.post(
        f"/api/v1/sponsors/{sid}/placements", json={"placementKey": "article_sidebar", "position": 5},
        headers=auth_headers(manager_token),
    )
    resp = client.post(
        f"/api/v1/sponsors/{sid}/placements", json={"placementKey": "homepage_featured", "position": 1},
        headers=auth_headers(manager_token),
    )
    placements = resp.get_json()["data"]["placements"]
    assert [p["placement_key"] for p in placements] == ["homepage_featured", "article_sidebar"]


def test_placement_removal(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    added = client.post(
        f"/api/v1/sponsors/{sid}/placements", json={"placementKey": "homepage_footer"}, headers=auth_headers(manager_token)
    )
    pid = added.get_json()["data"]["placements"][0]["id"]
    removed = client.delete(f"/api/v1/sponsors/{sid}/placements/{pid}", headers=auth_headers(manager_token))
    assert removed.status_code == 200
    assert removed.get_json()["data"]["placements"] == []


# ---------------------------------------------------------------------------
# Public eligibility / expiry / disclosure / privacy
# ---------------------------------------------------------------------------

def _activate_and_place(client, token, sid, placement="homepage_featured", **update_fields):
    fields = {"publicVisible": True}
    fields.update(update_fields)
    client.patch(f"/api/v1/sponsors/{sid}", json=fields, headers=auth_headers(token))
    client.patch(f"/api/v1/sponsors/{sid}/status", json={"status": "active"}, headers=auth_headers(token))
    client.post(f"/api/v1/sponsors/{sid}/placements", json={"placementKey": placement}, headers=auth_headers(token))


def test_public_placement_requires_visibility_and_active_status(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    client.post(f"/api/v1/sponsors/{sid}/placements", json={"placementKey": "homepage_featured"}, headers=auth_headers(manager_token))

    # Draft, not public — should not appear.
    empty = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    assert empty.get_json()["data"] == []

    _activate_and_place(client, manager_token, sid)
    visible = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    ids = [row["id"] for row in visible.get_json()["data"]]
    assert sid in ids


def test_public_placement_requires_placement_param(client):
    resp = client.get("/api/v1/sponsors/public")
    assert resp.status_code == 422
    resp2 = client.get("/api/v1/sponsors/public?placement=not_a_real_key")
    assert resp2.status_code == 422


def test_expired_campaign_excluded_from_public_placement(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app, endsAt="2020-01-01").get_json()["data"]["id"]
    _activate_and_place(client, manager_token, sid)
    resp = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    assert sid not in [row["id"] for row in resp.get_json()["data"]]

    # But the record itself is preserved in the CMS.
    fetched = client.get(f"/api/v1/sponsors/{sid}", headers=auth_headers(manager_token))
    assert fetched.status_code == 200


def test_future_start_date_excluded_until_reached(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app, startsAt="2099-01-01").get_json()["data"]["id"]
    _activate_and_place(client, manager_token, sid)
    resp = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    assert sid not in [row["id"] for row in resp.get_json()["data"]]


def test_disclosure_label_present_and_controlled(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app, disclosureLabel="In partnership with").get_json()["data"]["id"]
    _activate_and_place(client, manager_token, sid, disclosureLabel="In partnership with")
    resp = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    row = next(r for r in resp.get_json()["data"] if r["id"] == sid)
    assert row["disclosureLabel"] == "In partnership with"


def test_public_payload_excludes_commercial_and_internal_fields(client, manager_token, app):
    sid = _create_sponsor(
        client, manager_token, app, estimatedValue=50000, currency="USD", commercialNotes="Negotiated 15% discount",
        internalNotes="Contact prefers email", tier="Gold",
    ).get_json()["data"]["id"]
    _activate_and_place(client, manager_token, sid)
    resp = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    row = next(r for r in resp.get_json()["data"] if r["id"] == sid)
    dumped_text = str(row)
    assert "50000" not in dumped_text
    assert "Negotiated 15% discount" not in dumped_text
    assert "Contact prefers email" not in dumped_text
    assert "estimatedValue" not in row and "commercialNotes" not in row and "internalNotes" not in row and "tier" not in row


def test_public_endpoint_is_unauthenticated(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    _activate_and_place(client, manager_token, sid)
    resp = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Media / logo fallback
# ---------------------------------------------------------------------------

def test_logo_falls_back_to_organization_logo(client, manager_token, app):
    from app.extensions import db
    from app.models.media import Media
    from app.models.people import Organization

    with app.app_context():
        media = Media(
            original_filename="logo.jpg", stored_filename="logo-abc.jpg",
            file_path="orgs/brand-co-logo.jpg", public_url="/media/orgs/brand-co-logo.jpg", mime_type="image/jpeg",
        )
        db.session.add(media)
        db.session.commit()
        org = Organization.query.filter_by(slug="brand-co").first()
        if org is None:
            org = Organization(slug="brand-co", name="Brand Co", country_code="US")
            db.session.add(org)
        org.logo_media_id = media.id
        db.session.commit()

    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    _activate_and_place(client, manager_token, sid)
    resp = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    row = next(r for r in resp.get_json()["data"] if r["id"] == sid)
    assert row["logo"] is not None


def test_no_logo_omits_rather_than_fakes(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app, organizationSlug=_make_organization(app, "no-logo-org", "No Logo Org")).get_json()["data"]["id"]
    _activate_and_place(client, manager_token, sid)
    resp = client.get("/api/v1/sponsors/public?placement=homepage_featured")
    row = next(r for r in resp.get_json()["data"] if r["id"] == sid)
    assert row["logo"] is None


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

def test_no_permission_user_denied(client, no_permission_token, app):
    resp = client.get("/api/v1/sponsors/", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_unauthenticated_admin_list_denied(client):
    assert client.get("/api/v1/sponsors/").status_code == 401


def test_manager_can_manage(client, manager_token, app):
    resp = _create_sponsor(client, manager_token, app)
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# History / analytics
# ---------------------------------------------------------------------------

def test_history_records_lifecycle_actions(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]
    client.patch(f"/api/v1/sponsors/{sid}/status", json={"status": "active"}, headers=auth_headers(manager_token))
    resp = client.get(f"/api/v1/sponsors/{sid}/history", headers=auth_headers(manager_token))
    actions = [e["action"] for e in resp.get_json()["data"]]
    assert "sponsor.create" in actions
    assert "sponsor.status_change" in actions


def test_analytics_counts_real_events_and_omits_ctr_without_impressions(client, manager_token, app):
    sid = _create_sponsor(client, manager_token, app).get_json()["data"]["id"]

    before = client.get(f"/api/v1/sponsors/{sid}/analytics", headers=auth_headers(manager_token)).get_json()["data"]
    assert before == {"impressions": 0, "clicks": 0, "clickThroughRate": None}

    client.post("/api/v1/analytics/events", json={"eventName": "sponsor_impression", "entityType": "Sponsor", "entityId": str(sid)})
    client.post("/api/v1/analytics/events", json={"eventName": "sponsor_impression", "entityType": "Sponsor", "entityId": str(sid)})
    client.post("/api/v1/analytics/events", json={"eventName": "sponsor_click", "entityType": "Sponsor", "entityId": str(sid)})

    after = client.get(f"/api/v1/sponsors/{sid}/analytics", headers=auth_headers(manager_token)).get_json()["data"]
    assert after == {"impressions": 2, "clicks": 1, "clickThroughRate": 50.0}


# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------

def test_search_and_filter(client, manager_token, app):
    _create_sponsor(client, manager_token, app, campaignName="Summer Newsletter Push", sponsorshipType="Newsletter Sponsor")
    _create_sponsor(client, manager_token, app, campaignName="Winter Event Push", sponsorshipType="Event Sponsor")

    by_search = client.get("/api/v1/sponsors/?q=Summer", headers=auth_headers(manager_token))
    names = [r["campaign_name"] for r in by_search.get_json()["data"]]
    assert names == ["Summer Newsletter Push"]

    by_type = client.get(
        "/api/v1/sponsors/", query_string={"sponsorship_type": "Event Sponsor"}, headers=auth_headers(manager_token)
    )
    names = [r["campaign_name"] for r in by_type.get_json()["data"]]
    assert names == ["Winter Event Push"]
