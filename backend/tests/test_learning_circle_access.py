"""Focused tests for WSF Learning Access Tiers + WSF Circle Gating —
the new `circle_only` LearningProgram.access_type (free/circle_only/
external/product), the curriculum-leak fix (public outline vs full
curriculum), the central app/services/learning_access.py eligibility
rule, the protected curriculum endpoint
(GET /learning-enrollments/{id}/curriculum), and the Circle-gated
enrollment/progress rules in app/services/learning_enrollments.py.

Circle entitlement itself is never re-derived here — every "should this
grant access" assertion traces back to app/services/circle.py's
has_circle_access(), exactly as production code does.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

USER_A = {
    "email": "lcircle-user-a@example.com", "password": "supersecret1",
    "first_name": "Amina", "last_name": "Diallo", "country_code": "SN",
}
USER_B = {
    "email": "lcircle-user-b@example.com", "password": "supersecret1",
    "first_name": "Beatrice", "last_name": "Mwangi", "country_code": "KE",
}
MANAGER_PAYLOAD = {
    "email": "lcircle-manager@example.com", "password": "supersecret1",
    "first_name": "Amara", "last_name": "Nwosu", "country_code": "NG",
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


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _now():
    return datetime.now(timezone.utc)


def _instructor_id(app):
    from app.extensions import db
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="lcircle-instructor").first()
        if author is None:
            author = Author(slug="lcircle-instructor", name="Circle Learning Instructor", status="active")
            db.session.add(author)
            db.session.commit()
        return author.id


def _make_resource(app):
    from app.extensions import db
    from app.models.resource import Resource as ResourceModel

    with app.app_context():
        resource = ResourceModel(
            slug=_slug("resource"), name="A Guide", status="published", type="Guide",
            file_url="https://files.example.org/secret-guide.pdf",
        )
        db.session.add(resource)
        db.session.commit()
        return resource.id, resource.slug


def _make_program(app, lesson_count=2, with_resource_lesson=False, **overrides):
    """Direct-ORM program + one module with `lesson_count` lessons (plus,
    optionally, a trailing Resource-linked lesson) — bypasses the
    curriculum PUT endpoint for test setup speed. Returns
    (program_id, [lesson_id, ...]).
    """
    from app.extensions import db
    from app.models.learning import LearningLesson, LearningModule, LearningProgram

    instructor_id = _instructor_id(app)
    resource_id = None
    if with_resource_lesson:
        resource_id, _ = _make_resource(app)

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
        module = LearningModule(learning_program_id=program.id, title="Module 1", sort_order=0)
        db.session.add(module)
        db.session.flush()
        for i in range(lesson_count):
            lesson = LearningLesson(
                module_id=module.id, title=f"Lesson {i + 1}", lesson_type="text",
                content=[{"type": "paragraph", "text": "Secret lesson body."}],
                summary=f"Summary {i + 1}", duration_minutes=5, sort_order=i,
                external_url="https://video.example.org/secret" if i == 0 else None,
            )
            db.session.add(lesson)
            db.session.flush()
            lesson_ids.append(lesson.id)
        if with_resource_lesson:
            resource_lesson = LearningLesson(
                module_id=module.id, title="Resource Lesson", lesson_type="resource",
                resource_id=resource_id, content=[], sort_order=lesson_count,
            )
            db.session.add(resource_lesson)
            db.session.flush()
            lesson_ids.append(resource_lesson.id)
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


def _make_plan(app, **overrides):
    from app.extensions import db
    from app.models.circle import CirclePlan

    defaults = dict(
        slug=overrides.pop("slug", None) or f"plan-{uuid.uuid4().hex[:10]}",
        name="WSF Circle Membership", billing_interval="monthly", price=1000, currency="USD", status="active",
    )
    defaults.update(overrides)
    with app.app_context():
        plan = CirclePlan(**defaults)
        db.session.add(plan)
        db.session.commit()
        return plan.id


def _make_subscription(app, user_email, plan_id, **overrides):
    from app.extensions import db
    from app.models.circle import CircleSubscription
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=user_email).first()
        defaults = dict(user_id=user.id, plan_id=plan_id, status="active", source="manual")
        defaults.update(overrides)
        subscription = CircleSubscription(**defaults)
        db.session.add(subscription)
        db.session.commit()
        return subscription.id


def _give_active_circle(app, email):
    plan_id = _make_plan(app)
    return _make_subscription(app, email, plan_id, status="active")


def _expire_subscription(app, subscription_id):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        sub = db.session.get(CircleSubscription, subscription_id)
        sub.status = "expired"
        db.session.commit()


def _reactivate_subscription(app, subscription_id):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        sub = db.session.get(CircleSubscription, subscription_id)
        sub.status = "active"
        sub.current_period_end = None
        db.session.commit()


def _make_member(app, email, membership_type="Community Member"):
    from app.extensions import db
    from app.models.community import Member
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        member = Member(
            first_name=user.first_name, last_name=user.last_name, email=email,
            status="active", membership_type=membership_type, consent_given=True, user_id=user.id,
        )
        db.session.add(member)
        db.session.commit()
        return member.id


# ===========================================================================
# 1-5: Access type / migration logic
# ===========================================================================


def test_1_circle_only_accepted_as_access_type(app):
    program_id, _ = _make_program(app, lesson_count=0, access_type="circle_only")
    assert program_id is not None


def test_2_free_still_accepted(app):
    program_id, _ = _make_program(app, lesson_count=0, access_type="free")
    assert program_id is not None


def test_3_external_still_accepted(app):
    program_id, _ = _make_program(app, lesson_count=0, access_type="external", external_url="https://example.org/go")
    assert program_id is not None


def test_4_product_still_accepted(app):
    from app.extensions import db
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=_slug("product"), name="A Product", price=4900, currency="USD", status="active")
        db.session.add(product)
        db.session.commit()
        product_id = product.id
    program_id, _ = _make_program(app, lesson_count=0, access_type="product", product_id=product_id)
    assert program_id is not None


def test_5_unknown_access_type_rejected_by_db_constraint(app):
    from sqlalchemy.exc import IntegrityError

    from app.extensions import db
    from app.models.learning import LearningProgram

    with app.app_context():
        program = LearningProgram(
            slug=_slug("program"), title="Bad", overview=[], status="draft", access_type="premium_tier",
            primary_instructor_id=_instructor_id(app),
        )
        db.session.add(program)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ===========================================================================
# 6-18: Public serialization
# ===========================================================================


def test_6_free_public_detail_includes_full_lesson_content(client, app):
    program_id, _ = _make_program(app, lesson_count=1, access_type="free")
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    module = resp.get_json()["data"]["modules"][0]
    assert module["lessons"][0]["content"]


def test_7_circle_only_public_detail_outline_excludes_content(client, app):
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    module = resp.get_json()["data"]["modules"][0]
    assert "content" not in module["lessons"][0]


def test_8_circle_only_public_detail_excludes_external_url(client, app):
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    module = resp.get_json()["data"]["modules"][0]
    lesson = module["lessons"][0]
    assert "externalUrl" not in lesson and "external_url" not in lesson


def test_9_circle_only_public_detail_excludes_article_reference(client, app):
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    lesson = resp.get_json()["data"]["modules"][0]["lessons"][0]
    assert "article" not in lesson


def test_10_circle_only_public_detail_excludes_resource_reference(client, app):
    program_id, _ = _make_program(app, lesson_count=1, with_resource_lesson=True, access_type="circle_only")
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    lessons = resp.get_json()["data"]["modules"][0]["lessons"]
    assert all("resource" not in lesson for lesson in lessons)


def test_11_circle_only_public_detail_includes_safe_outline_fields(client, app):
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    module = resp.get_json()["data"]["modules"][0]
    lesson = module["lessons"][0]
    assert module["title"] == "Module 1"
    assert lesson["title"] == "Lesson 1"
    assert lesson["summary"] == "Summary 1"
    assert lesson["durationMinutes"] == 5
    assert lesson["sortOrder"] == 0


def test_12_external_public_detail_outline_only(client, app):
    program_id, _ = _make_program(app, lesson_count=1, access_type="external", external_url="https://example.org/go")
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    lesson = resp.get_json()["data"]["modules"][0]["lessons"][0]
    assert "content" not in lesson and "externalUrl" not in lesson


def test_13_product_public_detail_outline_only(client, app):
    from app.extensions import db
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=_slug("product"), name="A Product", price=4900, currency="USD", status="active")
        db.session.add(product)
        db.session.commit()
        product_id = product.id
    program_id, _ = _make_program(app, lesson_count=1, access_type="product", product_id=product_id)
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    lesson = resp.get_json()["data"]["modules"][0]["lessons"][0]
    assert "content" not in lesson


def test_14_public_detail_requires_circle_true_for_circle_only(client, app):
    program_id, _ = _make_program(app, lesson_count=0, access_type="circle_only")
    slug = _get_program_slug(app, program_id)
    body = client.get(f"/api/v1/learning/{slug}").get_json()["data"]
    assert body["requiresCircle"] is True


def test_15_public_detail_requires_circle_false_for_free(client, app):
    program_id, _ = _make_program(app, lesson_count=0, access_type="free")
    slug = _get_program_slug(app, program_id)
    body = client.get(f"/api/v1/learning/{slug}").get_json()["data"]
    assert body["requiresCircle"] is False


def test_16_public_list_never_leaks_circle_only_curriculum(client, app):
    _make_program(app, lesson_count=2, access_type="circle_only")
    listing = client.get("/api/v1/learning").get_json()["data"]
    assert all("modules" not in item for item in listing)


def test_17_viewer_can_access_true_for_anonymous_free(client, app):
    program_id, _ = _make_program(app, lesson_count=0, access_type="free")
    slug = _get_program_slug(app, program_id)
    body = client.get(f"/api/v1/learning/{slug}").get_json()["data"]
    assert body["viewerCanAccess"] is True


def test_18_viewer_can_access_false_for_anonymous_circle_only(client, app):
    program_id, _ = _make_program(app, lesson_count=0, access_type="circle_only")
    slug = _get_program_slug(app, program_id)
    body = client.get(f"/api/v1/learning/{slug}").get_json()["data"]
    assert body["viewerCanAccess"] is False


# ===========================================================================
# 19-22: Free regression
# ===========================================================================


def test_19_free_readable_anonymously(client, app):
    program_id, _ = _make_program(app, lesson_count=1, access_type="free")
    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["modules"][0]["lessons"][0]["content"]


def test_20_free_enroll_still_works(client, app, user_a_token):
    program_id, _ = _make_program(app, access_type="free")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrolled"] is True


def test_21_free_protected_curriculum_endpoint_works(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="free")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"][0]["lessons"][0]["content"]


def test_22_free_progress_tracking_unaffected(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="free")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrollment"]["completed_lessons"] == 1


# ===========================================================================
# 23-40: Circle enrollment
# ===========================================================================


def test_23_anonymous_cannot_enroll_circle_only(client, app):
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id})
    assert resp.status_code == 401


def test_24_enroll_circle_only_without_circle_denied(client, app, user_a_token):
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_25_community_member_without_circle_denied(client, app, user_a_token):
    _make_member(app, USER_A["email"], membership_type="Community Member")
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_26_premium_member_without_circle_denied(client, app, user_a_token):
    # Regression: Community "Premium Member" membership_type must NEVER
    # be mistaken for WSF Circle entitlement (spec section B).
    _make_member(app, USER_A["email"], membership_type="Premium Member")
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


@pytest.mark.parametrize("status", ["pending", "past_due", "cancelled", "expired", "revoked"])
def test_27_enroll_denied_for_nonactive_statuses(client, app, user_a_token, status):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status=status)
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_28_enroll_denied_future_starts_at(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status="active", starts_at=_now() + timedelta(days=5))
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_29_enroll_denied_expired_period_end(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status="active", current_period_end=_now() - timedelta(days=1))
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_30_enroll_allowed_active_subscription(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrolled"] is True


def test_31_enroll_allowed_cancel_at_period_end_future_end(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(
        app, USER_A["email"], plan_id, status="active", cancel_at_period_end=True,
        current_period_end=_now() + timedelta(days=10),
    )
    program_id, _ = _make_program(app, access_type="circle_only")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 200


def test_32_enroll_denied_creates_no_enrollment_row(client, app, user_a_token):
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert _count_enrollments(app, program_id) == 0


def test_33_enroll_denied_does_not_touch_member(client, app, user_a_token):
    member_id = _make_member(app, USER_A["email"], membership_type="Community Member")
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))

    from app.extensions import db
    from app.models.community import Member

    with app.app_context():
        member = db.session.get(Member, member_id)
        assert member.membership_type == "Community Member"
        assert member.status == "active"


def test_34_enroll_denied_does_not_create_product_or_order(client, app, user_a_token):
    from app.models.commerce import Order, Product

    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))

    with app.app_context():
        assert Order.query.count() == 0
        assert Product.query.filter(Product.name.ilike("%circle%")).count() == 0


def test_35_duplicate_circle_enroll_idempotent(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    first = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    second = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert first.get_json()["data"]["enrollment"]["id"] == second.get_json()["data"]["enrollment"]["id"]
    assert _count_enrollments(app, program_id) == 1


def test_36_withdrawn_circle_enrollment_resume_requires_current_access(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    resume_denied = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resume_denied.status_code == 403
    assert resume_denied.get_json()["error"]["code"] == "circle_required"

    _reactivate_subscription(app, sub_id)
    resume_allowed = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resume_allowed.status_code == 200
    assert resume_allowed.get_json()["data"]["enrollment"]["status"] == "active"


def test_37_enroll_denied_does_not_send_email(client, app, user_a_token, monkeypatch):
    import app.api.v1.learning_enrollments as mod

    calls = []
    monkeypatch.setattr(mod, "send_email", lambda **kwargs: calls.append(1) or True)
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert len(calls) == 0


def test_38_enroll_allowed_circle_only_sends_email(client, app, user_a_token, monkeypatch):
    import app.api.v1.learning_enrollments as mod

    calls = []
    monkeypatch.setattr(mod, "send_email", lambda **kwargs: calls.append(1) or True)
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert len(calls) == 1


def test_39_forced_password_change_blocks_circle_enrollment(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "password_change_required"


def test_40_circle_enroll_nonexistent_program_404(client, user_a_token):
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": 999999}, headers=auth_headers(user_a_token))
    assert resp.status_code == 404


# ===========================================================================
# 41-51: Circle curriculum (protected endpoint)
# ===========================================================================


def test_41_curriculum_active_circle_enrolled_succeeds(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    assert resp.status_code == 200


def test_42_curriculum_active_circle_not_enrolled_fails(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    # No enrollment row exists for this program/user — never owned.
    resp = client.get("/api/v1/learning-enrollments/999999/curriculum", headers=auth_headers(user_a_token))
    assert resp.status_code == 404


def test_43_curriculum_ordinary_account_fails(client, app, user_a_token, user_b_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    # user_b has no Circle access and no enrollment of their own.
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_b_token))
    assert resp.status_code == 404  # owner-scoped lookup — never leaks


def test_44_curriculum_another_user_fails_404(client, app, user_a_token, user_b_token):
    _give_active_circle(app, USER_A["email"])
    _give_active_circle(app, USER_B["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_b_token))
    assert resp.status_code == 404


def test_45_curriculum_expired_circle_loses_access(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    _expire_subscription(app, sub_id)
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_46_curriculum_enrollment_and_progress_remain_after_expiry(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=2, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))

    row = _get_enrollment_row(app, program_id, USER_A["email"])
    assert row.status == "active"

    from app.models.learning_enrollment import LearningLessonProgress

    with app.app_context():
        assert LearningLessonProgress.query.filter_by(enrollment_id=enrollment.id, lesson_id=lesson_ids[0]).count() == 1


def test_47_curriculum_renewed_circle_restores_access(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    _expire_subscription(app, sub_id)
    denied = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    assert denied.status_code == 403

    _reactivate_subscription(app, sub_id)
    restored = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    assert restored.status_code == 200


def test_48_curriculum_contains_lesson_content(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"][0]["lessons"][0]["content"]


def test_49_curriculum_contains_safe_article_resource_refs(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, with_resource_lesson=True, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    lessons = resp.get_json()["data"][0]["lessons"]
    resource_lesson = next(l for l in lessons if l["lesson_type"] == "resource")
    assert set(resource_lesson["resource"].keys()) == {"id", "slug", "name"}


def test_50_curriculum_does_not_expose_raw_resource_url(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, with_resource_lesson=True, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "secret-guide.pdf" not in serialized


def test_51_curriculum_withdrawn_enrollment_denied(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_a_token))

    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "enrollment_withdrawn"


# ===========================================================================
# 52-57: Progress authorization
# ===========================================================================


def test_52_circle_active_can_mark_complete(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrollment"]["completed_lessons"] == 1


def test_53_circle_expired_cannot_mark_complete(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    _expire_subscription(app, sub_id)
    resp = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_54_circle_expired_cannot_mark_incomplete(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    resp = client.delete(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_55_circle_denied_leaves_progress_unchanged(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=2, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[1]}/complete", headers=auth_headers(user_a_token))

    from app.models.learning_enrollment import LearningLessonProgress

    with app.app_context():
        assert LearningLessonProgress.query.filter_by(enrollment_id=enrollment.id).count() == 1


def test_56_circle_denied_leaves_completed_at_unchanged(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    completed_at_before = _get_enrollment_row(app, program_id, USER_A["email"]).completed_at

    _expire_subscription(app, sub_id)
    client.delete(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))

    completed_at_after = _get_enrollment_row(app, program_id, USER_A["email"]).completed_at
    assert completed_at_before == completed_at_after


def test_57_circle_restored_allows_progress_again(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    _expire_subscription(app, sub_id)
    denied = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    assert denied.status_code == 403

    _reactivate_subscription(app, sub_id)
    allowed = client.post(f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token))
    assert allowed.status_code == 200
    assert allowed.get_json()["data"]["enrollment"]["completed_lessons"] == 1


# ===========================================================================
# 58-61: Product / External
# ===========================================================================


def test_58_product_program_cannot_create_enrollment(client, app, user_a_token):
    from app.extensions import db
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=_slug("product"), name="A Product", price=4900, currency="USD", status="active")
        db.session.add(product)
        db.session.commit()
        product_id = product.id
    program_id, _ = _make_program(app, access_type="product", product_id=product_id)
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "product_enrollment"
    assert _count_enrollments(app, program_id) == 0


def test_59_circle_does_not_unlock_product(client, app, user_a_token):
    from app.extensions import db
    from app.models.commerce import Product

    _give_active_circle(app, USER_A["email"])
    with app.app_context():
        product = Product(slug=_slug("product"), name="A Product", price=4900, currency="USD", status="active")
        db.session.add(product)
        db.session.commit()
        product_id = product.id
    program_id, _ = _make_program(app, access_type="product", product_id=product_id)
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "product_enrollment"


def test_60_external_program_cannot_create_enrollment(client, app, user_a_token):
    program_id, _ = _make_program(app, access_type="external", external_url="https://example.org/enroll")
    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "external_enrollment"


def test_61_external_url_usable_and_safe(client, app):
    program_id, _ = _make_program(app, lesson_count=0, access_type="external", external_url="https://example.org/enroll")
    slug = _get_program_slug(app, program_id)
    body = client.get(f"/api/v1/learning/{slug}").get_json()["data"]
    assert body["external_url"] == "https://example.org/enroll"


# ===========================================================================
# 62-67: Owner payload
# ===========================================================================


def test_62_owner_payload_free_can_access_true(client, app, user_a_token):
    program_id, _ = _make_program(app, access_type="free")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    resp = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]["enrollment"]
    assert data["can_access_curriculum"] is True
    assert data["access_reason"] is None


def test_63_owner_payload_circle_active_true(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    resp = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]["enrollment"]
    assert data["can_access_curriculum"] is True
    assert data["access_reason"] is None


def test_64_owner_payload_circle_lapsed_false_with_reason(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    _expire_subscription(app, sub_id)

    resp = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]["enrollment"]
    assert data["can_access_curriculum"] is False
    assert data["access_reason"] == "circle_required"


def test_65_owner_payload_archived_program_false_with_reason(client, app, user_a_token):
    from app.extensions import db
    from app.models.learning import LearningProgram

    program_id, _ = _make_program(app, access_type="free")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    with app.app_context():
        program = db.session.get(LearningProgram, program_id)
        program.status = "archived"
        db.session.commit()

    resp = client.get("/api/v1/learning-enrollments/me", headers=auth_headers(user_a_token))
    row = resp.get_json()["data"][0]
    assert row["can_access_curriculum"] is False
    assert row["access_reason"] == "program_unavailable"


def test_66_owner_payload_withdrawn_false_with_reason(client, app, user_a_token):
    program_id, _ = _make_program(app, access_type="free")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    client.post(f"/api/v1/learning-enrollments/{enrollment.id}/withdraw", headers=auth_headers(user_a_token))

    resp = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]["enrollment"]
    assert data["can_access_curriculum"] is False
    assert data["access_reason"] == "enrollment_withdrawn"


def test_67_owner_payload_no_provider_metadata_leak(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    resp = client.get(f"/api/v1/learning-enrollments/check?program_id={program_id}", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "provider_customer_id" not in serialized
    assert "payment_reference" not in serialized


# ===========================================================================
# 68-70: My Learning / privacy
# ===========================================================================


def test_68_me_lapsed_circle_enrollment_still_appears(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    _expire_subscription(app, sub_id)

    resp = client.get("/api/v1/learning-enrollments/me", headers=auth_headers(user_a_token))
    rows = resp.get_json()["data"]
    assert len(rows) == 1
    assert rows[0]["status"] == "active"
    assert rows[0]["can_access_curriculum"] is False


def test_69_me_does_not_leak_curriculum_content(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))

    resp = client.get("/api/v1/learning-enrollments/me", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "Secret lesson body" not in serialized


def test_70_public_api_never_leaks_learner_identity_for_circle_only(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    slug = _get_program_slug(app, program_id)

    detail = client.get(f"/api/v1/learning/{slug}")
    serialized = str(detail.get_json())
    assert USER_A["email"] not in serialized
    assert "enrollment" not in serialized.lower()


# ===========================================================================
# 71-75: Regressions
# ===========================================================================


def test_71_saved_learning_independent_of_circle_enrollment(client, app, user_a_token):
    program_id, _ = _make_program(app, access_type="circle_only")
    save_resp = client.post(
        "/api/v1/saved", json={"content_type": "learning_program", "content_id": program_id}, headers=auth_headers(user_a_token)
    )
    assert save_resp.status_code == 200
    assert _count_enrollments(app, program_id) == 0  # saving never enrolls, never requires Circle


def test_72_event_registration_independent_of_learning_circle(client, app, user_a_token):
    from datetime import date

    from app.extensions import db
    from app.models.learning import LearningProgramEvent
    from app.models.opportunity import Event

    _give_active_circle(app, USER_A["email"])
    with app.app_context():
        event = Event(
            slug=_slug("linked-event"), title="Linked Event", date=date.today() + timedelta(days=10),
            status="published", registration_required=True, registration_mode="wsf", format="virtual",
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

    program_id, _ = _make_program(app, lesson_count=0, access_type="circle_only")
    with app.app_context():
        db.session.add(LearningProgramEvent(learning_program_id=program_id, event_id=event_id, position=0))
        db.session.commit()

    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))

    from app.models.event_registration import EventRegistration

    with app.app_context():
        assert EventRegistration.query.filter_by(event_id=event_id).count() == 0


def test_73_resource_access_authoritative_for_linked_lesson(client, app, user_a_token):
    # The Resource's own /resources/{slug}/access endpoint remains the one
    # authority for Resource entitlement — Learning never duplicates it,
    # it only ever surfaces the safe id/slug/name reference (spec P).
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=0, with_resource_lesson=True, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.get(f"/api/v1/learning-enrollments/{enrollment.id}/curriculum", headers=auth_headers(user_a_token))
    resource_ref = resp.get_json()["data"][0]["lessons"][0]["resource"]
    assert set(resource_ref.keys()) == {"id", "slug", "name"}


def test_74_curriculum_id_preservation_intact_for_circle_only(client, app, manager_token):
    # Lessons carry real text content so this still satisfies the
    # circle_only "needs meaningful content" publish guard re-checked on
    # every curriculum PUT to an already-published program (see
    # app/api/v1/learning.py's _is_meaningful_lesson) — this test is only
    # about ID preservation across edits, not content validation.
    program_id, _ = _make_program(app, lesson_count=0, access_type="circle_only")
    create = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={
            "modules": [
                {
                    "title": "Module A",
                    "lessons": [
                        {
                            "title": "Lesson A",
                            "lessonType": "text",
                            "content": [{"type": "paragraph", "text": "Real content."}],
                        }
                    ],
                }
            ]
        },
        headers=auth_headers(manager_token),
    )
    module = create.get_json()["data"]["modules"][0]
    lesson_id = module["lessons"][0]["id"]

    edit = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={
            "modules": [
                {
                    "id": module["id"],
                    "title": "Module A",
                    "lessons": [
                        {
                            "id": lesson_id,
                            "title": "Lesson A Renamed",
                            "lessonType": "text",
                            "content": [{"type": "paragraph", "text": "Real content."}],
                        }
                    ],
                }
            ]
        },
        headers=auth_headers(manager_token),
    )
    assert edit.get_json()["data"]["modules"][0]["id"] == module["id"]
    assert edit.get_json()["data"]["modules"][0]["lessons"][0]["id"] == lesson_id


def test_75_historical_completion_semantics_intact_for_circle_only(client, app, manager_token, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    complete_resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert complete_resp.get_json()["data"]["enrollment"]["completed_at"] is not None

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
    assert data["total_lessons"] == 2
    assert data["completed_lessons"] == 1


# ===========================================================================
# Follow-up fix: can_access_program_content() is the ONE Learning content-
# eligibility authority — learning_enrollments.py must never import/call
# has_circle_access() directly, and the same rule must deny progress
# mutation on a historical/invalid enrollment against an external/product
# program (not just circle_only).
# ===========================================================================


def _make_legacy_enrollment(app, program_id, email):
    """A deliberately invalid LearningEnrollment row against an external/
    product program — enroll() itself would never create one (it rejects
    both access types outright), but a historical/migrated row could
    still exist. _check_progress_allowed() must deny it regardless.
    """
    from app.extensions import db
    from app.models.learning_enrollment import LearningEnrollment
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        enrollment = LearningEnrollment(
            learning_program_id=program_id, user_id=user.id, status="active", enrolled_at=datetime.now(timezone.utc)
        )
        db.session.add(enrollment)
        db.session.commit()
        return enrollment.id


def test_76_learning_enrollments_module_does_not_import_has_circle_access():
    import app.services.learning_enrollments as mod

    assert not hasattr(mod, "has_circle_access")


def test_77_can_access_program_content_false_for_forced_password_change(client, app):
    from app.extensions import db
    from app.models.user import User
    from app.services.learning_access import can_access_program_content

    _register(client, USER_A)
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=0, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    with app.app_context():
        from app.models.learning import LearningProgram

        program = db.session.get(LearningProgram, program_id)
        user = User.query.filter_by(email=USER_A["email"]).first()
        assert can_access_program_content(program, user) is False


def test_78_public_circle_only_viewer_can_access_false_for_forced_password_change(client, app):
    from app.extensions import db
    from app.models.user import User

    user_a_token = _register(client, USER_A)
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, lesson_count=0, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    slug = _get_program_slug(app, program_id)
    resp = client.get(f"/api/v1/learning/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["viewerCanAccess"] is False


def test_79_circle_enroll_blocked_by_password_change_required(client, app):
    user_a_token = _register(client, USER_A)
    _give_active_circle(app, USER_A["email"])
    program_id, _ = _make_program(app, access_type="circle_only")

    from app.extensions import db
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    resp = client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "password_change_required"


def test_80_legacy_external_enrollment_mark_complete_denied(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="external", external_url="https://example.org/go")
    enrollment_id = _make_legacy_enrollment(app, program_id, USER_A["email"])

    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment_id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "access_denied"

    from app.models.learning_enrollment import LearningLessonProgress

    with app.app_context():
        assert LearningLessonProgress.query.filter_by(enrollment_id=enrollment_id).count() == 0


def test_81_legacy_product_enrollment_mark_complete_denied(client, app, user_a_token):
    from app.extensions import db
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=_slug("product"), name="A Product", price=4900, currency="USD", status="active")
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="product", product_id=product_id)
    enrollment_id = _make_legacy_enrollment(app, program_id, USER_A["email"])

    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment_id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "access_denied"

    from app.models.learning_enrollment import LearningLessonProgress

    with app.app_context():
        assert LearningLessonProgress.query.filter_by(enrollment_id=enrollment_id).count() == 0


def test_82_legacy_external_enrollment_mark_incomplete_denied_without_mutating_progress(client, app, user_a_token):
    from app.extensions import db
    from app.models.learning_enrollment import LearningLessonProgress

    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="external", external_url="https://example.org/go")
    enrollment_id = _make_legacy_enrollment(app, program_id, USER_A["email"])

    # Pre-seed a progress row directly (bypassing the API) so the test can
    # assert the denied incomplete-call leaves it completely untouched.
    with app.app_context():
        db.session.add(LearningLessonProgress(enrollment_id=enrollment_id, lesson_id=lesson_ids[0]))
        db.session.commit()

    resp = client.delete(
        f"/api/v1/learning-enrollments/{enrollment_id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "access_denied"

    with app.app_context():
        assert LearningLessonProgress.query.filter_by(enrollment_id=enrollment_id, lesson_id=lesson_ids[0]).count() == 1


def test_83_free_progress_still_works_after_fix(client, app, user_a_token):
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="free")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrollment"]["completed_lessons"] == 1


def test_84_valid_circle_progress_still_works_after_fix(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])
    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enrollment"]["completed_lessons"] == 1


def test_85_lapsed_circle_progress_still_returns_circle_required_after_fix(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    program_id, lesson_ids = _make_program(app, lesson_count=1, access_type="circle_only")
    client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(user_a_token))
    enrollment = _get_enrollment_row(app, program_id, USER_A["email"])

    _expire_subscription(app, sub_id)
    resp = client.post(
        f"/api/v1/learning-enrollments/{enrollment.id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"
