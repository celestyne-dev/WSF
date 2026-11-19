"""WSF Learning certificates of completion: opt-in, eligibility, automatic
idempotent issuance from the backend completion flow, snapshots, revoke +
reissue, public verification privacy, PDF authorization and admin tools."""
import threading
import uuid

import pytest

from app.extensions import db
from tests.conftest import auth_headers
from tests.test_learning_circle_access import _make_program

LEARNER = {"email": "cert-learner@example.com", "password": "supersecret1", "first_name": "Amara", "last_name": "Okafor"}
OTHER = {"email": "cert-other@example.com", "password": "supersecret1", "first_name": "Other", "last_name": "Person"}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    return client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]


@pytest.fixture()
def learner(client):
    return _register(client, LEARNER)


@pytest.fixture()
def admin(client, app):
    from app.models.user import Role, User

    payload = {"email": "cert-admin@example.com", "password": "supersecret1", "first_name": "Ada", "last_name": "Admin"}
    _register(client, payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="admin").first())
        db.session.commit()
    return auth_headers(client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"])


def _program(app, lessons=2, enabled=True, **extra):
    program_id, lesson_ids = _make_program(app, lesson_count=lessons, access_type=extra.pop("access_type", "free"), **extra)
    from app.models.learning import LearningProgram

    with app.app_context():
        program = db.session.get(LearningProgram, program_id)
        program.certificate_enabled = enabled
        program.certificate_signatory_name = "Celestine Nyamoita"
        program.certificate_signatory_title = "Founder, Women Shaping Futures"
        db.session.commit()
    return program_id, lesson_ids


def _enroll(client, token, program_id):
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(token))
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()["data"]["enrollment"]["id"]


def _complete(client, token, enrollment_id, lesson_id):
    return client.post(f"/api/v1/learning-enrollments/{enrollment_id}/lessons/{lesson_id}/complete", headers=auth_headers(token))


def _certificates(app):
    from app.models.learning_certificate import LearningCertificate

    with app.app_context():
        return LearningCertificate.query.order_by(LearningCertificate.id).all()


def _finish(client, token, program_id, lesson_ids):
    enrollment_id = _enroll(client, token, program_id)
    for lesson_id in lesson_ids:
        assert _complete(client, token, enrollment_id, lesson_id).status_code == 200
    return enrollment_id


class TestIssuance:
    def test_disabled_program_issues_nothing(self, client, app, learner):
        program_id, lessons = _program(app, enabled=False)
        _finish(client, learner, program_id, lessons)
        assert _certificates(app) == []

    def test_incomplete_program_issues_nothing(self, client, app, learner):
        program_id, lessons = _program(app, lessons=2)
        enrollment_id = _enroll(client, learner, program_id)
        _complete(client, learner, enrollment_id, lessons[0])
        assert _certificates(app) == []

    def test_final_lesson_issues_one_certificate_with_snapshot(self, client, app, learner):
        program_id, lessons = _program(app)
        enrollment_id = _finish(client, learner, program_id, lessons)
        (cert,) = _certificates(app)
        assert cert.status == "active" and cert.enrollment_id == enrollment_id
        assert cert.recipient_name == "Amara Okafor" and cert.issuer_name == "Women Shaping Futures"
        assert cert.certificate_title == "Certificate of Completion"
        assert cert.signatory_name == "Celestine Nyamoita" and cert.completed_at is not None
        assert cert.certificate_number.startswith("WSF-") and str(cert.id) not in cert.certificate_number.split("-")[-1]
        assert len(cert.public_id) == 36

    def test_duplicate_completion_never_duplicates(self, client, app, learner):
        program_id, lessons = _program(app, lessons=1)
        enrollment_id = _finish(client, learner, program_id, lessons)
        assert client.delete(f"/api/v1/learning-enrollments/{enrollment_id}/lessons/{lessons[0]}/complete", headers=auth_headers(learner)).status_code == 200
        assert len(_certificates(app)) == 1 and _certificates(app)[0].status == "active"  # un-completing never revokes
        _complete(client, learner, enrollment_id, lessons[0])
        _complete(client, learner, enrollment_id, lessons[0])
        assert len(_certificates(app)) == 1

    def test_concurrent_issuance_creates_one(self, client, app, learner):
        from app.models.learning_enrollment import LearningEnrollment
        from app.services.learning_certificates import issue_certificate_if_eligible

        program_id, lessons = _program(app, lessons=1)
        enrollment_id = _finish(client, learner, program_id, lessons)
        from app.models.learning_certificate import LearningCertificate

        with app.app_context():
            LearningCertificate.query.delete()
            db.session.commit()
        barrier = threading.Barrier(2)
        results = []

        def worker():
            with app.app_context():
                enrollment = db.session.get(LearningEnrollment, enrollment_id)
                barrier.wait()
                try:
                    results.append(issue_certificate_if_eligible(enrollment).id)
                    db.session.commit()
                finally:
                    db.session.remove()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        assert len(_certificates(app)) == 1
        assert len(set(results)) == 1

    @pytest.mark.parametrize("access", ["external"])
    def test_external_program_never_issues(self, client, app, learner, access):
        from app.models.learning import LearningProgram
        from app.services.learning_certificates import program_issues_certificates

        program_id, _ = _program(app, access_type=access, external_url="https://partner.example.org/course")
        with app.app_context():
            assert program_issues_certificates(db.session.get(LearningProgram, program_id)) is False

    def test_partner_provider_program_never_issues(self, client, app, learner):
        from app.models.people import Organization

        with app.app_context():
            org = Organization(slug="partner-x", name="Partner X", status="published")
            db.session.add(org)
            db.session.commit()
            org_id = org.id
        program_id, lessons = _program(app, provider_organization_id=org_id)
        _finish(client, learner, program_id, lessons)
        assert _certificates(app) == []


class TestSnapshots:
    def test_renames_and_new_lessons_never_change_an_issued_certificate(self, client, app, learner):
        from app.models.learning import LearningLesson, LearningModule, LearningProgram
        from app.models.people import Author

        program_id, lessons = _program(app, lessons=1)
        _finish(client, learner, program_id, lessons)
        (before,) = _certificates(app)
        with app.app_context():
            program = db.session.get(LearningProgram, program_id)
            program.title = "Renamed Program"
            db.session.get(Author, program.primary_instructor_id).name = "Renamed Instructor"
            module = LearningModule.query.filter_by(learning_program_id=program_id).first()
            db.session.add(LearningLesson(module_id=module.id, title="New", lesson_type="text", content=[], sort_order=5))
            db.session.commit()
        (after,) = _certificates(app)
        assert after.status == "active"
        assert after.program_title == before.program_title == "Test Program"
        assert after.instructor_names == before.instructor_names and "Renamed Instructor" not in after.instructor_names


class TestVerificationAndPdf:
    def test_public_verification_is_safe(self, client, app, learner):
        program_id, lessons = _program(app, lessons=1)
        _finish(client, learner, program_id, lessons)
        (cert,) = _certificates(app)
        data = client.get(f"/api/v1/certificates/verify/{cert.public_id}").get_json()["data"]
        assert data["status"] == "active" and data["recipientName"] == "Amara Okafor" and data["programTitle"] == "Test Program"
        body = client.get(f"/api/v1/certificates/verify/{cert.public_id}").get_data(as_text=True)
        for secret in (LEARNER["email"], '"userId"', '"user_id"', '"enrollmentId"', f'"id": {cert.id}'):
            assert secret not in body
        assert client.get(f"/api/v1/certificates/verify/{uuid.uuid4()}").status_code == 404

    def test_pdf_owner_only(self, client, app, learner, admin):
        program_id, lessons = _program(app, lessons=1)
        _finish(client, learner, program_id, lessons)
        (cert,) = _certificates(app)
        url = f"/api/v1/certificates/{cert.public_id}/pdf"
        assert client.get(url).status_code == 401
        other = _register(client, OTHER)
        assert client.get(url, headers=auth_headers(other)).status_code == 404
        resp = client.get(url, headers=auth_headers(learner))
        assert resp.status_code == 200 and resp.headers["Content-Type"] == "application/pdf"
        assert resp.data[:5] == b"%PDF-" and len(resp.data) > 2000
        assert client.get(url, headers=admin).status_code == 200

    def test_my_learning_and_my_certificates(self, client, app, learner):
        program_id, lessons = _program(app, lessons=1)
        _finish(client, learner, program_id, lessons)
        rows = client.get("/api/v1/learning-enrollments/me", headers=auth_headers(learner)).get_json()["data"]
        assert rows[0]["certificate_enabled"] is True
        assert rows[0]["certificate"]["certificateNumber"].startswith("WSF-")
        assert rows[0]["certificate"]["linkedinUrl"].startswith("https://www.linkedin.com/profile/add?")
        mine = client.get("/api/v1/certificates/me", headers=auth_headers(learner)).get_json()["data"]
        assert len(mine) == 1 and mine[0]["verificationUrl"].endswith(mine[0]["publicId"])

    def test_program_payload_advertises_certificate_only_when_enabled(self, client, app):
        from app.models.learning import LearningProgram

        on_id, _ = _program(app, lessons=1)
        off_id, _ = _program(app, lessons=1, enabled=False)
        with app.app_context():
            on, off = db.session.get(LearningProgram, on_id).slug, db.session.get(LearningProgram, off_id).slug
        assert client.get(f"/api/v1/learning/{on}").get_json()["data"]["certificateAvailable"] is True
        assert client.get(f"/api/v1/learning/{off}").get_json()["data"]["certificateAvailable"] is False


class TestAdmin:
    def test_list_revoke_and_reissue(self, client, app, learner, admin):
        program_id, lessons = _program(app, lessons=1)
        _finish(client, learner, program_id, lessons)
        listed = client.get("/api/v1/certificates/admin", query_string={"q": "amara"}, headers=admin).get_json()
        assert len(listed["data"]) == 1 and listed["data"][0]["learnerEmail"] == LEARNER["email"]
        cert_id = listed["data"][0]["id"]
        assert client.post(f"/api/v1/certificates/admin/{cert_id}/revoke", json={}, headers=admin).status_code == 422
        revoked = client.post(f"/api/v1/certificates/admin/{cert_id}/revoke", json={"reason": "Issued in error"}, headers=admin)
        assert revoked.status_code == 200 and revoked.get_json()["data"]["status"] == "revoked"
        public_id = revoked.get_json()["data"]["publicId"]
        assert client.get(f"/api/v1/certificates/verify/{public_id}").get_json()["data"]["status"] == "revoked"
        reissued = client.post(f"/api/v1/certificates/admin/{cert_id}/reissue", json={"reason": "Name corrected"}, headers=admin)
        assert reissued.status_code == 201
        new = reissued.get_json()["data"]
        assert new["status"] == "active" and new["replacesCertificateId"] == cert_id and new["publicId"] != public_id
        statuses = sorted(c.status for c in _certificates(app))
        assert statuses == ["active", "revoked"]

    def test_admin_requires_permission(self, client, app, learner):
        assert client.get("/api/v1/certificates/admin", headers=auth_headers(learner)).status_code == 403

    def test_studio_toggles_certificate_settings_and_omission_keeps_them(self, client, app, admin):
        program_id, _ = _program(app, lessons=1, enabled=False)
        current = client.get(f"/api/v1/learning/admin/programs/{program_id}", headers=admin).get_json()["data"]
        base = {"title": current["title"], "slug": current["slug"], "status": "published",
                "primaryInstructorSlug": (current.get("primary_instructor") or {}).get("slug")}
        body = {**base, "certificateEnabled": True,
                "certificateTitle": "Certificate of Completion", "certificateSignatoryName": "Celestine Nyamoita"}
        resp = client.patch(f"/api/v1/learning/admin/programs/{program_id}", json=body, headers=admin)
        assert resp.status_code == 200, resp.get_json()
        data = resp.get_json()["data"]
        assert data["certificate_enabled"] is True and data["certificate_signatory_name"] == "Celestine Nyamoita"
        again = client.patch(f"/api/v1/learning/admin/programs/{program_id}", json=base, headers=admin)
        assert again.get_json()["data"]["certificate_enabled"] is True


class TestMigrations:
    def test_chain(self):
        import os

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config()
        config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
        script = ScriptDirectory.from_config(config)
        assert len(script.get_heads()) == 1
        assert script.get_revision("a1d3b6e8f0c5").down_revision == "f9c2a5d0e7b4"
        assert script.get_revision("f9c2a5d0e7b4").down_revision == "e8b1f4c9d6a3"


class TestVerificationShell:
    def test_verify_shell_status_follows_certificate_existence(self, client, app, learner, admin):
        import os

        app.config["SPA_INDEX_PATH"] = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")

        def shell(public_id):
            resp = client.get(f"/certificates/verify/{public_id}")
            html = resp.get_data(as_text=True)
            # Same safe noindex shell whatever the status; never a recipient name.
            assert "noindex, nofollow" in html and "Verify a Certificate" in html
            assert "Amara" not in html and "Okafor" not in html
            return resp.status_code

        assert shell(uuid.uuid4()) == 404  # invented id: never looks valid
        assert shell("not-a-uuid") == 404
        program_id, lesson_ids = _program(app, lessons=1)
        _finish(client, learner, program_id, lesson_ids)
        cert = _certificates(app)[0]
        assert shell(cert.public_id) == 200
        client.post(f"/api/v1/certificates/admin/{cert.id}/revoke", json={"reason": "Issued in error"}, headers=admin)
        assert shell(cert.public_id) == 200  # revoked still exists; the page shows it as revoked
        assert client.get(f"/api/v1/certificates/verify/{cert.public_id}").get_json()["data"]["status"] == "revoked"
        assert client.get("/certificates/verify").status_code == 404

    def test_certificates_is_a_reserved_slug(self):
        from app.utils.slugs import is_reserved_slug

        assert is_reserved_slug("certificates")
