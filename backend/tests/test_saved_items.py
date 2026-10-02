"""Focused tests for the private "save for later" feature — see
app/models/saved_item.py, app/services/saved_items.py, and
app/api/v1/saved.py.

Content fixtures are inserted directly via the ORM (rather than through
each content type's own admin-create API) since the Saved feature's own
correctness never depends on how a row got into the database — only on
its current status/visibility, which these fixtures control directly and
exactly.
"""
import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import auth_headers

USER_A = {
    "email": "saved-user-a@example.com",
    "password": "supersecret1",
    "first_name": "Amina",
    "last_name": "Diallo",
    "country_code": "SN",
}

USER_B = {
    "email": "saved-user-b@example.com",
    "password": "supersecret1",
    "first_name": "Beatrice",
    "last_name": "Mwangi",
    "country_code": "KE",
}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def user_a_token(client):
    return _register(client, USER_A)


@pytest.fixture()
def user_b_token(client):
    return _register(client, USER_B)


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _make_article(app, status="published"):
    from app.extensions import db
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author(slug=_slug("author"), name="Test Author")
        db.session.add(author)
        db.session.flush()
        article = Article(
            slug=_slug("article"),
            title="Test Article",
            author_id=author.id,
            status=status,
            content=[{"type": "paragraph", "text": "Hello world"}],
        )
        db.session.add(article)
        db.session.commit()
        return article.id


def _make_job(app, status="published", **overrides):
    from app.extensions import db
    from app.models.opportunity import Job

    with app.app_context():
        job = Job(slug=_slug("job"), title="Test Job", company_name="Test Co", status=status)
        for key, value in overrides.items():
            setattr(job, key, value)
        db.session.add(job)
        db.session.commit()
        return job.id


def _make_opportunity(app, status="published"):
    from app.extensions import db
    from app.models.opportunity import Opportunity

    with app.app_context():
        opportunity = Opportunity(slug=_slug("opportunity"), title="Test Opportunity", status=status)
        db.session.add(opportunity)
        db.session.commit()
        return opportunity.id


def _make_event(app, status="published", **overrides):
    from app.extensions import db
    from app.models.opportunity import Event

    with app.app_context():
        event = Event(slug=_slug("event"), title="Test Event", status=status, date=date.today())
        for key, value in overrides.items():
            setattr(event, key, value)
        db.session.add(event)
        db.session.commit()
        return event.id


def _make_resource(app, status="published", **overrides):
    from app.extensions import db
    from app.models.resource import Resource

    with app.app_context():
        resource = Resource(slug=_slug("resource"), name="Test Resource", status=status)
        for key, value in overrides.items():
            setattr(resource, key, value)
        db.session.add(resource)
        db.session.commit()
        return resource.id


def _make_learning_program(app, status="published"):
    from app.extensions import db
    from app.models.learning import LearningProgram

    with app.app_context():
        program = LearningProgram(slug=_slug("learning"), title="Test Program", status=status)
        db.session.add(program)
        db.session.commit()
        return program.id


def _set_status(app, model_name, content_id, status):
    """Flips an existing row's status directly — used to simulate content
    that was public when saved and later became non-public.
    """
    from app.extensions import db

    models = {
        "article": "app.models.article.Article",
        "job": "app.models.opportunity.Job",
        "opportunity": "app.models.opportunity.Opportunity",
        "event": "app.models.opportunity.Event",
        "resource": "app.models.resource.Resource",
        "learning_program": "app.models.learning.LearningProgram",
    }
    module_path, class_name = models[model_name].rsplit(".", 1)
    import importlib

    model_cls = getattr(importlib.import_module(module_path), class_name)
    with app.app_context():
        row = db.session.get(model_cls, content_id)
        row.status = status
        db.session.commit()


def _delete_row(app, model_name, content_id):
    from app.extensions import db

    models = {
        "job": "app.models.opportunity.Job",
    }
    module_path, class_name = models[model_name].rsplit(".", 1)
    import importlib

    model_cls = getattr(importlib.import_module(module_path), class_name)
    with app.app_context():
        row = db.session.get(model_cls, content_id)
        db.session.delete(row)
        db.session.commit()


# ---------------------------------------------------------------------------
# Authentication / authorization
# ---------------------------------------------------------------------------


def test_unauthenticated_cannot_save(client, app):
    article_id = _make_article(app)
    resp = client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id})
    assert resp.status_code == 401


def test_unauthenticated_cannot_list_saved(client):
    resp = client.get("/api/v1/saved")
    assert resp.status_code == 401


def test_forced_password_change_blocks_saving(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    article_id = _make_article(app)
    resp = client.post(
        "/api/v1/saved",
        json={"content_type": "article", "content_id": article_id},
        headers=auth_headers(user_a_token),
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "password_change_required"


def test_community_membership_not_required_to_save(client, app, user_a_token):
    from app.models.community import Member

    with app.app_context():
        assert Member.query.count() == 0

    article_id = _make_article(app)
    resp = client.post(
        "/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["saved"] is True


# ---------------------------------------------------------------------------
# Save / unsave happy paths for each content type
# ---------------------------------------------------------------------------


def test_save_and_unsave_published_article(client, app, user_a_token):
    article_id = _make_article(app, status="published")
    headers = auth_headers(user_a_token)

    save_resp = client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)
    assert save_resp.status_code == 200
    assert save_resp.get_json()["data"]["saved"] is True

    check_resp = client.get(f"/api/v1/saved/check?content_type=article&content_id={article_id}", headers=headers)
    assert check_resp.get_json()["data"]["saved"] is True

    delete_resp = client.delete(f"/api/v1/saved/article/{article_id}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()["data"]["saved"] is False

    check_again = client.get(f"/api/v1/saved/check?content_type=article&content_id={article_id}", headers=headers)
    assert check_again.get_json()["data"]["saved"] is False


@pytest.mark.parametrize(
    "content_type,factory",
    [
        ("job", _make_job),
        ("opportunity", _make_opportunity),
        ("resource", _make_resource),
        ("event", _make_event),
        ("learning_program", _make_learning_program),
    ],
)
def test_save_each_supported_content_type(client, app, user_a_token, content_type, factory):
    content_id = factory(app, status="published")
    headers = auth_headers(user_a_token)

    resp = client.post("/api/v1/saved", json={"content_type": content_type, "content_id": content_id}, headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["saved"] is True

    list_resp = client.get("/api/v1/saved", headers=headers)
    items = list_resp.get_json()["data"]["items"]
    assert any(item["content_type"] == content_type and item["content_id"] == content_id for item in items)


# ---------------------------------------------------------------------------
# Idempotency / uniqueness
# ---------------------------------------------------------------------------


def test_duplicate_save_is_idempotent_and_unique(client, app, user_a_token):
    article_id = _make_article(app)
    headers = auth_headers(user_a_token)

    first = client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)
    second = client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)
    assert first.get_json()["data"]["saved"] is True
    assert second.get_json()["data"]["saved"] is True

    from app.extensions import db
    from app.models.saved_item import SavedItem

    with app.app_context():
        count = SavedItem.query.filter_by(content_type="article", content_id=article_id).count()
        assert count == 1


def test_delete_is_idempotent(client, app, user_a_token):
    article_id = _make_article(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)

    first_delete = client.delete(f"/api/v1/saved/article/{article_id}", headers=headers)
    second_delete = client.delete(f"/api/v1/saved/article/{article_id}", headers=headers)
    assert first_delete.status_code == 200
    assert second_delete.status_code == 200
    assert first_delete.get_json()["data"]["saved"] is False
    assert second_delete.get_json()["data"]["saved"] is False


def test_delete_of_never_saved_item_is_harmless(client, user_a_token):
    resp = client.delete("/api/v1/saved/article/999999", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["saved"] is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_unsupported_content_type_rejected(client, user_a_token):
    resp = client.post(
        "/api/v1/saved", json={"content_type": "video", "content_id": 1}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("bad_content_id", [-1, 0, "not-a-number", None])
def test_invalid_content_id_rejected(client, user_a_token, bad_content_id):
    resp = client.post(
        "/api/v1/saved",
        json={"content_type": "article", "content_id": bad_content_id},
        headers=auth_headers(user_a_token),
    )
    assert resp.status_code == 422


def test_nonexistent_entity_cannot_be_saved(client, user_a_token):
    resp = client.post(
        "/api/v1/saved", json={"content_type": "article", "content_id": 999999}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 404


def test_draft_article_cannot_be_saved(client, app, user_a_token):
    article_id = _make_article(app, status="draft")
    resp = client.post(
        "/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 404


def test_archived_resource_cannot_be_saved(client, app, user_a_token):
    resource_id = _make_resource(app, status="archived")
    resp = client.post(
        "/api/v1/saved", json={"content_type": "resource", "content_id": resource_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 404


def test_closed_opportunity_cannot_be_saved(client, app, user_a_token):
    opportunity_id = _make_opportunity(app, status="closed")
    resp = client.post(
        "/api/v1/saved",
        json={"content_type": "opportunity", "content_id": opportunity_id},
        headers=auth_headers(user_a_token),
    )
    assert resp.status_code == 404


def test_scheduled_job_with_future_date_cannot_be_saved(client, app, user_a_token):
    job_id = _make_job(app, status="scheduled", published_date=date.today() + timedelta(days=10))
    resp = client.post(
        "/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 404


def test_cancelled_event_can_still_be_saved(client, app, user_a_token):
    event_id = _make_event(app, status="cancelled")
    resp = client.post(
        "/api/v1/saved", json={"content_type": "event", "content_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["saved"] is True


# ---------------------------------------------------------------------------
# Per-user isolation
# ---------------------------------------------------------------------------


def test_user_b_cannot_affect_user_a_saved_row(client, app, user_a_token, user_b_token):
    article_id = _make_article(app)
    client.post(
        "/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=auth_headers(user_a_token)
    )

    # User B deletes the same pointer — only ever scoped to their own rows,
    # so this must not touch user A's saved row.
    client.delete(f"/api/v1/saved/article/{article_id}", headers=auth_headers(user_b_token))

    check_a = client.get(
        f"/api/v1/saved/check?content_type=article&content_id={article_id}", headers=auth_headers(user_a_token)
    )
    assert check_a.get_json()["data"]["saved"] is True


def test_check_endpoint_reflects_only_current_user(client, app, user_a_token, user_b_token):
    article_id = _make_article(app)
    client.post(
        "/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=auth_headers(user_a_token)
    )

    check_b = client.get(
        f"/api/v1/saved/check?content_type=article&content_id={article_id}", headers=auth_headers(user_b_token)
    )
    assert check_b.get_json()["data"]["saved"] is False


def test_saved_list_never_returns_another_users_items(client, app, user_a_token, user_b_token):
    article_a = _make_article(app)
    article_b = _make_article(app)
    client.post(
        "/api/v1/saved", json={"content_type": "article", "content_id": article_a}, headers=auth_headers(user_a_token)
    )
    client.post(
        "/api/v1/saved", json={"content_type": "article", "content_id": article_b}, headers=auth_headers(user_b_token)
    )

    list_a = client.get("/api/v1/saved", headers=auth_headers(user_a_token)).get_json()["data"]["items"]
    assert [item["content_id"] for item in list_a] == [article_a]


# ---------------------------------------------------------------------------
# Serialization safety
# ---------------------------------------------------------------------------


def test_article_serialization_exposes_only_public_fields(client, app, user_a_token):
    article_id = _make_article(app)
    client.post(
        "/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=auth_headers(user_a_token)
    )

    list_resp = client.get("/api/v1/saved?type=article", headers=auth_headers(user_a_token))
    items = list_resp.get_json()["data"]["items"]
    assert len(items) == 1
    content = items[0]["content"]
    assert "content" not in content
    assert "ai_editorial_notes" not in content


def test_saved_content_that_becomes_non_public_is_omitted_from_list(client, app, user_a_token):
    article_id = _make_article(app, status="published")
    headers = auth_headers(user_a_token)
    client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)

    _set_status(app, "article", article_id, "draft")

    list_resp = client.get("/api/v1/saved", headers=headers)
    items = list_resp.get_json()["data"]["items"]
    assert all(item["content_id"] != article_id for item in items)


def test_stale_deleted_polymorphic_item_does_not_crash_listing(client, app, user_a_token):
    job_id = _make_job(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=headers)

    _delete_row(app, "job", job_id)

    list_resp = client.get("/api/v1/saved", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.get_json()["data"]["items"]
    assert all(item["content_id"] != job_id for item in items)


# ---------------------------------------------------------------------------
# Listing: filtering, pagination, ordering, counts
# ---------------------------------------------------------------------------


def test_filtering_by_type(client, app, user_a_token):
    article_id = _make_article(app)
    job_id = _make_job(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=headers)

    resp = client.get("/api/v1/saved?type=job", headers=headers)
    items = resp.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["content_type"] == "job"


def test_newest_saved_item_appears_first(client, app, user_a_token):
    article_id = _make_article(app)
    job_id = _make_job(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=headers)

    items = client.get("/api/v1/saved", headers=headers).get_json()["data"]["items"]
    assert items[0]["content_type"] == "job"
    assert items[1]["content_type"] == "article"


def test_pagination(client, app, user_a_token):
    headers = auth_headers(user_a_token)
    article_ids = [_make_article(app) for _ in range(3)]
    for article_id in article_ids:
        client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)

    resp = client.get("/api/v1/saved?per_page=2&page=1", headers=headers)
    body = resp.get_json()["data"]
    assert len(body["items"]) == 2
    assert body["pagination"]["total"] == 3
    assert body["pagination"]["total_pages"] == 2


def test_counts_by_type(client, app, user_a_token):
    headers = auth_headers(user_a_token)
    article_id = _make_article(app)
    job_id = _make_job(app)
    client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=headers)

    resp = client.get("/api/v1/saved", headers=headers)
    counts = resp.get_json()["data"]["counts"]
    assert counts["article"] == 1
    assert counts["job"] == 1
    assert counts["opportunity"] == 0


# ---------------------------------------------------------------------------
# Privacy: no audit-log leakage
# ---------------------------------------------------------------------------


def test_saving_does_not_write_audit_log_entries(client, app, user_a_token):
    from app.models.audit import AuditLog

    with app.app_context():
        before = AuditLog.query.count()

    article_id = _make_article(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/saved", json={"content_type": "article", "content_id": article_id}, headers=headers)
    client.delete(f"/api/v1/saved/article/{article_id}", headers=headers)

    with app.app_context():
        after = AuditLog.query.count()
    assert after == before
