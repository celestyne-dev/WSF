"""Focused tests for first-party WSF Learning enrollment and lesson
progress — see app/models/learning_enrollment.py,
app/services/learning_enrollments.py, app/api/v1/learning_enrollments.py
(self-service), the read-only enrollment list added to
app/api/v1/learning.py (staff), and the AdminLearningCurriculumResource
ID-preservation refactor in that same file.
"""
import uuid

import pytest

from tests.conftest import auth_headers

USER_A = {
    "email": "learnenroll-user-a@example.com",
    "password": "supersecret1",
    "first_name": "Amina",
    "last_name": "Diallo",
    "country_code": "SN",
}
USER_B = {
    "email": "learnenroll-user-b@example.com",
    "password": "supersecret1",
    "first_name": "Beatrice",
    "last_name": "Mwangi",
    "country_code": "KE",
}
MANAGER_PAYLOAD = {
    "email": "learnenroll-manager@example.com",
    "password": "supersecret1",
    "first_name": "Amara",
    "last_name": "Nwosu",
    "country_code": "NG",
}
NO_PERMISSION_PAYLOAD = {
    "email": "learnenroll-nobody@example.com",
    "password": "supersecret1",
    "first_name": "No",
    "last_name": "Permission",
    "country_code": "US",
}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


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
def user_a_token(client):
    return _register(client, USER_A)


@pytest.fixture()
def user_b_token(client):
    return _register(client, USER_B)


@pytest.fixture()
def manager_token(client, app):
    return _register_with_role(client, app, MANAGER_PAYLOAD, "learning_manager")


@pytest.fixture()
def no_permission_token(client):
    # Registration already assigns the base "member" role (see
    # RegisterResource) — no learning.manage permission on it, so no
    # extra role assignment is needed to exercise "unauthorized staff".
    return _register(client, NO_PERMISSION_PAYLOAD)


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _instructor_id(app):
    from app.extensions import db
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="learnenroll-instructor").first()
        if author is None:
            author = Author(slug="learnenroll-instructor", name="Learning Instructor", status="active")
            db.session.add(author)
            db.session.commit()
        return author.id


def _make_program(app, lesson_count=2, **overrides):
    """Direct-ORM program + one module with `lesson_count` lessons —
    bypasses the curriculum PUT endpoint for test setup speed. Returns
    (program_id, [lesson_id, ...]) in curriculum order.
    """
    from app.extensions import db
    from app.models.learning import LearningLesson, LearningModule, LearningProgram

    instructor_id = _instructor_id(app)
    with app.app_context():
        program = LearningProgram(
            slug=overrides.pop("slug", _slug("program")),
            title=overrides.pop("title", "Test Program"),
            overview=[],
            status=overrides.pop("status", "published"),
            access_type=overrides.pop("access_type", "free"),
            primary_instructor_id=instructor_id,
            **overrides,
        )
        db.session.add(program)
        db.session.flush()

        lesson_ids = []
        if lesson_count:
            module = LearningModule(learning_program_id=program.id, title="Module 1", sort_order=0)
            db.session.add(module)
            db.session.flush()
            for i in range(lesson_count):
                lesson = LearningLesson(module_id=module.id, title=f"Lesson {i + 1}", lesson_type="text", content=[], sort_order=i)
                db.session.add(lesson)
                db.session.flush()
                lesson_ids.append(lesson.id)
        db.session.commit()
        return program.id, lesson_ids


def _get_program_slug(app, program_id):
    from app.extensions import db
    from app.models.learning import LearningProgram

    with app.app_context():
        return db.session.get(LearningProgram, program_id).slug


def _count_enrollments(app, program_id=None):
    from app.models.learning_enrollment import LearningEnrollment

    with app.app_context():
        query = LearningEnrollment.query
        if program_id is not None:
            query = query.filter_by(learning_program_id=program_id)
        return query.count()


def _get_enrollment_row(app, program_id, email):
    from app.models.learning_enrollment import LearningEnrollment
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        return LearningEnrollment.query.filter_by(learning_program_id=program_id, user_id=user.id).first()


def _base_curriculum_payload(**overrides):
    payload = {"modules": [{"title": "Module One", "lessons": [{"title": "Lesson One", "lessonType": "text"}]}]}
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Enrollment eligibility
# ---------------------------------------------------------------------------


def test_enroll_requires_auth(client, app):
    program_id, _ = _make_program(app)
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id})
    assert resp.status_code == 401


def test_enroll_without_community_membership_succeeds(client, app, no_permission_token):
    program_id, _ = _make_program(app)
    resp = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(no_permission_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrolled"] is True


def test_enroll_rejects_draft_program(client, app, user_a_token):
    program_id, _ = _make_program(app, status="draft")
    resp = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 404
    assert _count_enrollments(app, program_id) == 0


def test_enroll_rejects_archived_program(client, app, user_a_token):
    program_id, _ = _make_program(app, status="archived")
    resp = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 404


def test_enroll_rejects_external_program_no_row_created(client, app, user_a_token):
    program_id, _ = _make_program(app, access_type="external", external_url="https://example.org/enroll")
    resp = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "external_enrollment"
    assert _count_enrollments(app, program_id) == 0


def test_enroll_rejects_product_program_no_row_created(client, app, user_a_token):
    from app.extensions import db
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=_slug("product"), name="A Product", price=4900, currency="USD", status="active")
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    program_id, _ = _make_program(app, access_type="product", product_id=product_id)
    resp = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "product_enrollment"
    assert _count_enrollments(app, program_id) == 0


def test_enroll_nonexistent_program_404(client, user_a_token):
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": 999999}, headers=auth_headers(user_a_token))
    assert resp.status_code == 404


def test_enroll_invalid_program_id_422(client, user_a_token):
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": "x"}, headers=auth_headers(user_a_token))
    assert resp.status_code == 422


def test_forced_password_change_blocks_enrollment(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    program_id, _ = _make_program(app)
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    resp = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "password_change_required"


# ---------------------------------------------------------------------------
# Idempotency, uniqueness, isolation
# ---------------------------------------------------------------------------


def test_duplicate_enroll_idempotent(client, app, user_a_token):
    program_id, _ = _make_program(app)
    first = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    second = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.get_json()["data"]["enrollment"]["id"] == second.get_json()["data"]["enrollment"]["id"]
    assert _count_enrollments(app, program_id) == 1


def test_unique_constraint_enforced_at_db_level(app):
    from sqlalchemy.exc import IntegrityError

    from app.extensions import db
    from app.models.learning_enrollment import LearningEnrollment
    from app.models.user import User

    program_id, _ = _make_program(app)
    with app.app_context():
        user = User.query.filter_by(email="nobody-yet@example.com").first()
        if user is None:
            from app.services.rbac import seed_roles_and_permissions

            seed_roles_and_permissions()
            user = User(email="dup-test@example.com", first_name="Dup", last_name="Test")
            user.set_password("supersecret1")
            db.session.add(user)
            db.session.commit()
        db.session.add(LearningEnrollment(learning_program_id=program_id, user_id=user.id, status="active"))
        db.session.commit()
        db.session.add(LearningEnrollment(learning_program_id=program_id, user_id=user.id, status="active"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_user_cannot_enroll_as_other_user(client, app, user_a_token):
    program_id, _ = _make_program(app)
    resp = client.post(
        "/api/v1/learning-enrollments",
        json={"program_id": program_id, "user_id": 999999},
        headers=auth_headers(user_a_token),
    )
    assert resp.status_code == 200
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    assert enrollment is not None  # attached to the authenticated caller, never the spoofed id


def test_withdraw_owner_only(client, app, user_a_token, user_b_token):
    program_id, _ = _make_program(app)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    resp = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_b_token))
    assert resp.status_code == 404  # scoped lookup — never leaks that it belongs to someone else


def test_withdraw_idempotent(client, app, user_a_token):
    program_id, _ = _make_program(app)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    first = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_a_token))
    second = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_a_token))
    assert first.status_code == 200 and second.status_code == 200
    assert first.get_json()["data"]["enrollment"]["status"] == "withdrawn"
    assert second.get_json()["data"]["enrollment"]["status"] == "withdrawn"


def test_reactivation_uses_same_row(client, app, user_a_token):
    program_id, _ = _make_program(app)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_a_token))

    resp = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrollment"]["id"] == enrollment.id
    assert resp.get_json()["data"]["enrollment"]["status"] == "active"
    assert _count_enrollments(app, program_id) == 1


def test_reactivation_preserves_progress(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_a_token))

    resp = client.post(
        "/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token)
    )
    data = resp.get_json()["data"]["enrollment"]
    assert data["completed_lessons"] == 1
    assert data["total_lessons"] == 2


def test_check_isolation(client, app, user_a_token, user_b_token):
    program_id, _ = _make_program(app)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))

    resp_a = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    resp_b = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_b_token))
    assert resp_a.get_json()["data"]["enrolled"] is True
    assert resp_b.get_json()["data"]["enrolled"] is False
    assert resp_b.get_json()["data"]["enrollment"] is None


def test_me_isolation(client, app, user_a_token, user_b_token):
    program_id, _ = _make_program(app)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))

    resp_a = client.get("/api/v1/learning-enrollments/me", headers=auth_headers(user_a_token))
    resp_b = client.get("/api/v1/learning-enrollments/me", headers=auth_headers(user_b_token))
    assert len(resp_a.get_json()["data"]) == 1
    assert len(resp_b.get_json()["data"]) == 0


# ---------------------------------------------------------------------------
# /me state filtering + pagination
# ---------------------------------------------------------------------------


def test_me_state_filters(client, app, user_a_token):
    current_id, current_lessons = _make_program(app, lesson_count=1, title="Current Program")
    completed_id, completed_lessons = _make_program(app, lesson_count=1, title="Completed Program")
    withdrawn_id, _ = _make_program(app, lesson_count=1, title="Withdrawn Program")

    client.post("/api/v1/learning-enrollments", json={"program_id": current_id}, headers=auth_headers(user_a_token))
    client.post("/api/v1/learning-enrollments", json={"program_id": completed_id}, headers=auth_headers(user_a_token))
    client.post("/api/v1/learning-enrollments", json={"program_id": withdrawn_id}, headers=auth_headers(user_a_token))

    completed_enrollment = _get_enrollment_row(app, completed_id, USER_A["email"])
    client.post(
        f"/api/v1/learning-enrollments/{completed_enrollment.id}/lessons/{completed_lessons[0]}/complete",
        headers=auth_headers(user_a_token),
    )
    withdrawn_enrollment = _get_enrollment_row(app, withdrawn_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{withdrawn_enrollment.id}/withdraw", headers=auth_headers(user_a_token))

    current = client.get("/api/v1/learning-enrollments/me?state=current", headers=auth_headers(user_a_token)).get_json()["data"]
    completed = client.get("/api/v1/learning-enrollments/me?state=completed", headers=auth_headers(user_a_token)).get_json()["data"]
    withdrawn = client.get("/api/v1/learning-enrollments/me?state=withdrawn", headers=auth_headers(user_a_token)).get_json()["data"]

    assert [r["program"]["title"] for r in current] == ["Current Program"]
    assert [r["program"]["title"] for r in completed] == ["Completed Program"]
    assert [r["program"]["title"] for r in withdrawn] == ["Withdrawn Program"]


def test_me_pagination(client, app, user_a_token):
    for i in range(3):
        pid, _ = _make_program(app, lesson_count=0, title=f"Program {i}")
        client.post("/api/v1/learning-enrollments", json={"program_id": pid}, headers=auth_headers(user_a_token))

    resp = client.get("/api/v1/learning-enrollments/me?per_page=2&page=1", headers=auth_headers(user_a_token))
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 3
    assert body["meta"]["total_pages"] == 2


# ---------------------------------------------------------------------------
# Lesson completion
# ---------------------------------------------------------------------------


def test_mark_lesson_complete(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]["enrollment"]
    assert data["completed_lessons"] == 1
    assert data["total_lessons"] == 2
    assert data["completed_at"] is None


def test_duplicate_mark_complete_idempotent(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    resp = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrollment"]["completed_lessons"] == 1

    from app.models.learning_enrollment import LearningLessonProgress

    with app.app_context():
        assert LearningLessonProgress.query.filter_by(enrollment_id=enrollment.id, lesson_id=lesson_ids[0]).count() == 1


def test_mark_lesson_incomplete(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))

    resp = client.delete(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrollment"]["completed_lessons"] == 0

    # Idempotent: marking an already-incomplete lesson incomplete again is a no-op.
    resp2 = client.delete(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    assert resp2.status_code == 200
    assert resp2.get_json()["data"]["enrollment"]["completed_lessons"] == 0


def test_lesson_must_belong_to_enrollments_program(client, app, user_a_token):
    program_id, _ = _make_program(app, lesson_count=1)
    other_program_id, other_lessons = _make_program(app, lesson_count=1)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{other_lessons[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 403


def test_cannot_alter_other_users_progress(client, app, user_a_token, user_b_token):
    program_id, lesson_ids = _make_program(app, lesson_count=1)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_b_token)
    )
    assert resp.status_code == 404


def test_withdrawn_enrollment_cannot_update_progress(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=1)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_a_token))

    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "enrollment_withdrawn"


def test_archived_program_blocks_progress_update(client, app, user_a_token):
    from app.extensions import db
    from app.models.learning import LearningProgram

    program_id, lesson_ids = _make_program(app, lesson_count=1)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    with app.app_context():
        program = db.session.get(LearningProgram, program_id)
        program.status = "archived"
        db.session.commit()

    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "program_unavailable"


def test_zero_lesson_program_does_not_autocomplete(client, app, user_a_token):
    program_id, _ = _make_program(app, lesson_count=0)
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["enrollment"]["completed_at"] is None
    assert resp.get_json()["data"]["enrollment"]["total_lessons"] == 0


def test_completing_all_lessons_sets_completed_at(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    resp = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[1]}/complete", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]["enrollment"]
    assert data["completed_at"] is not None
    assert data["completed_lessons"] == 2
    assert data["progress_percent"] == 100


def test_marking_incomplete_clears_completion_when_no_longer_complete(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[1]}/complete", headers=auth_headers(user_a_token))

    resp = client.delete(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]["enrollment"]
    assert data["completed_at"] is None
    assert data["completed_lessons"] == 1


def test_progress_counts_accurate(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=3)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    resp = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]["enrollment"]
    assert data["completed_lessons"] == 1
    assert data["total_lessons"] == 3
    assert data["progress_percent"] == 33


# ---------------------------------------------------------------------------
# Curriculum-change interaction with enrollment/progress
# ---------------------------------------------------------------------------


def test_removed_lesson_progress_safely_removed(client, app, manager_token, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))

    # Replace curriculum entirely without referencing the old lesson ids.
    client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json=_base_curriculum_payload(),
        headers=auth_headers(manager_token),
    )

    from app.models.learning_enrollment import LearningLessonProgress

    with app.app_context():
        assert LearningLessonProgress.query.filter_by(enrollment_id=enrollment.id, lesson_id=lesson_ids[0]).first() is None


def test_unchanged_lesson_progress_survives_curriculum_edit(client, app, manager_token, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))

    # Re-submit the SAME two lessons by id (module id included), just with
    # one title tweaked — an in-place edit, not a replace.
    get_resp = client.get(f"/api/v1/learning/admin/programs/{program_id}", headers=auth_headers(manager_token))
    program = get_resp.get_json()["data"]
    module = program["modules"][0]
    payload = {
        "modules": [
            {
                "id": module["id"],
                "title": "Module 1 — renamed",
                "lessons": [
                    {"id": lesson_ids[0], "title": "Lesson 1 renamed", "lessonType": "text"},
                    {"id": lesson_ids[1], "title": "Lesson 2", "lessonType": "text"},
                ],
            }
        ]
    }
    resp = client.put(f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 200

    check = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    assert check.get_json()["data"]["enrollment"]["completed_lessons"] == 1


def test_later_curriculum_additions_do_not_revoke_earned_completion(client, app, manager_token, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=1)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    complete_resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert complete_resp.get_json()["data"]["enrollment"]["completed_at"] is not None

    # Editor adds a second lesson via the curriculum editor — the first
    # lesson's id is preserved (submitted back), a new lesson has no id.
    get_resp = client.get(f"/api/v1/learning/admin/programs/{program_id}", headers=auth_headers(manager_token))
    module = get_resp.get_json()["data"]["modules"][0]
    payload = {
        "modules": [
            {
                "id": module["id"],
                "title": module["title"],
                "lessons": [
                    {"id": lesson_ids[0], "title": "Lesson 1", "lessonType": "text"},
                    {"title": "Brand New Lesson", "lessonType": "text"},
                ],
            }
        ]
    }
    client.put(f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=payload, headers=auth_headers(manager_token))

    check = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    data = check.get_json()["data"]["enrollment"]
    assert data["completed_at"] is not None  # historical completion preserved
    assert data["total_lessons"] == 2  # but the denominator reflects the new curriculum
    assert data["completed_lessons"] == 1


def test_me_archived_program_hides_curriculum(client, app, user_a_token):
    from app.extensions import db
    from app.models.learning import LearningProgram

    program_id, _ = _make_program(app, lesson_count=2)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))

    with app.app_context():
        program = db.session.get(LearningProgram, program_id)
        program.status = "archived"
        db.session.commit()

    resp = client.get("/api/v1/learning-enrollments/me", headers=auth_headers(user_a_token))
    row = resp.get_json()["data"][0]
    assert row["program_available"] is False
    assert "modules" not in row["program"]


# ---------------------------------------------------------------------------
# Curriculum ID-preservation refactor
# ---------------------------------------------------------------------------


def test_module_id_stable_across_curriculum_edit(client, app, manager_token):
    program_id, _ = _make_program(app, lesson_count=0)
    create = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "Module A", "lessons": []}]},
        headers=auth_headers(manager_token),
    )
    module_id = create.get_json()["data"]["modules"][0]["id"]

    edit = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"id": module_id, "title": "Module A Renamed", "lessons": []}]},
        headers=auth_headers(manager_token),
    )
    assert edit.status_code == 200
    assert edit.get_json()["data"]["modules"][0]["id"] == module_id
    assert edit.get_json()["data"]["modules"][0]["title"] == "Module A Renamed"


def test_lesson_id_stable_across_curriculum_edit(client, app, manager_token):
    program_id, _ = _make_program(app, lesson_count=0)
    create = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "Module A", "lessons": [{"title": "Lesson A", "lessonType": "text"}]}]},
        headers=auth_headers(manager_token),
    )
    module = create.get_json()["data"]["modules"][0]
    lesson_id = module["lessons"][0]["id"]

    edit = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"id": module["id"], "title": "Module A", "lessons": [{"id": lesson_id, "title": "Lesson A Renamed", "lessonType": "text"}]}]},
        headers=auth_headers(manager_token),
    )
    assert edit.status_code == 200
    edited_lesson = edit.get_json()["data"]["modules"][0]["lessons"][0]
    assert edited_lesson["id"] == lesson_id
    assert edited_lesson["title"] == "Lesson A Renamed"


def test_new_curriculum_rows_receive_new_ids(client, app, manager_token):
    program_id, _ = _make_program(app, lesson_count=0)
    create = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "Module A", "lessons": [{"title": "Lesson A", "lessonType": "text"}]}]},
        headers=auth_headers(manager_token),
    )
    module = create.get_json()["data"]["modules"][0]

    edit = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={
            "modules": [
                {
                    "id": module["id"],
                    "title": "Module A",
                    "lessons": [
                        {"id": module["lessons"][0]["id"], "title": "Lesson A", "lessonType": "text"},
                        {"title": "Lesson B (new)", "lessonType": "text"},
                    ],
                }
            ]
        },
        headers=auth_headers(manager_token),
    )
    lessons = edit.get_json()["data"]["modules"][0]["lessons"]
    assert len(lessons) == 2
    assert lessons[0]["id"] == module["lessons"][0]["id"]
    assert lessons[1]["id"] != module["lessons"][0]["id"]
    assert lessons[1]["id"] is not None


def test_removed_curriculum_rows_are_deleted(client, app, manager_token):
    program_id, _ = _make_program(app, lesson_count=0)
    create = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={
            "modules": [
                {"title": "Module A", "lessons": [{"title": "Lesson A", "lessonType": "text"}, {"title": "Lesson B", "lessonType": "text"}]}
            ]
        },
        headers=auth_headers(manager_token),
    )
    module = create.get_json()["data"]["modules"][0]
    keep_lesson_id = module["lessons"][0]["id"]
    removed_lesson_id = module["lessons"][1]["id"]

    edit = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"id": module["id"], "title": "Module A", "lessons": [{"id": keep_lesson_id, "title": "Lesson A", "lessonType": "text"}]}]},
        headers=auth_headers(manager_token),
    )
    assert len(edit.get_json()["data"]["modules"][0]["lessons"]) == 1

    from app.models.learning import LearningLesson

    with app.app_context():
        assert LearningLesson.query.get(removed_lesson_id) is None
        assert LearningLesson.query.get(keep_lesson_id) is not None


def test_cross_program_module_id_rejected(client, app, manager_token):
    program_a, _ = _make_program(app, lesson_count=0)
    program_b, _ = _make_program(app, lesson_count=0)
    create = client.put(
        f"/api/v1/learning/admin/programs/{program_a}/curriculum",
        json={"modules": [{"title": "Module A", "lessons": []}]},
        headers=auth_headers(manager_token),
    )
    module_id = create.get_json()["data"]["modules"][0]["id"]

    resp = client.put(
        f"/api/v1/learning/admin/programs/{program_b}/curriculum",
        json={"modules": [{"id": module_id, "title": "Hijacked", "lessons": []}]},
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 404

    from app.models.learning import LearningModule

    with app.app_context():
        assert LearningModule.query.get(module_id).title == "Module A"  # untouched


def test_cross_program_lesson_id_rejected(client, app, manager_token):
    program_a, _ = _make_program(app, lesson_count=0)
    program_b, _ = _make_program(app, lesson_count=0)
    create_a = client.put(
        f"/api/v1/learning/admin/programs/{program_a}/curriculum",
        json={"modules": [{"title": "Module A", "lessons": [{"title": "Lesson A", "lessonType": "text"}]}]},
        headers=auth_headers(manager_token),
    )
    lesson_id = create_a.get_json()["data"]["modules"][0]["lessons"][0]["id"]

    create_b = client.put(
        f"/api/v1/learning/admin/programs/{program_b}/curriculum",
        json={"modules": [{"title": "Module B", "lessons": []}]},
        headers=auth_headers(manager_token),
    )
    module_b_id = create_b.get_json()["data"]["modules"][0]["id"]

    resp = client.put(
        f"/api/v1/learning/admin/programs/{program_b}/curriculum",
        json={"modules": [{"id": module_b_id, "title": "Module B", "lessons": [{"id": lesson_id, "title": "Hijacked", "lessonType": "text"}]}]},
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 404


def test_curriculum_edit_remains_atomic_on_validation_failure(client, app, manager_token):
    program_id, _ = _make_program(app, lesson_count=0)
    create = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "Original Title", "lessons": [{"title": "Lesson A", "lessonType": "text"}]}]},
        headers=auth_headers(manager_token),
    )
    module = create.get_json()["data"]["modules"][0]
    lesson_id = module["lessons"][0]["id"]

    bad_payload = {
        "modules": [
            {
                "id": module["id"],
                "title": "Attempted Rename",
                "lessons": [
                    {"id": lesson_id, "title": "Attempted Lesson Rename", "lessonType": "text"},
                    {"title": "Bad", "lessonType": "article", "articleSlug": "does-not-exist"},
                ],
            }
        ]
    }
    resp = client.put(f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=bad_payload, headers=auth_headers(manager_token))
    assert resp.status_code == 404

    from app.models.learning import LearningModule

    with app.app_context():
        reloaded = LearningModule.query.get(module["id"])
        assert reloaded.title == "Original Title"  # rolled back — nothing partially saved
        assert reloaded.lessons[0].title == "Lesson A"


def test_curriculum_edit_does_not_touch_article_or_resource(client, app, manager_token):
    from app.extensions import db
    from app.models.article import Article
    from app.models.people import Author

    program_id, _ = _make_program(app, lesson_count=0)  # ensures the shared instructor Author exists

    with app.app_context():
        author = Author.query.filter_by(slug="learnenroll-instructor").first()
        article = Article(slug=_slug("article"), title="An Article", author_id=author.id, status="published", content=[])
        db.session.add(article)
        db.session.commit()
        article_slug = article.slug

    client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "M1", "lessons": [{"title": "Read it", "lessonType": "article", "articleSlug": article_slug}]}]},
        headers=auth_headers(manager_token),
    )
    # Second edit drops the module entirely.
    client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": []},
        headers=auth_headers(manager_token),
    )

    with app.app_context():
        assert Article.query.filter_by(slug=article_slug).first() is not None


# ---------------------------------------------------------------------------
# Admin enrollment listing
# ---------------------------------------------------------------------------


def test_admin_can_list_enrollments(client, app, manager_token, user_a_token, user_b_token):
    program_id, lesson_ids = _make_program(app, lesson_count=1)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_b_token))

    resp = client.get(f"/api/v1/learning/admin/programs/{program_id}/enrollments", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    body = resp.get_json()["data"]
    assert len(body["items"]) == 2
    assert body["counts"]["current"] == 2
    emails = {row["learner_email"] for row in body["items"]}
    assert emails == {USER_A["email"], USER_B["email"]}


def test_unauthorized_staff_cannot_list_enrollments(client, app, no_permission_token):
    program_id, _ = _make_program(app)
    resp = client.get(f"/api/v1/learning/admin/programs/{program_id}/enrollments", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Privacy / independence from other modules
# ---------------------------------------------------------------------------


def test_public_learning_api_never_leaks_learner_data(client, app, user_a_token):
    program_id, _ = _make_program(app, lesson_count=1)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    slug = _get_program_slug(app, program_id)

    detail = client.get(f"/api/v1/learning/{slug}")
    body = detail.get_json()["data"]
    serialized = str(body)
    assert USER_A["email"] not in serialized
    assert "enrollment" not in serialized.lower()

    listing = client.get("/api/v1/learning")
    assert USER_A["email"] not in str(listing.get_json())


def test_saved_learning_independent_of_enrollment(client, app, user_a_token):
    program_id, _ = _make_program(app, lesson_count=1)
    save_resp = client.post(
        "/api/v1/saved", json={"content_type": "learning_program", "content_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert save_resp.status_code == 200
    assert _count_enrollments(app, program_id) == 0  # saving never enrolls

    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    saved_list = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    assert saved_list.get_json()["data"]["items"][0]["content_id"] == program_id  # still independently saved


def test_event_registration_independent_of_learning_enrollment(client, app, user_a_token):
    from datetime import date, timedelta

    from app.extensions import db
    from app.models.learning import LearningProgramEvent
    from app.models.opportunity import Event

    with app.app_context():
        event = Event(
            slug=_slug("linked-event"),
            title="Linked Event",
            date=date.today() + timedelta(days=10),
            status="published",
            registration_required=True,
            registration_mode="wsf",
            format="virtual",
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

    program_id, _ = _make_program(app, lesson_count=0)
    with app.app_context():
        db.session.add(LearningProgramEvent(learning_program_id=program_id, event_id=event_id, position=0))
        db.session.commit()

    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))

    from app.models.event_registration import EventRegistration

    with app.app_context():
        assert EventRegistration.query.filter_by(event_id=event_id).count() == 0


def test_email_failure_does_not_undo_enrollment(client, app, user_a_token, monkeypatch):
    import app.api.v1.learning_enrollments as mod

    monkeypatch.setattr(mod, "send_email", lambda **kwargs: False)
    program_id, _ = _make_program(app)
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrolled"] is True
    assert _count_enrollments(app, program_id) == 1


def test_duplicate_enroll_does_not_resend_email(client, app, user_a_token, monkeypatch):
    import app.api.v1.learning_enrollments as mod

    calls = []
    monkeypatch.setattr(mod, "send_email", lambda **kwargs: calls.append(1) or True)
    program_id, _ = _make_program(app)
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert len(calls) == 1
