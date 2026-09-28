from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers


def _register_and_login(client, email, password="supersecret1"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "first_name": "Jane", "last_name": "Doe"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.get_json()["data"]["access_token"]


def _grant_role(app, email, role_name):
    from app.extensions import db
    from app.models.user import Role, User

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        role = Role.query.filter_by(name=role_name).first()
        user.roles.append(role)
        db.session.commit()


def _token_with_role(client, app, role_name, email=None):
    email = email or f"{role_name}@example.com"
    token = _register_and_login(client, email)
    _grant_role(app, email, role_name)
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    return login.get_json()["data"]["access_token"]


def _make_organization(app, **overrides):
    from app.extensions import db
    from app.models.people import Organization

    with app.app_context():
        fields = {
            "slug": overrides.pop("slug", "acme-ventures"),
            "name": overrides.pop("name", "Acme Ventures"),
            "status": overrides.pop("status", "published"),
            "short_description": overrides.pop("short_description", "A fictional test company."),
            "website": overrides.pop("website", None),
            "country_code": overrides.pop("country_code", None),
        }
        fields.update(overrides)
        org = Organization(**fields)
        db.session.add(org)
        db.session.commit()
        return org.id, org.slug


def _make_listing(app, organization_id, **overrides):
    from app.extensions import db
    from app.models.directory import DirectoryListing

    with app.app_context():
        fields = {
            "organization_id": organization_id,
            "status": overrides.pop("status", "published"),
            "listing_type": overrides.pop("listing_type", "business"),
            "ownership_classification": overrides.pop("ownership_classification", "women_owned"),
            "classification_provenance": overrides.pop("classification_provenance", "self_attested"),
            "verification_status": overrides.pop("verification_status", "unverified"),
            "service_summary": overrides.pop("service_summary", "We do fictional things."),
        }
        fields.update(overrides)
        listing = DirectoryListing(**fields)
        if fields["status"] == "published" and listing.published_at is None:
            listing.published_at = datetime.now(timezone.utc)
        db.session.add(listing)
        db.session.commit()
        return listing.id


SUBMISSION_PAYLOAD = {
    "businessName": "Sunrise Fictional Bakery",
    "website": "https://sunrise-fictional-bakery.example.com",
    "listingType": "business",
    "ownershipClassification": "women_owned",
    "countryCode": "KE",
    "location": "Nairobi",
    "description": "A fictional test bakery for automated tests only.",
    "keyServices": ["Custom cakes", "Wholesale bread"],
    "serviceModes": ["local", "online"],
    "submitterName": "Test Submitter",
    "submitterEmail": "submitter@example.com",
    "submitterRole": "Owner",
    "elapsedMs": 5000,
}


# ---------------------------------------------------------------------------
# Public directory
# ---------------------------------------------------------------------------


class TestPublicDirectory:
    def test_only_published_listing_and_organization_are_visible(self, client, app):
        pub_org_id, pub_slug = _make_organization(app, slug="visible-org", name="Visible Org")
        _make_listing(app, pub_org_id, status="published")

        draft_org_id, draft_slug = _make_organization(app, slug="draft-org", name="Draft Org", status="draft")
        _make_listing(app, draft_org_id, status="published")

        pending_org_id, pending_slug = _make_organization(app, slug="pending-org", name="Pending Org")
        _make_listing(app, pending_org_id, status="pending")

        resp = client.get("/api/v1/directory")
        assert resp.status_code == 200
        slugs = [row["organization"]["slug"] for row in resp.get_json()["data"]]
        assert pub_slug in slugs
        assert draft_slug not in slugs
        assert pending_slug not in slugs

    def test_public_detail_404s_for_unpublished(self, client, app):
        org_id, slug = _make_organization(app, slug="hidden-org", name="Hidden Org")
        _make_listing(app, org_id, status="pending")

        resp = client.get(f"/api/v1/directory/{slug}")
        assert resp.status_code == 404

    def test_public_detail_excludes_internal_fields(self, client, app):
        org_id, slug = _make_organization(app, slug="clean-org", name="Clean Org")
        _make_listing(
            app, org_id, status="published", verification_notes="internal only", rejection_reason="internal only"
        )

        resp = client.get(f"/api/v1/directory/{slug}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "verification_notes" not in data
        assert "rejection_reason" not in data
        assert "verified_by" not in data
        assert "reviewed_by" not in data

    def test_country_filter(self, client, app):
        ke_org_id, ke_slug = _make_organization(app, slug="kenya-org", name="Kenya Org", country_code="KE")
        _make_listing(app, ke_org_id, status="published")
        us_org_id, us_slug = _make_organization(app, slug="us-org", name="US Org", country_code="US")
        _make_listing(app, us_org_id, status="published")

        resp = client.get("/api/v1/directory?country=KE")
        slugs = [row["organization"]["slug"] for row in resp.get_json()["data"]]
        assert ke_slug in slugs
        assert us_slug not in slugs

    def test_pagination_meta_present(self, client, app):
        for i in range(3):
            org_id, _ = _make_organization(app, slug=f"paginated-org-{i}", name=f"Paginated Org {i}")
            _make_listing(app, org_id, status="published")

        resp = client.get("/api/v1/directory?per_page=2")
        body = resp.get_json()
        assert body["meta"]["per_page"] == 2
        assert body["meta"]["total"] >= 3

    def test_featured_window_boundary(self, client, app):
        now = datetime.now(timezone.utc)
        org_id, slug = _make_organization(app, slug="featured-org", name="Featured Org")
        listing_id = _make_listing(
            app,
            org_id,
            status="published",
            featured=True,
            featured_start_at=now - timedelta(days=1),
            featured_end_at=now + timedelta(days=1),
        )

        from app.extensions import db
        from app.models.directory import DirectoryListing

        with app.app_context():
            listing = db.session.get(DirectoryListing, listing_id)
            assert listing.is_currently_featured is True

            listing.featured_end_at = now - timedelta(minutes=1)
            db.session.commit()
            assert listing.is_currently_featured is False

            listing.featured_end_at = None
            listing.featured_start_at = now + timedelta(days=1)
            db.session.commit()
            assert listing.is_currently_featured is False


# ---------------------------------------------------------------------------
# Public submission
# ---------------------------------------------------------------------------


class TestPublicSubmission:
    def test_valid_submission_creates_record_with_reference(self, client, app):
        resp = client.post("/api/v1/directory/submit", json=SUBMISSION_PAYLOAD)
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["status"] == "received"
        assert body["reference"].startswith("WSF-DIR-")

        from app.models.directory import DirectorySubmission

        with app.app_context():
            submission = DirectorySubmission.query.filter_by(reference=body["reference"]).first()
            assert submission is not None
            assert submission.status == "new"
            assert submission.submitter_email == "submitter@example.com"

    def test_required_fields_enforced(self, client):
        resp = client.post("/api/v1/directory/submit", json={"businessName": "x"})
        assert resp.status_code == 422

    def test_javascript_scheme_website_rejected(self, client):
        payload = {**SUBMISSION_PAYLOAD, "website": "javascript:alert(1)"}
        resp = client.post("/api/v1/directory/submit", json=payload)
        assert resp.status_code == 422

    def test_honeypot_silently_drops_submission(self, client, app):
        payload = {**SUBMISSION_PAYLOAD, "hpWebsite": "http://spam.example.com", "businessName": "Honeypot Test Co"}
        resp = client.post("/api/v1/directory/submit", json=payload)
        assert resp.status_code == 201  # a believable confirmation...

        from app.models.directory import DirectorySubmission

        with app.app_context():
            # ...but nothing was actually persisted.
            assert DirectorySubmission.query.filter_by(business_name="Honeypot Test Co").first() is None

    def test_too_fast_submission_treated_as_spam(self, client, app):
        payload = {**SUBMISSION_PAYLOAD, "businessName": "Too Fast Co", "elapsedMs": 100}
        client.post("/api/v1/directory/submit", json=payload)

        from app.models.directory import DirectorySubmission

        with app.app_context():
            assert DirectorySubmission.query.filter_by(business_name="Too Fast Co").first() is None

    def test_duplicate_organization_detected_and_never_auto_merged(self, client, app):
        org_id, _ = _make_organization(
            app, slug="sunrise-bakery", name="Sunrise Fictional Bakery",
            website="https://sunrise-fictional-bakery.example.com",
        )
        resp = client.post("/api/v1/directory/submit", json=SUBMISSION_PAYLOAD)
        reference = resp.get_json()["data"]["reference"]

        from app.models.directory import DirectorySubmission

        with app.app_context():
            submission = DirectorySubmission.query.filter_by(reference=reference).first()
            assert submission.possible_duplicate_organization_id == org_id
            # Never auto-merged — the submission stays "new" until staff act.
            assert submission.status == "new"
            assert submission.matched_organization_id is None

    def test_public_confirmation_excludes_internal_fields(self, client):
        resp = client.post("/api/v1/directory/submit", json=SUBMISSION_PAYLOAD)
        body = resp.get_json()["data"]
        assert set(body.keys()) == {"reference", "status"}


# ---------------------------------------------------------------------------
# Admin workflow
# ---------------------------------------------------------------------------


class TestAdminListings:
    def test_create_requires_permission(self, client, app):
        org_id, _ = _make_organization(app, slug="unauth-org", name="Unauth Org")
        token = _token_with_role(client, app, "author", email="author@example.com")
        resp = client.post(
            "/api/v1/directory/admin/listings", json={"organizationId": org_id}, headers=auth_headers(token)
        )
        assert resp.status_code == 403

    def test_unauthenticated_forbidden(self, client, app):
        org_id, _ = _make_organization(app, slug="anon-org", name="Anon Org")
        resp = client.post("/api/v1/directory/admin/listings", json={"organizationId": org_id})
        assert resp.status_code in (401, 403)

    def test_admin_can_create_listing_and_link_organization(self, client, app):
        org_id, _ = _make_organization(app, slug="linked-org", name="Linked Org")
        token = _token_with_role(client, app, "admin")

        resp = client.post(
            "/api/v1/directory/admin/listings", json={"organizationId": org_id}, headers=auth_headers(token)
        )
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["status"] == "pending"
        assert body["organization"]["id"] == org_id

        from app.models.audit import AuditLog

        with app.app_context():
            entry = AuditLog.query.filter_by(action="directory.organization_linked").first()
            assert entry is not None

    def test_cannot_double_list_same_organization(self, client, app):
        org_id, _ = _make_organization(app, slug="double-org", name="Double Org")
        token = _token_with_role(client, app, "editor")

        first = client.post(
            "/api/v1/directory/admin/listings", json={"organizationId": org_id}, headers=auth_headers(token)
        )
        assert first.status_code == 201
        second = client.post(
            "/api/v1/directory/admin/listings", json={"organizationId": org_id}, headers=auth_headers(token)
        )
        assert second.status_code == 409

    def test_status_transition_validation(self, client, app):
        org_id, _ = _make_organization(app, slug="transition-org", name="Transition Org")
        listing_id = _make_listing(app, org_id, status="pending")
        token = _token_with_role(client, app, "admin")

        # pending -> published is not a direct transition.
        bad = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/status",
            json={"status": "published"},
            headers=auth_headers(token),
        )
        assert bad.status_code == 409

        ok = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/status",
            json={"status": "under_review"},
            headers=auth_headers(token),
        )
        assert ok.status_code == 200
        assert ok.get_json()["data"]["status"] == "under_review"

    def test_rejection_requires_reason(self, client, app):
        org_id, _ = _make_organization(app, slug="reject-org", name="Reject Org")
        listing_id = _make_listing(app, org_id, status="pending")
        token = _token_with_role(client, app, "admin")

        resp = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/status",
            json={"status": "rejected"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

        resp2 = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/status",
            json={"status": "rejected", "rejectionReason": "Not enough information provided."},
            headers=auth_headers(token),
        )
        assert resp2.status_code == 200
        assert resp2.get_json()["data"]["status"] == "rejected"

    def test_delete_listing_never_deletes_organization(self, client, app):
        org_id, org_slug = _make_organization(app, slug="keep-org", name="Keep Org")
        listing_id = _make_listing(app, org_id, status="pending")
        token = _token_with_role(client, app, "admin")

        resp = client.delete(f"/api/v1/directory/admin/listings/{listing_id}", headers=auth_headers(token))
        assert resp.status_code == 200

        from app.models.people import Organization

        with app.app_context():
            assert Organization.query.filter_by(slug=org_slug).first() is not None

    def test_organization_delete_blocked_when_listed(self, client, app):
        org_id, org_slug = _make_organization(app, slug="referenced-org", name="Referenced Org")
        _make_listing(app, org_id, status="pending")
        token = _token_with_role(client, app, "admin")

        resp = client.delete(f"/api/v1/organizations/{org_slug}", headers=auth_headers(token))
        assert resp.status_code == 409


class TestVerificationAndFeaturedIndependence:
    """Dedicated regression coverage per spec: self-attested classification
    must never silently become "verified", and featured/verified are fully
    independent state changes in both directions."""

    def test_self_attested_classification_never_auto_verifies(self, client, app):
        org_id, _ = _make_organization(app, slug="self-attest-org", name="Self Attest Org")
        listing_id = _make_listing(
            app, org_id, status="pending", ownership_classification="women_owned",
            classification_provenance="self_attested", verification_status="unverified",
        )
        token = _token_with_role(client, app, "admin")

        # Publishing the listing (an editorial/publication action) must not
        # touch verification_status at all.
        client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/status",
            json={"status": "under_review"}, headers=auth_headers(token),
        )
        resp = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/status",
            json={"status": "approved"}, headers=auth_headers(token),
        )
        assert resp.status_code == 200
        published = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/status",
            json={"status": "published"}, headers=auth_headers(token),
        )
        assert published.status_code == 200
        body = published.get_json()["data"]
        assert body["verification_status"] == "unverified"
        assert body["classification_provenance"] == "self_attested"

    def test_featured_and_verified_are_independent(self, client, app):
        org_id, _ = _make_organization(app, slug="independence-org", name="Independence Org")
        listing_id = _make_listing(app, org_id, status="published", verification_status="unverified", featured=False)
        token = _token_with_role(client, app, "admin")

        # Featuring a listing must not change verification.
        feature_resp = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/featured",
            json={"featured": True}, headers=auth_headers(token),
        )
        assert feature_resp.status_code == 200
        assert feature_resp.get_json()["data"]["verification_status"] == "unverified"
        assert feature_resp.get_json()["data"]["featured"] is True

        # Verifying a listing must not change its featured state.
        verify_resp = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/verification",
            json={"verificationStatus": "verified"}, headers=auth_headers(token),
        )
        assert verify_resp.status_code == 200
        assert verify_resp.get_json()["data"]["featured"] is True
        assert verify_resp.get_json()["data"]["verification_status"] == "verified"

        # Un-verifying must not un-feature it either.
        unverify_resp = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/verification",
            json={"verificationStatus": "unverified"}, headers=auth_headers(token),
        )
        assert unverify_resp.status_code == 200
        assert unverify_resp.get_json()["data"]["featured"] is True

        # Un-featuring must not affect verification.
        unfeature_resp = client.patch(
            f"/api/v1/directory/admin/listings/{listing_id}/featured",
            json={"featured": False}, headers=auth_headers(token),
        )
        assert unfeature_resp.status_code == 200
        assert unfeature_resp.get_json()["data"]["verification_status"] == "unverified"


class TestAdminSubmissionWorkflow:
    def test_convert_creates_new_organization_and_pending_listing(self, client, app):
        client.post("/api/v1/directory/submit", json=SUBMISSION_PAYLOAD)
        token = _token_with_role(client, app, "admin")

        from app.models.directory import DirectorySubmission

        with app.app_context():
            submission_id = DirectorySubmission.query.filter_by(submitter_email="submitter@example.com").first().id

        resp = client.post(f"/api/v1/directory/admin/submissions/{submission_id}/convert", json={}, headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["submission"]["status"] == "converted"
        assert body["listing"]["status"] == "pending"  # never auto-published

        from app.models.people import Organization

        with app.app_context():
            org = db_get_org_by_id(app, body["listing"]["organization"]["id"])
            assert org.status == "draft"  # requires a separate publish decision

    def test_convert_can_link_to_existing_organization(self, client, app):
        org_id, _ = _make_organization(app, slug="existing-link-org", name="Existing Link Org")
        client.post("/api/v1/directory/submit", json={**SUBMISSION_PAYLOAD, "businessName": "Existing Link Test"})
        token = _token_with_role(client, app, "admin")

        from app.models.directory import DirectorySubmission

        with app.app_context():
            submission_id = DirectorySubmission.query.filter_by(business_name="Existing Link Test").first().id

        resp = client.post(
            f"/api/v1/directory/admin/submissions/{submission_id}/convert",
            json={"organizationId": org_id},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["listing"]["organization"]["id"] == org_id

    def test_submission_detail_includes_private_submitter_fields_for_staff_only(self, client, app):
        client.post("/api/v1/directory/submit", json=SUBMISSION_PAYLOAD)
        token = _token_with_role(client, app, "admin")

        from app.models.directory import DirectorySubmission

        with app.app_context():
            submission_id = DirectorySubmission.query.filter_by(submitter_email="submitter@example.com").first().id

        resp = client.get(f"/api/v1/directory/admin/submissions/{submission_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["submitter_email"] == "submitter@example.com"

    def test_submission_notes_are_staff_only(self, client, app):
        client.post("/api/v1/directory/submit", json=SUBMISSION_PAYLOAD)
        token = _token_with_role(client, app, "admin")

        from app.models.directory import DirectorySubmission

        with app.app_context():
            submission_id = DirectorySubmission.query.filter_by(submitter_email="submitter@example.com").first().id

        resp = client.post(
            f"/api/v1/directory/admin/submissions/{submission_id}/notes",
            json={"body": "Looks legitimate, verifying website."},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["notes"][0]["body"] == "Looks legitimate, verifying website."


def db_get_org_by_id(app, org_id):
    from app.extensions import db
    from app.models.people import Organization

    with app.app_context():
        return db.session.get(Organization, org_id)


class TestRBAC:
    @pytest.mark.parametrize("role_name", ["admin", "editor", "partnerships_manager", "directory_manager"])
    def test_authorized_roles_can_manage(self, client, app, role_name):
        org_id, _ = _make_organization(app, slug=f"rbac-org-{role_name}", name=f"RBAC Org {role_name}")
        token = _token_with_role(client, app, role_name, email=f"{role_name}-rbac@example.com")
        resp = client.post(
            "/api/v1/directory/admin/listings", json={"organizationId": org_id}, headers=auth_headers(token)
        )
        assert resp.status_code == 201

    def test_moderator_is_not_authorized(self, client, app):
        org_id, _ = _make_organization(app, slug="mod-org", name="Mod Org")
        token = _token_with_role(client, app, "moderator")
        resp = client.post(
            "/api/v1/directory/admin/listings", json={"organizationId": org_id}, headers=auth_headers(token)
        )
        assert resp.status_code == 403

    def test_category_admin_gated_by_taxonomy_manage(self, client, app):
        token = _token_with_role(client, app, "taxonomy_manager")
        resp = client.post(
            "/api/v1/directory/admin/categories", json={"name": "Consulting"}, headers=auth_headers(token)
        )
        assert resp.status_code == 201

        directory_only_token = _token_with_role(client, app, "directory_manager", email="dir-only@example.com")
        forbidden = client.post(
            "/api/v1/directory/admin/categories", json={"name": "Retail"}, headers=auth_headers(directory_only_token)
        )
        assert forbidden.status_code == 403


class TestDirectoryCategories:
    def test_category_crud_and_slug_generation(self, client, app):
        token = _token_with_role(client, app, "admin")
        create = client.post(
            "/api/v1/directory/admin/categories", json={"name": "Consulting & Advisory"}, headers=auth_headers(token)
        )
        assert create.status_code == 201
        category = create.get_json()["data"]
        assert category["slug"] == "consulting-advisory"

        public = client.get("/api/v1/directory/categories")
        assert public.status_code == 200
        assert any(c["slug"] == "consulting-advisory" for c in public.get_json()["data"])

    def test_category_delete_blocked_when_in_use(self, client, app):
        token = _token_with_role(client, app, "admin")
        create = client.post(
            "/api/v1/directory/admin/categories", json={"name": "Legal Services"}, headers=auth_headers(token)
        )
        category_id = create.get_json()["data"]["id"]

        org_id, _ = _make_organization(app, slug="category-user-org", name="Category User Org")
        listing_id = _make_listing(app, org_id, status="pending")

        from app.extensions import db
        from app.models.directory import DirectoryCategory, DirectoryListing

        with app.app_context():
            listing = db.session.get(DirectoryListing, listing_id)
            listing.categories = [db.session.get(DirectoryCategory, category_id)]
            db.session.commit()

        resp = client.delete(f"/api/v1/directory/admin/categories/{category_id}", headers=auth_headers(token))
        assert resp.status_code == 409
