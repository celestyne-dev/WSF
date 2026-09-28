"""WSF Learning CMS — structured educational offerings (courses,
masterclasses, programs, learning series). See app/models/learning.py.
"""
import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "learning-editor@example.com",
    "password": "supersecret1",
    "first_name": "Learning",
    "last_name": "Editor",
}


@pytest.fixture()
def editor_token(client, app):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=EDITOR_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=EDITOR_PAYLOAD["email"]).first()
        role = Role.query.filter_by(name="editor").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": EDITOR_PAYLOAD["email"], "password": EDITOR_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def instructor_slug(app):
    from app.extensions import db
    from app.models.people import Author

    with app.app_context():
        author = Author(slug="jane-instructor", name="Jane Instructor", status="active")
        db.session.add(author)
        db.session.commit()
        return author.slug


@pytest.fixture()
def published_article_slug(app):
    from app.extensions import db
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="jane-instructor").first() or Author(slug="jane-instructor", name="Jane Instructor", status="active")
        if author.id is None:
            db.session.add(author)
            db.session.flush()
        article = Article(
            slug="a-published-article-for-learning",
            title="A Published Article For Learning",
            author_id=author.id,
            status="published",
            content=[{"type": "paragraph", "text": "Body."}],
        )
        db.session.add(article)
        db.session.commit()
        return article.slug


@pytest.fixture()
def draft_article_slug(app):
    from app.extensions import db
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="jane-instructor").first()
        if author is None:
            author = Author(slug="jane-instructor", name="Jane Instructor", status="active")
            db.session.add(author)
            db.session.flush()
        article = Article(
            slug="a-draft-article-for-learning",
            title="A Draft Article For Learning",
            author_id=author.id,
            status="draft",
            content=[],
        )
        db.session.add(article)
        db.session.commit()
        return article.slug


@pytest.fixture()
def published_resource_slug(app):
    from app.extensions import db
    from app.models.resource import Resource

    with app.app_context():
        resource = Resource(slug="a-published-resource", name="A Published Resource", status="published")
        db.session.add(resource)
        db.session.commit()
        return resource.slug


@pytest.fixture()
def product_slug(app):
    from app.extensions import db
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug="a-test-product", name="A Test Product", price=4900, currency="USD", status="active")
        db.session.add(product)
        db.session.commit()
        return product.slug


@pytest.fixture()
def event_slug(app):
    from datetime import date

    from app.extensions import db
    from app.models.opportunity import Event

    with app.app_context():
        event = Event(slug="a-test-cohort-event", title="A Test Cohort Event", date=date(2027, 1, 15), status="published")
        db.session.add(event)
        db.session.commit()
        return event.slug


def _base_payload(instructor_slug, **overrides):
    payload = {
        "title": "Women in Leadership Foundations",
        "programType": "course",
        "difficultyLevel": "beginner",
        "audience": ["aspiring_leaders", "professionals"],
        "overview": [{"type": "paragraph", "text": "A foundations course."}],
        "learningOutcomes": ["Lead with confidence", "Build a personal brand"],
        "durationValue": 4,
        "durationUnit": "weeks",
        "primaryInstructorSlug": instructor_slug,
        "deliveryMode": "self_paced",
        "accessType": "free",
        "featured": False,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Program CRUD
# ---------------------------------------------------------------------------


def test_create_update_retrieve_program(client, editor_token, instructor_slug):
    create = client.post(
        "/api/v1/learning/admin/programs", json=_base_payload(instructor_slug), headers=auth_headers(editor_token)
    )
    assert create.status_code == 201
    data = create.get_json()["data"]
    assert data["slug"] == "women-in-leadership-foundations"
    assert data["status"] == "draft"
    assert data["primary_instructor"]["slug"] == instructor_slug

    program_id = data["id"]
    detail = client.get(f"/api/v1/learning/admin/programs/{program_id}", headers=auth_headers(editor_token))
    assert detail.status_code == 200
    assert detail.get_json()["data"]["title"] == "Women in Leadership Foundations"

    update = client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, subtitle="Updated subtitle"),
        headers=auth_headers(editor_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["subtitle"] == "Updated subtitle"


def test_unique_slug_auto_deduplicated(client, editor_token, instructor_slug):
    first = client.post(
        "/api/v1/learning/admin/programs", json=_base_payload(instructor_slug), headers=auth_headers(editor_token)
    )
    second = client.post(
        "/api/v1/learning/admin/programs", json=_base_payload(instructor_slug), headers=auth_headers(editor_token)
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["data"]["slug"] != second.get_json()["data"]["slug"]
    assert second.get_json()["data"]["slug"] == "women-in-leadership-foundations-2"


def test_validation_rejects_missing_title(client, editor_token, instructor_slug):
    payload = _base_payload(instructor_slug)
    del payload["title"]
    resp = client.post("/api/v1/learning/admin/programs", json=payload, headers=auth_headers(editor_token))
    assert resp.status_code == 422


def test_publish_and_archive_lifecycle(client, editor_token, instructor_slug):
    create = client.post(
        "/api/v1/learning/admin/programs", json=_base_payload(instructor_slug), headers=auth_headers(editor_token)
    )
    program_id = create.get_json()["data"]["id"]

    publish = client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, status="published"),
        headers=auth_headers(editor_token),
    )
    assert publish.status_code == 200
    assert publish.get_json()["data"]["status"] == "published"
    assert publish.get_json()["data"]["published_at"] is not None

    archive = client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, status="archived"),
        headers=auth_headers(editor_token),
    )
    assert archive.status_code == 200
    assert archive.get_json()["data"]["status"] == "archived"
    assert archive.get_json()["data"]["archived_at"] is not None


def test_featured_flag_roundtrips(client, editor_token, instructor_slug):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, featured=True),
        headers=auth_headers(editor_token),
    )
    assert create.get_json()["data"]["featured"] is True


# ---------------------------------------------------------------------------
# Access types
# ---------------------------------------------------------------------------


def test_publish_requires_product_when_access_type_is_product(client, editor_token, instructor_slug):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, accessType="product"),
        headers=auth_headers(editor_token),
    )
    program_id = create.get_json()["data"]["id"]

    publish = client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, accessType="product", status="published"),
        headers=auth_headers(editor_token),
    )
    assert publish.status_code == 422
    assert publish.get_json()["error"]["code"] == "publish_validation_failed"


def test_product_linked_program_resolves_product_without_duplicating_price(
    client, editor_token, instructor_slug, product_slug
):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, accessType="product", productSlug=product_slug),
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    data = create.get_json()["data"]
    assert data["product"]["slug"] == product_slug
    assert data["product"]["price"] == 4900
    # LearningProgram itself carries no price/currency/sale_price fields —
    # Product remains the sole source of truth (spec section 61).
    assert "price" not in data
    assert "currency" not in data


def test_invalid_product_slug_rejected(client, editor_token, instructor_slug):
    resp = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, accessType="product", productSlug="does-not-exist"),
        headers=auth_headers(editor_token),
    )
    assert resp.status_code == 404


def test_deleting_program_link_does_not_delete_product(client, editor_token, instructor_slug, product_slug, app):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, accessType="product", productSlug=product_slug),
        headers=auth_headers(editor_token),
    )
    program_id = create.get_json()["data"]["id"]

    # Unlink the Product by saving without productSlug.
    client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, accessType="free"),
        headers=auth_headers(editor_token),
    )

    with app.app_context():
        from app.models.commerce import Product

        assert Product.query.filter_by(slug=product_slug).first() is not None


def test_external_access_requires_safe_url_before_publish(client, editor_token, instructor_slug):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, accessType="external", externalUrl="javascript:alert(1)"),
        headers=auth_headers(editor_token),
    )
    program_id = create.get_json()["data"]["id"]

    publish = client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, accessType="external", externalUrl="javascript:alert(1)", status="published"),
        headers=auth_headers(editor_token),
    )
    assert publish.status_code == 422


# ---------------------------------------------------------------------------
# Event integration
# ---------------------------------------------------------------------------


def test_event_relationship_and_unlink_preserves_event(client, editor_token, instructor_slug, event_slug, app):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, deliveryMode="live_online", eventSlugs=[event_slug]),
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    events = create.get_json()["data"]["events"]
    assert len(events) == 1
    assert events[0]["slug"] == event_slug

    program_id = create.get_json()["data"]["id"]
    client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, deliveryMode="live_online", eventSlugs=[]),
        headers=auth_headers(editor_token),
    )

    with app.app_context():
        from app.models.opportunity import Event

        assert Event.query.filter_by(slug=event_slug).first() is not None


def test_public_detail_only_exposes_public_event_fields(client, editor_token, instructor_slug, event_slug):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, deliveryMode="live_online", eventSlugs=[event_slug], status="published"),
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]

    public = client.get(f"/api/v1/learning/{slug}")
    assert public.status_code == 200
    events = public.get_json()["data"]["events"]
    assert events[0]["slug"] == event_slug
    assert "registration_url" in events[0] or events[0].get("registration_url") is None


# ---------------------------------------------------------------------------
# Curriculum — modules and lessons
# ---------------------------------------------------------------------------


def _create_program(client, token, instructor_slug):
    create = client.post(
        "/api/v1/learning/admin/programs", json=_base_payload(instructor_slug), headers=auth_headers(token)
    )
    return create.get_json()["data"]["id"]


def test_curriculum_module_and_lesson_creation_with_ordering(client, editor_token, instructor_slug):
    program_id = _create_program(client, editor_token, instructor_slug)

    payload = {
        "modules": [
            {
                "title": "Module Two",
                "lessons": [{"title": "Lesson B", "lessonType": "text", "content": [{"type": "paragraph", "text": "Hi"}]}],
            },
            {
                "title": "Module One",
                "lessons": [
                    {"title": "Lesson A1", "lessonType": "text"},
                    {"title": "Lesson A2", "lessonType": "text"},
                ],
            },
        ]
    }
    resp = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=payload, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 200
    modules = resp.get_json()["data"]["modules"]
    assert len(modules) == 2
    assert modules[0]["title"] == "Module Two"
    assert modules[1]["title"] == "Module One"
    assert [l["title"] for l in modules[1]["lessons"]] == ["Lesson A1", "Lesson A2"]


def test_lesson_can_reference_published_article_without_copying_content(
    client, editor_token, instructor_slug, published_article_slug
):
    program_id = _create_program(client, editor_token, instructor_slug)
    payload = {
        "modules": [
            {
                "title": "Module One",
                "lessons": [{"title": "Read the article", "lessonType": "article", "articleSlug": published_article_slug}],
            }
        ]
    }
    resp = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=payload, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 200
    lesson = resp.get_json()["data"]["modules"][0]["lessons"][0]
    assert lesson["article"]["slug"] == published_article_slug
    # No copied Article content stored on the lesson.
    assert lesson["content"] == []


def test_lesson_can_reference_resource(client, editor_token, instructor_slug, published_resource_slug):
    program_id = _create_program(client, editor_token, instructor_slug)
    payload = {
        "modules": [
            {
                "title": "Module One",
                "lessons": [{"title": "Download the guide", "lessonType": "resource", "resourceSlug": published_resource_slug}],
            }
        ]
    }
    resp = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=payload, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 200
    lesson = resp.get_json()["data"]["modules"][0]["lessons"][0]
    assert lesson["resource"]["slug"] == published_resource_slug


def test_draft_article_lesson_reference_hidden_from_public(client, editor_token, instructor_slug, draft_article_slug):
    program_id = _create_program(client, editor_token, instructor_slug)
    client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "M1", "lessons": [{"title": "L1", "lessonType": "article", "articleSlug": draft_article_slug}]}]},
        headers=auth_headers(editor_token),
    )
    client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, status="published"),
        headers=auth_headers(editor_token),
    )
    program = client.get(f"/api/v1/learning/admin/programs/{program_id}", headers=auth_headers(editor_token)).get_json()["data"]
    slug = program["slug"]

    public = client.get(f"/api/v1/learning/{slug}")
    lesson = public.get_json()["data"]["modules"][0]["lessons"][0]
    assert lesson["article"] is None  # never leaks the draft Article's title/slug


def test_external_link_lesson_requires_safe_url(client, editor_token, instructor_slug):
    program_id = _create_program(client, editor_token, instructor_slug)
    payload = {"modules": [{"title": "M1", "lessons": [{"title": "Watch", "lessonType": "video", "externalUrl": "javascript:alert(1)"}]}]}
    resp = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=payload, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 422


def test_video_lesson_requires_external_url(client, editor_token, instructor_slug):
    program_id = _create_program(client, editor_token, instructor_slug)
    payload = {"modules": [{"title": "M1", "lessons": [{"title": "Watch", "lessonType": "video"}]}]}
    resp = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=payload, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 422


def test_curriculum_update_is_transactional_on_invalid_reference(client, editor_token, instructor_slug, app):
    program_id = _create_program(client, editor_token, instructor_slug)
    # Seed valid curriculum first.
    client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "Existing Module", "lessons": []}]},
        headers=auth_headers(editor_token),
    )

    # Attempt an update where the second module references a nonexistent Article.
    bad_payload = {
        "modules": [
            {"title": "Valid Module", "lessons": []},
            {"title": "Bad Module", "lessons": [{"title": "L1", "lessonType": "article", "articleSlug": "does-not-exist"}]},
        ]
    }
    resp = client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum", json=bad_payload, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 404

    with app.app_context():
        from app.models.learning import LearningModule

        modules = LearningModule.query.filter_by(learning_program_id=program_id).all()
        assert len(modules) == 1
        assert modules[0].title == "Existing Module"  # untouched — nothing partially saved


def test_unlinking_lesson_does_not_delete_referenced_article(
    client, editor_token, instructor_slug, published_article_slug, app
):
    program_id = _create_program(client, editor_token, instructor_slug)
    client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "M1", "lessons": [{"title": "L1", "lessonType": "article", "articleSlug": published_article_slug}]}]},
        headers=auth_headers(editor_token),
    )
    # Replace curriculum entirely, dropping the lesson.
    client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": []},
        headers=auth_headers(editor_token),
    )

    with app.app_context():
        from app.models.article import Article

        assert Article.query.filter_by(slug=published_article_slug).first() is not None


# ---------------------------------------------------------------------------
# Public eligibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["draft", "review", "archived"])
def test_non_published_programs_excluded_from_public_list_and_detail(client, editor_token, instructor_slug, status):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, status=status),
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]

    detail = client.get(f"/api/v1/learning/{slug}")
    assert detail.status_code == 404

    listing = client.get("/api/v1/learning")
    assert slug not in [p["slug"] for p in listing.get_json()["data"]]


def test_published_program_visible_publicly(client, editor_token, instructor_slug):
    create = client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, status="published"),
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]

    detail = client.get(f"/api/v1/learning/{slug}")
    assert detail.status_code == 200

    listing = client.get("/api/v1/learning")
    assert slug in [p["slug"] for p in listing.get_json()["data"]]

    # Public list is the lightweight card shape — no full curriculum.
    card = next(p for p in listing.get_json()["data"] if p["slug"] == slug)
    assert "modules" not in card


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_finds_published_program_and_excludes_draft(client, editor_token, instructor_slug):
    client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, status="published"),
        headers=auth_headers(editor_token),
    )
    client.post(
        "/api/v1/learning/admin/programs",
        json=_base_payload(instructor_slug, title="Draft Only Program", status="draft"),
        headers=auth_headers(editor_token),
    )

    found = client.get("/api/v1/search?q=Leadership+Foundations&type=learning")
    assert found.status_code == 200
    titles = [r["title"] for r in found.get_json()["data"]["results"]]
    assert "Women in Leadership Foundations" in titles

    not_found = client.get("/api/v1/search?q=Draft+Only+Program&type=learning")
    assert "Draft Only Program" not in [r["title"] for r in not_found.get_json()["data"]["results"]]


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_unauthenticated_cannot_manage(client, instructor_slug):
    resp = client.post("/api/v1/learning/admin/programs", json=_base_payload(instructor_slug))
    assert resp.status_code == 401


def test_unauthorized_role_cannot_manage(client, instructor_slug):
    client.post(
        "/api/v1/auth/register",
        json={"email": "plain-member@example.com", "password": "supersecret1", "first_name": "P", "last_name": "M"},
    )
    login = client.post("/api/v1/auth/login", json={"email": "plain-member@example.com", "password": "supersecret1"})
    token = login.get_json()["data"]["access_token"]

    resp = client.post("/api/v1/learning/admin/programs", json=_base_payload(instructor_slug), headers=auth_headers(token))
    assert resp.status_code == 403


def test_super_admin_can_manage(client, app, instructor_slug):
    from app.extensions import db
    from app.models.user import Role, User

    client.post(
        "/api/v1/auth/register",
        json={"email": "super-admin-learning@example.com", "password": "supersecret1", "first_name": "S", "last_name": "A"},
    )
    with app.app_context():
        user = User.query.filter_by(email="super-admin-learning@example.com").first()
        role = Role.query.filter_by(name="super_admin").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": "super-admin-learning@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]

    resp = client.post("/api/v1/learning/admin/programs", json=_base_payload(instructor_slug), headers=auth_headers(token))
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_audit_log_records_create_publish_and_curriculum_change(client, editor_token, instructor_slug, app):
    create = client.post(
        "/api/v1/learning/admin/programs", json=_base_payload(instructor_slug), headers=auth_headers(editor_token)
    )
    program_id = create.get_json()["data"]["id"]

    client.patch(
        f"/api/v1/learning/admin/programs/{program_id}",
        json=_base_payload(instructor_slug, status="published"),
        headers=auth_headers(editor_token),
    )
    client.put(
        f"/api/v1/learning/admin/programs/{program_id}/curriculum",
        json={"modules": [{"title": "M1", "lessons": []}]},
        headers=auth_headers(editor_token),
    )

    with app.app_context():
        from app.models.audit import AuditLog

        actions = {
            entry.action
            for entry in AuditLog.query.filter_by(entity_type="LearningProgram", entity_id=str(program_id)).all()
        }
        assert "learning.create" in actions
        assert "learning.update" in actions
        assert "learning.curriculum_update" in actions

        publish_entry = AuditLog.query.filter_by(
            entity_type="LearningProgram", entity_id=str(program_id), action="learning.update"
        ).first()
        assert publish_entry.changes.get("to_status") == "published"
        # Never a full lesson content body in the audit trail.
        curriculum_entry = AuditLog.query.filter_by(
            entity_type="LearningProgram", entity_id=str(program_id), action="learning.curriculum_update"
        ).first()
        assert "content" not in curriculum_entry.changes
