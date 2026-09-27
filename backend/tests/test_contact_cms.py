from app.extensions import db
from app.models.audit import AuditLog
from app.models.contact import ContactInquiry
from app.models.user import Permission, Role, User
from app.services.rbac import seed_roles_and_permissions
from tests.conftest import auth_headers

VALID_PAYLOAD = {
    "firstName": "Amara",
    "lastName": "Otieno",
    "email": "amara@example.com",
    "inquiryType": "general",
    "subject": "Question about the newsletter",
    "message": "Hello, I would like to know how often the newsletter is sent out. Thank you!",
    "privacyAcknowledged": True,
    "elapsedMs": 5000,
}


def _register_and_login(client, email="jane@example.com", password="supersecret1"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "first_name": "Jane", "last_name": "Doe"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.get_json()["data"]["access_token"]


def _grant_role(app, email, role_name):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        role = Role.query.filter_by(name=role_name).first()
        user.roles.append(role)
        db.session.commit()


def _super_admin_headers(client, app, email="admin@example.com"):
    token = _register_and_login(client, email=email)
    _grant_role(app, email, "super_admin")
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    return auth_headers(login.get_json()["data"]["access_token"])


def _submit(client, **overrides):
    payload = {**VALID_PAYLOAD, **overrides}
    return client.post("/api/v1/contact", json=payload)


class TestPublicSubmission:
    def test_valid_inquiry_creates_record_with_reference(self, client, app):
        resp = _submit(client, email="unique1@example.com")
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["status"] == "received"
        assert body["reference"].startswith("WSF-CON-")

        with app.app_context():
            inquiry = ContactInquiry.query.filter_by(email="unique1@example.com").first()
            assert inquiry is not None
            assert inquiry.reference == body["reference"]
            assert inquiry.status == "new"

    def test_required_fields_enforced(self, client):
        resp = client.post("/api/v1/contact", json={"email": "x@example.com"})
        assert resp.status_code == 422

    def test_invalid_email_rejected(self, client):
        resp = _submit(client, email="not-an-email")
        assert resp.status_code == 422

    def test_email_normalized_to_lowercase(self, client, app):
        resp = _submit(client, email="MixedCase@Example.com")
        assert resp.status_code == 201
        with app.app_context():
            inquiry = ContactInquiry.query.filter_by(email="mixedcase@example.com").first()
            assert inquiry is not None

    def test_message_too_short_rejected(self, client):
        resp = _submit(client, email="short@example.com", message="hi")
        assert resp.status_code == 422

    def test_message_too_long_rejected(self, client):
        resp = _submit(client, email="long@example.com", message="x" * 6000)
        assert resp.status_code == 422

    def test_invalid_inquiry_type_rejected(self, client):
        resp = _submit(client, email="badtype@example.com", inquiryType="partnership")
        assert resp.status_code == 422

    def test_specialized_categories_not_offered(self, client):
        for excluded in ("partnership", "sponsorship", "advertising"):
            resp = _submit(client, email=f"{excluded}@example.com", inquiryType=excluded)
            assert resp.status_code == 422

    def test_privacy_acknowledgement_required(self, client):
        resp = _submit(client, email="noconsent@example.com", privacyAcknowledged=False)
        assert resp.status_code == 422

    def test_html_content_stored_as_plain_text(self, client, app):
        malicious = "<script>alert('xss')</script> Please help with my account"
        resp = _submit(client, email="xsstest@example.com", message=malicious)
        assert resp.status_code == 201
        with app.app_context():
            inquiry = ContactInquiry.query.filter_by(email="xsstest@example.com").first()
            assert inquiry.message == malicious  # stored verbatim as plain text, not executed/stripped

    def test_oversized_payload_rejected(self, client):
        resp = client.post(
            "/api/v1/contact",
            json={**VALID_PAYLOAD, "email": "huge@example.com", "subject": "x" * 5000},
        )
        assert resp.status_code == 422

    def test_no_authentication_required(self, client):
        resp = _submit(client, email="noauth@example.com")
        assert resp.status_code == 201

    def test_public_response_excludes_internal_fields(self, client):
        resp = _submit(client, email="safeconfirm@example.com")
        raw = resp.get_data(as_text=True)
        assert "assigned" not in raw.lower()
        assert "internal" not in raw.lower()
        assert "note" not in raw.lower()
        body = resp.get_json()["data"]
        assert set(body.keys()) == {"reference", "status"}

    def test_honeypot_filled_drops_silently(self, client, app):
        resp = client.post(
            "/api/v1/contact",
            json={**VALID_PAYLOAD, "email": "bot1@example.com", "hpWebsite": "http://spam.example"},
        )
        assert resp.status_code == 201
        with app.app_context():
            assert ContactInquiry.query.filter_by(email="bot1@example.com").first() is None

    def test_too_fast_submission_drops_silently(self, client, app):
        resp = client.post(
            "/api/v1/contact",
            json={**VALID_PAYLOAD, "email": "bot2@example.com", "elapsedMs": 50},
        )
        assert resp.status_code == 201
        with app.app_context():
            assert ContactInquiry.query.filter_by(email="bot2@example.com").first() is None

    def test_duplicate_rapid_click_does_not_create_second_record(self, client, app):
        first = _submit(client, email="dup@example.com")
        second = _submit(client, email="dup@example.com")
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.get_json()["data"]["reference"] == second.get_json()["data"]["reference"]
        with app.app_context():
            assert ContactInquiry.query.filter_by(email="dup@example.com").count() == 1


class TestAdminAccessControl:
    def test_list_requires_authentication(self, client):
        resp = client.get("/api/v1/contact")
        assert resp.status_code == 401

    def test_list_requires_permission(self, client, app):
        token = _register_and_login(client)
        resp = client.get("/api/v1/contact", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_super_admin_can_list(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = client.get("/api/v1/contact", headers=headers)
        assert resp.status_code == 200

    def test_admin_role_can_list(self, client, app):
        token = _register_and_login(client, email="plainadmin@example.com")
        _grant_role(app, "plainadmin@example.com", "admin")
        login = client.post("/api/v1/auth/login", json={"email": "plainadmin@example.com", "password": "supersecret1"})
        headers = auth_headers(login.get_json()["data"]["access_token"])
        resp = client.get("/api/v1/contact", headers=headers)
        assert resp.status_code == 200

    def test_moderator_role_can_list(self, client, app):
        token = _register_and_login(client, email="mod@example.com")
        _grant_role(app, "mod@example.com", "moderator")
        login = client.post("/api/v1/auth/login", json={"email": "mod@example.com", "password": "supersecret1"})
        headers = auth_headers(login.get_json()["data"]["access_token"])
        resp = client.get("/api/v1/contact", headers=headers)
        assert resp.status_code == 200

    def test_editor_role_cannot_list(self, client, app):
        token = _register_and_login(client, email="editor1@example.com")
        _grant_role(app, "editor1@example.com", "editor")
        login = client.post("/api/v1/auth/login", json={"email": "editor1@example.com", "password": "supersecret1"})
        headers = auth_headers(login.get_json()["data"]["access_token"])
        resp = client.get("/api/v1/contact", headers=headers)
        assert resp.status_code == 403


class TestAdminListing:
    def test_pagination_and_ordering(self, client, app):
        headers = _super_admin_headers(client, app)
        for i in range(3):
            _submit(client, email=f"order{i}@example.com", subject=f"Subject {i}")

        resp = client.get("/api/v1/contact?per_page=2", headers=headers)
        body = resp.get_json()
        assert len(body["data"]) == 2
        assert body["meta"]["total"] >= 3
        timestamps = [row["created_at"] for row in client.get("/api/v1/contact?per_page=50", headers=headers).get_json()["data"]]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_filter_by_status(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="statusfilter@example.com")
        resp = client.get("/api/v1/contact?status=new", headers=headers)
        rows = resp.get_json()["data"]
        assert any(r["email"] == "statusfilter@example.com" for r in rows)
        assert all(r["status"] == "new" for r in rows)

    def test_filter_by_inquiry_type(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="techtype@example.com", inquiryType="technical")
        resp = client.get("/api/v1/contact?inquiry_type=technical", headers=headers)
        rows = resp.get_json()["data"]
        assert any(r["email"] == "techtype@example.com" for r in rows)
        assert all(r["inquiry_type"] == "technical" for r in rows)

    def test_search_by_reference_email_name_subject(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _submit(client, email="searchable@example.com", subject="Very Unique Subject Line")
        reference = create.get_json()["data"]["reference"]

        for term in [reference, "searchable@example.com", "Amara", "Very Unique Subject Line"]:
            resp = client.get(f"/api/v1/contact?q={term}", headers=headers)
            rows = resp.get_json()["data"]
            assert len(rows) >= 1, f"search term {term!r} found nothing"

    def test_list_row_excludes_message_and_notes(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="rowcheck@example.com", message="This body should not appear in the list row.")
        resp = client.get("/api/v1/contact?q=rowcheck", headers=headers)
        raw = resp.get_data(as_text=True)
        assert "This body should not appear" not in raw


class TestAdminDetail:
    def test_detail_retrieval(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _submit(client, email="detailcheck@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="detailcheck@example.com").first().id

        resp = client.get(f"/api/v1/contact/{inquiry_id}", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["email"] == "detailcheck@example.com"
        assert body["notes"] == []

    def test_missing_inquiry_404(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = client.get("/api/v1/contact/999999", headers=headers)
        assert resp.status_code == 404


class TestStatusWorkflow:
    def _create(self, client, email):
        _submit(client, email=email)

    def _get_id(self, app, email):
        with app.app_context():
            return ContactInquiry.query.filter_by(email=email).first().id

    def test_new_to_in_progress(self, client, app):
        headers = _super_admin_headers(client, app)
        self._create(client, "flow1@example.com")
        inquiry_id = self._get_id(app, "flow1@example.com")
        resp = client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "in_progress"}, headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "in_progress"

    def test_new_to_spam(self, client, app):
        headers = _super_admin_headers(client, app)
        self._create(client, "flow2@example.com")
        inquiry_id = self._get_id(app, "flow2@example.com")
        resp = client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "spam"}, headers=headers)
        assert resp.status_code == 200

    def test_invalid_transition_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        self._create(client, "flow3@example.com")
        inquiry_id = self._get_id(app, "flow3@example.com")
        resp = client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "resolved"}, headers=headers)
        assert resp.status_code == 409

    def test_full_lifecycle_to_resolved_records_resolution(self, client, app):
        headers = _super_admin_headers(client, app, email="resolver@example.com")
        self._create(client, "flow4@example.com")
        inquiry_id = self._get_id(app, "flow4@example.com")
        client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "in_progress"}, headers=headers)
        resp = client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "resolved"}, headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["resolved_at"] is not None
        assert body["resolved_by"]["email"] == "resolver@example.com"

    def test_resolved_to_closed(self, client, app):
        headers = _super_admin_headers(client, app)
        self._create(client, "flow5@example.com")
        inquiry_id = self._get_id(app, "flow5@example.com")
        client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "in_progress"}, headers=headers)
        client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "resolved"}, headers=headers)
        resp = client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "closed"}, headers=headers)
        assert resp.status_code == 200

    def test_invalid_status_value_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        self._create(client, "flow6@example.com")
        inquiry_id = self._get_id(app, "flow6@example.com")
        resp = client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "not_a_status"}, headers=headers)
        assert resp.status_code == 422

    def test_status_update_requires_permission(self, client, app):
        headers = _super_admin_headers(client, app)
        self._create(client, "flow7@example.com")
        inquiry_id = self._get_id(app, "flow7@example.com")
        token = _register_and_login(client, email="norole@example.com")
        resp = client.patch(
            f"/api/v1/contact/{inquiry_id}/status", json={"status": "in_progress"}, headers=auth_headers(token)
        )
        assert resp.status_code == 403


class TestAssignment:
    def test_assign_to_active_staff(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="assignme@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="assignme@example.com").first().id
            staff = User.query.filter_by(email="admin@example.com").first()
            staff_id = staff.id

        resp = client.post(f"/api/v1/contact/{inquiry_id}/assign", json={"userId": staff_id}, headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["assigned_to"]["id"] == staff_id

    def test_assign_is_optional_unassign(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="unassign@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="unassign@example.com").first().id

        resp = client.post(f"/api/v1/contact/{inquiry_id}/assign", json={"userId": None}, headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["assigned_to"] is None

    def test_assign_invalid_user_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="badassign@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="badassign@example.com").first().id

        resp = client.post(f"/api/v1/contact/{inquiry_id}/assign", json={"userId": 999999}, headers=headers)
        assert resp.status_code == 422

    def test_assign_inactive_user_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="inactiveassign@example.com")
        token = _register_and_login(client, email="inactivestaff@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="inactiveassign@example.com").first().id
            inactive_user = User.query.filter_by(email="inactivestaff@example.com").first()
            inactive_user.is_active = False
            inactive_user_id = inactive_user.id
            db.session.commit()

        resp = client.post(f"/api/v1/contact/{inquiry_id}/assign", json={"userId": inactive_user_id}, headers=headers)
        assert resp.status_code == 422


class TestInternalNotes:
    def test_add_note_and_never_public(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _submit(client, email="notetest@example.com")
        reference = create.get_json()["data"]["reference"]
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="notetest@example.com").first().id

        resp = client.post(
            f"/api/v1/contact/{inquiry_id}/notes", json={"body": "Confidential internal follow-up plan."}, headers=headers
        )
        assert resp.status_code == 201
        assert len(resp.get_json()["data"]["notes"]) == 1

        # Never exposed anywhere the public can reach: no public GET exists,
        # and a fresh public submission's response never carries any notes.
        second = _submit(client, email="noteleak-check@example.com")
        raw = second.get_data(as_text=True)
        assert "Confidential internal follow-up plan" not in raw

    def test_notes_require_permission(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="noteperm@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="noteperm@example.com").first().id
        token = _register_and_login(client, email="notesnobody@example.com")
        resp = client.post(
            f"/api/v1/contact/{inquiry_id}/notes", json={"body": "x"}, headers=auth_headers(token)
        )
        assert resp.status_code == 403


class TestPrivacySeparation:
    def test_no_public_list_endpoint(self, client, app):
        headers = _super_admin_headers(client, app)
        # GET without auth must never succeed regardless of query shape.
        resp = client.get("/api/v1/contact")
        assert resp.status_code == 401

    def test_message_body_not_in_audit_metadata(self, client, app):
        headers = _super_admin_headers(client, app)
        secret_message = "This is a very private message body that must never leak into audit logs."
        _submit(client, email="auditprivacy@example.com", message=secret_message)
        with app.app_context():
            inquiry = ContactInquiry.query.filter_by(email="auditprivacy@example.com").first()
            entries = AuditLog.query.filter_by(action="contact.received", entity_id=str(inquiry.id)).all()
            assert len(entries) == 1
            assert secret_message not in str(entries[0].changes)

    def test_internal_note_not_in_audit_metadata(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="notesaudit@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="notesaudit@example.com").first().id
        secret_note = "Sensitive staff-only reasoning about this inquiry."
        client.post(f"/api/v1/contact/{inquiry_id}/notes", json={"body": secret_note}, headers=headers)
        with app.app_context():
            entries = AuditLog.query.filter_by(action="contact.note_added", entity_id=str(inquiry_id)).all()
            assert len(entries) == 1
            assert secret_note not in str(entries[0].changes)


class TestAuditIntegration:
    def test_assignment_is_audited(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="auditassign@example.com")
        with app.app_context():
            inquiry = ContactInquiry.query.filter_by(email="auditassign@example.com").first()
            inquiry_id = inquiry.id
            staff_id = User.query.filter_by(email="admin@example.com").first().id

        client.post(f"/api/v1/contact/{inquiry_id}/assign", json={"userId": staff_id}, headers=headers)
        with app.app_context():
            entry = AuditLog.query.filter_by(action="contact.assigned", entity_id=str(inquiry_id)).first()
            assert entry is not None

    def test_status_change_is_audited(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="auditstatus@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="auditstatus@example.com").first().id

        client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "in_progress"}, headers=headers)
        with app.app_context():
            entry = AuditLog.query.filter_by(action="contact.status_changed", entity_id=str(inquiry_id)).first()
            assert entry is not None
            assert entry.changes["from_status"] == "new"
            assert entry.changes["to_status"] == "in_progress"

    def test_resolution_is_audited(self, client, app):
        headers = _super_admin_headers(client, app)
        _submit(client, email="auditresolve@example.com")
        with app.app_context():
            inquiry_id = ContactInquiry.query.filter_by(email="auditresolve@example.com").first().id

        client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "in_progress"}, headers=headers)
        client.patch(f"/api/v1/contact/{inquiry_id}/status", json={"status": "resolved"}, headers=headers)
        with app.app_context():
            entries = AuditLog.query.filter_by(action="contact.status_changed", entity_id=str(inquiry_id)).all()
            assert any(e.changes["to_status"] == "resolved" for e in entries)


class TestSeedIdempotency:
    def test_contact_manage_permission_seeded_idempotently(self, app):
        with app.app_context():
            before_roles = Role.query.count()
            before_permissions = Permission.query.count()
            seed_roles_and_permissions()
            seed_roles_and_permissions()
            assert Role.query.count() == before_roles
            assert Permission.query.count() == before_permissions
            assert Permission.query.filter_by(name="contact.manage").first() is not None

    def test_admin_and_moderator_have_contact_manage(self, app):
        with app.app_context():
            for role_name in ("admin", "moderator"):
                role = Role.query.filter_by(name=role_name).first()
                perm_names = {p.name for p in role.permissions}
                assert "contact.manage" in perm_names

    def test_editor_lacks_contact_manage(self, app):
        with app.app_context():
            role = Role.query.filter_by(name="editor").first()
            perm_names = {p.name for p in role.permissions}
            assert "contact.manage" not in perm_names
