from datetime import date, timedelta

import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "mentorship-manager@example.com",
    "password": "supersecret1",
    "first_name": "Diana",
    "last_name": "Kioko",
    "country_code": "KE",
}

ADMIN_PAYLOAD = {
    "email": "mentorship-admin@example.com",
    "password": "supersecret1",
    "first_name": "Site",
    "last_name": "Admin",
    "country_code": "US",
}

MODERATOR_PAYLOAD = {
    "email": "mentorship-moderator@example.com",
    "password": "supersecret1",
    "first_name": "Mod",
    "last_name": "Erator",
    "country_code": "GB",
}

NO_PERMISSION_PAYLOAD = {
    "email": "mentorship-nobody@example.com",
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
    return _register_with_role(client, app, MANAGER_PAYLOAD, "mentorship_manager")


@pytest.fixture()
def admin_token(client, app):
    return _register_with_role(client, app, ADMIN_PAYLOAD, "admin")


@pytest.fixture()
def moderator_token(client, app):
    return _register_with_role(client, app, MODERATOR_PAYLOAD, "moderator")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


def _make_topic(app, slug="leadership", name="Leadership"):
    from app.extensions import db
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic.query.filter_by(slug=slug).first()
        if topic is None:
            topic = Topic(slug=slug, name=name)
            db.session.add(topic)
            db.session.commit()
        return topic.slug


def _make_program(app, slug="wsf-career-mentorship", status="draft", public_visible=False, **overrides):
    from app.extensions import db
    from app.models.mentorship import MentorshipProgram

    with app.app_context():
        program = MentorshipProgram.query.filter_by(slug=slug).first()
        if program is None:
            program = MentorshipProgram(slug=slug, name="WSF Career Mentorship")
            db.session.add(program)
        program.status = status
        program.public_visible = public_visible
        for key, value in overrides.items():
            setattr(program, key, value)
        db.session.commit()
        return program.id


def _open_program(app, **overrides):
    return _make_program(app, status="applications_open", public_visible=True, **overrides)


def _base_mentor_payload(program_id, **overrides):
    payload = {
        "programId": program_id,
        "role": "mentor",
        "firstName": "Amara",
        "lastName": "Diallo",
        "email": "mentor@example.com",
        "countryCode": "KE",
        "consentGiven": True,
        "yearsExperience": 10,
        "careerStagesSupported": ["Early Career", "Mid Career"],
    }
    payload.update(overrides)
    return payload


def _base_mentee_payload(program_id, **overrides):
    payload = {
        "programId": program_id,
        "role": "mentee",
        "firstName": "Zola",
        "lastName": "Nkosi",
        "email": "mentee@example.com",
        "countryCode": "ZA",
        "consentGiven": True,
        "careerStage": "Early Career",
    }
    payload.update(overrides)
    return payload


def _get_application_by_email(app, email, role):
    from app.models.mentorship import MentorshipApplication

    with app.app_context():
        return MentorshipApplication.query.filter_by(email=email.strip().lower(), role=role).first()


class TestPublicPrograms:
    def test_hides_draft_programs(self, client, app):
        _make_program(app, status="draft", public_visible=True)
        resp = client.get("/api/v1/mentorship/programs/public")
        assert resp.get_json()["data"] == []

    def test_hides_non_public_programs(self, client, app):
        _make_program(app, status="applications_open", public_visible=False)
        resp = client.get("/api/v1/mentorship/programs/public")
        assert resp.get_json()["data"] == []

    def test_shows_open_public_program(self, client, app):
        _open_program(app)
        resp = client.get("/api/v1/mentorship/programs/public")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "WSF Career Mentorship"
        assert data[0]["applicationOpenNow"] is True

    def test_applications_closed_status_still_visible_but_not_open(self, client, app):
        _make_program(app, status="applications_closed", public_visible=True)
        resp = client.get("/api/v1/mentorship/programs/public")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["applicationOpenNow"] is False


class TestPublicApplication:
    def test_mentor_application_creates_record(self, client, app):
        program_id = _open_program(app)
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        assert resp.status_code == 201
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        assert application is not None
        assert application.status == "submitted"
        assert application.consent_given is True

    def test_mentee_application_creates_record(self, client, app):
        program_id = _open_program(app)
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id))
        assert resp.status_code == 201
        application = _get_application_by_email(app, "mentee@example.com", "mentee")
        assert application is not None
        assert application.status == "submitted"

    def test_requires_consent(self, client, app):
        program_id = _open_program(app)
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id, consentGiven=False))
        assert resp.status_code == 422

    def test_requires_valid_email(self, client, app):
        program_id = _open_program(app)
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id, email="not-an-email"))
        assert resp.status_code == 422

    def test_requires_country(self, client, app):
        program_id = _open_program(app)
        payload = _base_mentor_payload(program_id)
        del payload["countryCode"]
        resp = client.post("/api/v1/mentorship/applications", json=payload)
        assert resp.status_code == 422

    def test_invalid_career_stage_rejected(self, client, app):
        program_id = _open_program(app)
        resp = client.post(
            "/api/v1/mentorship/applications", json=_base_mentee_payload(program_id, careerStage="Not A Stage")
        )
        assert resp.status_code == 422

    def test_application_rejected_when_program_draft(self, client, app):
        program_id = _make_program(app, status="draft", public_visible=True)
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        assert resp.status_code == 422

    def test_application_rejected_when_applications_closed(self, client, app):
        program_id = _make_program(app, status="applications_closed", public_visible=True)
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        assert resp.status_code == 422

    def test_application_rejected_outside_window(self, client, app):
        program_id = _open_program(
            app,
            application_opens_at=date.today() + timedelta(days=5),
        )
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        assert resp.status_code == 422

    def test_duplicate_same_program_same_role_acknowledged(self, client, app):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        assert resp.status_code == 200
        assert "already" in resp.get_json()["data"]["message"].lower()
        from app.models.mentorship import MentorshipApplication

        with app.app_context():
            assert MentorshipApplication.query.filter_by(email="mentor@example.com", role="mentor").count() == 1

    def test_same_applicant_can_apply_as_both_mentor_and_mentee(self, client, app):
        program_id = _open_program(app)
        resp1 = client.post(
            "/api/v1/mentorship/applications", json=_base_mentor_payload(program_id, email="dual@example.com")
        )
        resp2 = client.post(
            "/api/v1/mentorship/applications", json=_base_mentee_payload(program_id, email="dual@example.com")
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201

    def test_applicant_can_apply_to_a_different_program(self, client, app):
        program_a = _open_program(app, slug="program-a")
        program_b = _open_program(app, slug="program-b")
        resp1 = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_a))
        resp2 = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_b))
        assert resp1.status_code == 201
        assert resp2.status_code == 201

    def test_reapply_allowed_after_declined(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        client.patch(
            f"/api/v1/mentorship/applications/{application.id}/status", json={"status": "declined"},
            headers=auth_headers(manager_token),
        )
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        assert resp.status_code == 201

    def test_newsletter_not_subscribed_by_default(self, client, app):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        from app.models.newsletter import NewsletterSubscriber

        with app.app_context():
            assert NewsletterSubscriber.query.filter_by(email="mentor@example.com").first() is None

    def test_newsletter_opt_in_subscribes_via_existing_service(self, client, app):
        program_id = _open_program(app)
        client.post(
            "/api/v1/mentorship/applications",
            json=_base_mentor_payload(program_id, subscribeNewsletter=True),
        )
        from app.models.newsletter import NewsletterSubscriber

        with app.app_context():
            assert NewsletterSubscriber.query.filter_by(email="mentor@example.com").first() is not None

    def test_application_response_never_exposes_internal_id(self, client, app):
        program_id = _open_program(app)
        resp = client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        assert "id" not in resp.get_json()["data"]


class TestAdminPrograms:
    def test_list_requires_permission(self, client, app, no_permission_token):
        resp = client.get("/api/v1/mentorship/programs", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

    def test_moderator_can_manage_programs(self, client, app, moderator_token):
        resp = client.get("/api/v1/mentorship/programs", headers=auth_headers(moderator_token))
        assert resp.status_code == 200

    def test_create_program(self, client, app, manager_token):
        _make_topic(app)
        resp = client.post(
            "/api/v1/mentorship/programs",
            json={"slug": "new-program", "name": "New Program", "topicSlugs": ["leadership"]},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["name"] == "New Program"

    def test_create_program_duplicate_slug_rejected(self, client, app, manager_token):
        client.post(
            "/api/v1/mentorship/programs", json={"slug": "dup-slug", "name": "One"},
            headers=auth_headers(manager_token),
        )
        resp = client.post(
            "/api/v1/mentorship/programs", json={"slug": "dup-slug", "name": "Two"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 409

    def test_invalid_date_order_rejected(self, client, app, manager_token):
        resp = client.post(
            "/api/v1/mentorship/programs",
            json={
                "slug": "bad-dates", "name": "Bad Dates",
                "programStartsAt": "2027-06-01", "programEndsAt": "2027-01-01",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_update_program_partial_preserves_fields(self, client, app, manager_token):
        program_id = _make_program(app)
        resp = client.patch(
            f"/api/v1/mentorship/programs/{program_id}", json={"mentorCapacity": 5},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["mentor_capacity"] == 5
        assert data["name"] == "WSF Career Mentorship"

    def test_status_action_opens_applications(self, client, app, manager_token):
        program_id = _make_program(app, status="draft")
        resp = client.patch(
            f"/api/v1/mentorship/programs/{program_id}/status", json={"status": "applications_open"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "applications_open"

    def test_delete_restricted_when_has_applications(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        resp = client.delete(f"/api/v1/mentorship/programs/{program_id}", headers=auth_headers(manager_token))
        assert resp.status_code == 409

    def test_delete_allowed_for_empty_draft(self, client, app, manager_token):
        program_id = _make_program(app, slug="deletable", status="draft")
        resp = client.delete(f"/api/v1/mentorship/programs/{program_id}", headers=auth_headers(manager_token))
        assert resp.status_code == 204


class TestAdminApplications:
    def test_list_and_filter_by_role(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id))
        resp = client.get("/api/v1/mentorship/applications?role=mentor", headers=auth_headers(manager_token))
        assert len(resp.get_json()["data"]) == 1
        assert resp.get_json()["data"][0]["role"] == "mentor"

    def test_search_by_name(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        resp = client.get("/api/v1/mentorship/applications?q=Amara", headers=auth_headers(manager_token))
        assert len(resp.get_json()["data"]) == 1

    def test_filter_by_country(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        resp = client.get("/api/v1/mentorship/applications?country=KE", headers=auth_headers(manager_token))
        assert len(resp.get_json()["data"]) == 1
        resp = client.get("/api/v1/mentorship/applications?country=US", headers=auth_headers(manager_token))
        assert len(resp.get_json()["data"]) == 0

    def test_admin_detail_includes_email_and_notes(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        resp = client.get(f"/api/v1/mentorship/applications/{application.id}", headers=auth_headers(manager_token))
        data = resp.get_json()["data"]
        assert data["email"] == "mentor@example.com"
        assert "notes" in data

    def test_status_change_to_approved(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        resp = client.patch(
            f"/api/v1/mentorship/applications/{application.id}/status", json={"status": "approved"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "approved"

    def test_invalid_status_rejected(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        resp = client.patch(
            f"/api/v1/mentorship/applications/{application.id}/status", json={"status": "not-a-status"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_internal_note_never_leaks_publicly(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        resp = client.post(
            f"/api/v1/mentorship/applications/{application.id}/notes",
            json={"body": "Strong candidate, fast-track"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201
        public = client.get("/api/v1/mentorship/programs/public")
        assert "fast-track" not in str(public.get_json())

    def test_history_records_status_change(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        client.patch(
            f"/api/v1/mentorship/applications/{application.id}/status", json={"status": "reviewing"},
            headers=auth_headers(manager_token),
        )
        resp = client.get(f"/api/v1/mentorship/applications/{application.id}/history", headers=auth_headers(manager_token))
        actions = {e["action"] for e in resp.get_json()["data"]}
        assert "mentorship.application_status_change" in actions

    def test_delete_restricted_for_approved_application(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        client.patch(
            f"/api/v1/mentorship/applications/{application.id}/status", json={"status": "approved"},
            headers=auth_headers(manager_token),
        )
        resp = client.delete(f"/api/v1/mentorship/applications/{application.id}", headers=auth_headers(manager_token))
        assert resp.status_code == 409

    def test_delete_allowed_for_submitted_without_notes(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        application = _get_application_by_email(app, "mentor@example.com", "mentor")
        resp = client.delete(f"/api/v1/mentorship/applications/{application.id}", headers=auth_headers(manager_token))
        assert resp.status_code == 204


class TestMatching:
    def _approve(self, client, manager_token, app, email, role):
        application = _get_application_by_email(app, email, role)
        client.patch(
            f"/api/v1/mentorship/applications/{application.id}/status", json={"status": "approved"},
            headers=auth_headers(manager_token),
        )
        return application.id

    def test_create_match_requires_approved_applications(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id))
        mentor_id = _get_application_by_email(app, "mentor@example.com", "mentor").id
        mentee_id = _get_application_by_email(app, "mentee@example.com", "mentee").id
        resp = client.post(
            "/api/v1/mentorship/matches",
            json={"mentorApplicationId": mentor_id, "menteeApplicationId": mentee_id},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_create_match_success(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id))
        mentor_id = self._approve(client, manager_token, app, "mentor@example.com", "mentor")
        mentee_id = self._approve(client, manager_token, app, "mentee@example.com", "mentee")

        resp = client.post(
            "/api/v1/mentorship/matches",
            json={"mentorApplicationId": mentor_id, "menteeApplicationId": mentee_id},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["status"] == "proposed"

    def test_create_match_rejects_mismatched_program(self, client, app, manager_token):
        program_a = _open_program(app, slug="program-a")
        program_b = _open_program(app, slug="program-b")
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_a))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_b))
        mentor_id = self._approve(client, manager_token, app, "mentor@example.com", "mentor")
        mentee_id = self._approve(client, manager_token, app, "mentee@example.com", "mentee")
        resp = client.post(
            "/api/v1/mentorship/matches",
            json={"mentorApplicationId": mentor_id, "menteeApplicationId": mentee_id},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_create_match_rejects_wrong_roles(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id, email="m1@example.com"))
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id, email="m2@example.com"))
        id1 = self._approve(client, manager_token, app, "m1@example.com", "mentor")
        id2 = self._approve(client, manager_token, app, "m2@example.com", "mentor")
        resp = client.post(
            "/api/v1/mentorship/matches", json={"mentorApplicationId": id1, "menteeApplicationId": id2},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_match_status_transition_to_completed_sets_date(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id))
        mentor_id = self._approve(client, manager_token, app, "mentor@example.com", "mentor")
        mentee_id = self._approve(client, manager_token, app, "mentee@example.com", "mentee")
        match = client.post(
            "/api/v1/mentorship/matches", json={"mentorApplicationId": mentor_id, "menteeApplicationId": mentee_id},
            headers=auth_headers(manager_token),
        ).get_json()["data"]

        resp = client.patch(
            f"/api/v1/mentorship/matches/{match['id']}/status", json={"status": "completed"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "completed"
        assert data["actual_completion_date"] is not None

    def test_capacity_warning_when_mentor_exceeds_stated_capacity(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post(
            "/api/v1/mentorship/applications",
            json=_base_mentor_payload(program_id, email="capacity-mentor@example.com"),
        )
        mentor_app = _get_application_by_email(app, "capacity-mentor@example.com", "mentor")
        from app.extensions import db

        with app.app_context():
            from app.models.mentorship import MentorshipApplication

            m = db.session.get(MentorshipApplication, mentor_app.id)
            m.mentor_capacity = 2
            db.session.commit()
        client.patch(
            f"/api/v1/mentorship/applications/{mentor_app.id}/status", json={"status": "approved"},
            headers=auth_headers(manager_token),
        )

        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id, email="mentee1@example.com"))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id, email="mentee2@example.com"))
        mentee1_id = self._approve(client, manager_token, app, "mentee1@example.com", "mentee")
        mentee2_id = self._approve(client, manager_token, app, "mentee2@example.com", "mentee")

        resp1 = client.post(
            "/api/v1/mentorship/matches",
            json={"mentorApplicationId": mentor_app.id, "menteeApplicationId": mentee1_id},
            headers=auth_headers(manager_token),
        )
        assert "capacityWarning" not in resp1.get_json()["data"]

        resp2 = client.post(
            "/api/v1/mentorship/matches",
            json={"mentorApplicationId": mentor_app.id, "menteeApplicationId": mentee2_id},
            headers=auth_headers(manager_token),
        )
        assert resp2.status_code == 201
        assert "capacityWarning" in resp2.get_json()["data"]

    def test_cancelled_match_preserved_as_history_and_rematch_creates_new_row(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id))
        mentor_id = self._approve(client, manager_token, app, "mentor@example.com", "mentor")
        mentee_id = self._approve(client, manager_token, app, "mentee@example.com", "mentee")
        match = client.post(
            "/api/v1/mentorship/matches", json={"mentorApplicationId": mentor_id, "menteeApplicationId": mentee_id},
            headers=auth_headers(manager_token),
        ).get_json()["data"]

        client.patch(
            f"/api/v1/mentorship/matches/{match['id']}/status",
            json={"status": "rematch_needed", "closureReason": "Scheduling conflict"},
            headers=auth_headers(manager_token),
        )
        rematch = client.post(
            "/api/v1/mentorship/matches", json={"mentorApplicationId": mentor_id, "menteeApplicationId": mentee_id},
            headers=auth_headers(manager_token),
        )
        assert rematch.status_code == 201
        assert rematch.get_json()["data"]["id"] != match["id"]

        from app.extensions import db
        from app.models.mentorship import MentorshipMatch

        with app.app_context():
            assert MentorshipMatch.query.count() == 2
            original = db.session.get(MentorshipMatch, match["id"])
            assert original.status == "rematch_needed"
            assert original.closure_reason == "Scheduling conflict"

    def test_sessions_are_admin_only(self, client, app, manager_token, no_permission_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id))
        mentor_id = self._approve(client, manager_token, app, "mentor@example.com", "mentor")
        mentee_id = self._approve(client, manager_token, app, "mentee@example.com", "mentee")
        match = client.post(
            "/api/v1/mentorship/matches", json={"mentorApplicationId": mentor_id, "menteeApplicationId": mentee_id},
            headers=auth_headers(manager_token),
        ).get_json()["data"]

        resp = client.post(
            f"/api/v1/mentorship/matches/{match['id']}/sessions",
            json={"sessionDate": str(date.today()), "summary": "Discussed career goals"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201

        no_perm = client.post(
            f"/api/v1/mentorship/matches/{match['id']}/sessions",
            json={"sessionDate": str(date.today())},
            headers=auth_headers(no_permission_token),
        )
        assert no_perm.status_code == 403


class TestOverview:
    def test_overview_reflects_real_counts(self, client, app, manager_token):
        program_id = _open_program(app)
        client.post("/api/v1/mentorship/applications", json=_base_mentor_payload(program_id))
        client.post("/api/v1/mentorship/applications", json=_base_mentee_payload(program_id))
        resp = client.get("/api/v1/mentorship/overview", headers=auth_headers(manager_token))
        data = resp.get_json()["data"]
        assert data["openPrograms"] == 1
        assert data["mentorApplications"] == 1
        assert data["menteeApplications"] == 1
        assert data["approvedMentors"] == 0

    def test_overview_requires_permission(self, client, app, no_permission_token):
        resp = client.get("/api/v1/mentorship/overview", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403


class TestRBAC:
    def test_admin_role_has_mentorship_access(self, client, app, admin_token):
        resp = client.get("/api/v1/mentorship/programs", headers=auth_headers(admin_token))
        assert resp.status_code == 200
