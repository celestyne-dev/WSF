"""WSF SEO Phase 2B — update-integration coverage for the 8 non-Article
entities' real CMS update endpoints (not just
create_entity_redirect_for_slug_change() in isolation — see
test_entity_redirects.py for that). Proves, through the actual
PUT /api/v1/... routes:

  * a slug change on a still-public entity commits an EntityRedirect
    in the SAME transaction as the slug update;
  * a draft rename never creates one (section 6/12);
  * a published-and-archived-in-the-same-save rename never creates one
    (section 6/12) — "renamed and unpublished" must never leave a
    redirect pointing at a now-404 slug;
  * a failed update (schema/business validation error) leaves neither
    the slug change nor the redirect persisted — the atomic-failure
    property required by section 21, proven here for Resource as the
    complex entity the task calls out by name.

Representative coverage per section 12's explicit list: Topic (draft/
published/archived-on-save), plus Author ("active"), Job
(is_job_publicly_visible), Event (is_event_publicly_visible), Resource
(is_publicly_visible()).
"""
import datetime

import pytest

from app.extensions import db
from tests.conftest import auth_headers

ADMIN_PAYLOAD = {
    "email": "entity-redirects-admin@example.com",
    "password": "supersecret1",
    "first_name": "Admin",
    "last_name": "User",
    "country_code": "US",
}


@pytest.fixture()
def admin_token(client, app):
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=ADMIN_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=ADMIN_PAYLOAD["email"]).first()
        role = Role.query.filter_by(name="admin").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_PAYLOAD["email"], "password": ADMIN_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


def _redirect_row(app, entity_type, from_slug):
    from app.models.entity_redirect import EntityRedirect

    with app.app_context():
        return EntityRedirect.query.filter_by(entity_type=entity_type, from_slug=from_slug).first()


# --------------------------------------------------------------------------
# Topic / Series — admin_taxonomy.py, partial TopicUpdateSchema/
# SeriesUpdateSchema (status omitted from a payload leaves it unchanged;
# included, it's a full explicit transition).
# --------------------------------------------------------------------------


def _make_topic_row(app, slug, status="published"):
    from app.models.taxonomy import Topic

    with app.app_context():
        row = Topic(slug=slug, name="A Topic", status=status)
        db.session.add(row)
        db.session.commit()
        return row.id


class TestTopicUpdateIntegration:
    def test_published_rename_creates_redirect_in_same_transaction(self, client, app, admin_token):
        topic_id = _make_topic_row(app, "old-topic-slug", status="published")

        resp = client.put(
            f"/api/v1/admin/taxonomy/topics/{topic_id}",
            json={"slug": "new-topic-slug"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["slug"] == "new-topic-slug"
        assert _redirect_row(app, "topic", "old-topic-slug").to_slug == "new-topic-slug"

    def test_draft_rename_creates_no_redirect(self, client, app, admin_token):
        topic_id = _make_topic_row(app, "draft-topic-slug", status="draft")

        resp = client.put(
            f"/api/v1/admin/taxonomy/topics/{topic_id}",
            json={"slug": "renamed-draft-topic-slug"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "topic", "draft-topic-slug") is None

    def test_published_renamed_and_archived_in_same_save_creates_no_redirect(self, client, app, admin_token):
        topic_id = _make_topic_row(app, "soon-archived-topic", status="published")

        resp = client.put(
            f"/api/v1/admin/taxonomy/topics/{topic_id}",
            json={"slug": "archived-topic-new-slug", "status": "archived"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "topic", "soon-archived-topic") is None


def _make_series_row(app, slug, status="published"):
    from app.models.taxonomy import Series

    with app.app_context():
        row = Series(slug=slug, name="A Series", status=status)
        db.session.add(row)
        db.session.commit()
        return row.id


class TestSeriesUpdateIntegration:
    def test_published_rename_creates_redirect_in_same_transaction(self, client, app, admin_token):
        series_id = _make_series_row(app, "old-series-slug", status="published")

        resp = client.put(
            f"/api/v1/admin/taxonomy/series/{series_id}",
            json={"slug": "new-series-slug"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "series", "old-series-slug").to_slug == "new-series-slug"

    def test_draft_rename_creates_no_redirect(self, client, app, admin_token):
        series_id = _make_series_row(app, "draft-series-slug", status="draft")

        resp = client.put(
            f"/api/v1/admin/taxonomy/series/{series_id}",
            json={"slug": "renamed-draft-series-slug"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "series", "draft-series-slug") is None


# --------------------------------------------------------------------------
# Person — people.py, full PersonInputSchema (status always explicit).
# --------------------------------------------------------------------------


def _make_person_row(app, slug, status="published"):
    from app.models.people import Person

    with app.app_context():
        row = Person(slug=slug, name="A Person", status=status, bio=[], short_bio="A short bio.")
        db.session.add(row)
        db.session.commit()
        return row.id


def _person_payload(**overrides):
    payload = {
        "name": "A Person",
        "shortBio": "A short bio.",
        "status": "published",
    }
    payload.update(overrides)
    return payload


class TestPersonUpdateIntegration:
    def test_published_rename_creates_redirect_in_same_transaction(self, client, app, admin_token):
        _make_person_row(app, "old-person-slug", status="published")

        resp = client.put(
            "/api/v1/people/old-person-slug",
            json=_person_payload(slug="new-person-slug"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "person", "old-person-slug").to_slug == "new-person-slug"

    def test_draft_rename_creates_no_redirect(self, client, app, admin_token):
        _make_person_row(app, "draft-person-slug", status="draft")

        resp = client.put(
            "/api/v1/people/draft-person-slug",
            json=_person_payload(slug="renamed-draft-person-slug", status="draft"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "person", "draft-person-slug") is None

    def test_published_renamed_and_archived_in_same_save_creates_no_redirect(self, client, app, admin_token):
        _make_person_row(app, "soon-archived-person", status="published")

        resp = client.put(
            "/api/v1/people/soon-archived-person",
            json=_person_payload(slug="archived-person-new-slug", status="archived"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "person", "soon-archived-person") is None


# --------------------------------------------------------------------------
# Author — authors.py, full AuthorInputSchema, "active" (not "published")
# is the live status.
# --------------------------------------------------------------------------


def _make_author_row(app, slug, status="active"):
    from app.models.people import Author

    with app.app_context():
        row = Author(slug=slug, name="An Author", status=status, short_bio="A short bio.")
        db.session.add(row)
        db.session.commit()
        return row.id


def _author_payload(**overrides):
    payload = {
        "name": "An Author",
        "shortBio": "A short bio.",
        "status": "active",
    }
    payload.update(overrides)
    return payload


class TestAuthorUpdateIntegration:
    def test_active_rename_creates_redirect_in_same_transaction(self, client, app, admin_token):
        _make_author_row(app, "old-author-slug", status="active")

        resp = client.put(
            "/api/v1/authors/old-author-slug",
            json=_author_payload(slug="new-author-slug"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "author", "old-author-slug").to_slug == "new-author-slug"

    def test_draft_rename_creates_no_redirect(self, client, app, admin_token):
        _make_author_row(app, "draft-author-slug", status="draft")

        resp = client.put(
            "/api/v1/authors/draft-author-slug",
            json=_author_payload(slug="renamed-draft-author-slug", status="draft"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "author", "draft-author-slug") is None

    def test_active_renamed_and_archived_in_same_save_creates_no_redirect(self, client, app, admin_token):
        _make_author_row(app, "soon-archived-author", status="active")

        resp = client.put(
            "/api/v1/authors/soon-archived-author",
            json=_author_payload(slug="archived-author-new-slug", status="archived"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "author", "soon-archived-author") is None


# --------------------------------------------------------------------------
# Opportunity — opportunities.py, full OpportunityInputSchema.
# --------------------------------------------------------------------------


def _make_opportunity_row(app, slug, status="published"):
    from app.models.opportunity import Opportunity

    with app.app_context():
        row = Opportunity(
            slug=slug,
            title="An Opportunity",
            status=status,
            description=[{"type": "paragraph", "text": "Details."}],
            application_url="https://example.com/apply",
        )
        db.session.add(row)
        db.session.commit()
        return row.id


def _opportunity_payload(**overrides):
    payload = {
        "title": "An Opportunity",
        "organizationName": "A Funder",
        "description": [{"type": "paragraph", "text": "Details."}],
        "applicationUrl": "https://example.com/apply",
        "status": "published",
    }
    payload.update(overrides)
    return payload


class TestOpportunityUpdateIntegration:
    def test_published_rename_creates_redirect_in_same_transaction(self, client, app, admin_token):
        _make_opportunity_row(app, "old-opportunity-slug", status="published")

        resp = client.put(
            "/api/v1/opportunities/old-opportunity-slug",
            json=_opportunity_payload(slug="new-opportunity-slug"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "opportunity", "old-opportunity-slug").to_slug == "new-opportunity-slug"

    def test_draft_rename_creates_no_redirect(self, client, app, admin_token):
        _make_opportunity_row(app, "draft-opportunity-slug", status="draft")

        resp = client.put(
            "/api/v1/opportunities/draft-opportunity-slug",
            json=_opportunity_payload(slug="renamed-draft-opportunity-slug", status="draft"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "opportunity", "draft-opportunity-slug") is None

    def test_published_renamed_and_archived_in_same_save_creates_no_redirect(self, client, app, admin_token):
        _make_opportunity_row(app, "soon-archived-opportunity", status="published")

        resp = client.put(
            "/api/v1/opportunities/soon-archived-opportunity",
            json=_opportunity_payload(slug="archived-opportunity-new-slug", status="archived"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "opportunity", "soon-archived-opportunity") is None


# --------------------------------------------------------------------------
# Job — jobs.py, full JobInputSchema, is_job_publicly_visible() rule.
# --------------------------------------------------------------------------


def _make_job_row(app, slug, status="published"):
    from app.models.opportunity import Job

    with app.app_context():
        row = Job(
            slug=slug,
            title="A Job",
            status=status,
            company_name="A Company",
            description=[{"type": "paragraph", "text": "Details."}],
            application_url="https://example.com/apply",
        )
        db.session.add(row)
        db.session.commit()
        return row.id


def _job_payload(**overrides):
    payload = {
        "title": "A Job",
        "companyName": "A Company",
        "description": [{"type": "paragraph", "text": "Details."}],
        "applicationUrl": "https://example.com/apply",
        "status": "published",
    }
    payload.update(overrides)
    return payload


class TestJobUpdateIntegration:
    def test_published_rename_creates_redirect_in_same_transaction(self, client, app, admin_token):
        _make_job_row(app, "old-job-slug", status="published")

        resp = client.put(
            "/api/v1/jobs/old-job-slug",
            json=_job_payload(slug="new-job-slug"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "job", "old-job-slug").to_slug == "new-job-slug"

    def test_draft_rename_creates_no_redirect(self, client, app, admin_token):
        _make_job_row(app, "draft-job-slug", status="draft")

        resp = client.put(
            "/api/v1/jobs/draft-job-slug",
            json=_job_payload(slug="renamed-draft-job-slug", status="draft"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "job", "draft-job-slug") is None

    def test_published_renamed_and_archived_in_same_save_creates_no_redirect(self, client, app, admin_token):
        _make_job_row(app, "soon-archived-job", status="published")

        resp = client.put(
            "/api/v1/jobs/soon-archived-job",
            json=_job_payload(slug="archived-job-new-slug", status="archived"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "job", "soon-archived-job") is None


# --------------------------------------------------------------------------
# Event — events.py, full EventInputSchema, is_event_publicly_visible().
# --------------------------------------------------------------------------


def _make_event_row(app, slug, status="published"):
    from app.models.opportunity import Event

    with app.app_context():
        row = Event(
            slug=slug,
            title="An Event",
            status=status,
            description=[{"type": "paragraph", "text": "Details."}],
            date=datetime.date.today() + datetime.timedelta(days=30),
            registration_required=False,
        )
        db.session.add(row)
        db.session.commit()
        return row.id


def _event_payload(**overrides):
    payload = {
        "title": "An Event",
        "date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
        "description": [{"type": "paragraph", "text": "Details."}],
        "registrationRequired": False,
        "status": "published",
    }
    payload.update(overrides)
    return payload


class TestEventUpdateIntegration:
    def test_published_rename_creates_redirect_in_same_transaction(self, client, app, admin_token):
        _make_event_row(app, "old-event-slug", status="published")

        resp = client.put(
            "/api/v1/events/old-event-slug",
            json=_event_payload(slug="new-event-slug"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "event", "old-event-slug").to_slug == "new-event-slug"

    def test_draft_rename_creates_no_redirect(self, client, app, admin_token):
        _make_event_row(app, "draft-event-slug", status="draft")

        resp = client.put(
            "/api/v1/events/draft-event-slug",
            json=_event_payload(slug="renamed-draft-event-slug", status="draft"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "event", "draft-event-slug") is None

    def test_published_renamed_and_archived_in_same_save_creates_no_redirect(self, client, app, admin_token):
        _make_event_row(app, "soon-archived-event", status="published")

        resp = client.put(
            "/api/v1/events/soon-archived-event",
            json=_event_payload(slug="archived-event-new-slug", status="archived"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "event", "soon-archived-event") is None


# --------------------------------------------------------------------------
# Resource — resources.py, full ResourceInputSchema, is_publicly_visible().
# Also the designated complex entity for the atomic-failure test (section
# 21): a failed publish-validation save must persist neither the slug
# change nor the redirect.
# --------------------------------------------------------------------------


def _make_resource_row(app, slug, status="published"):
    from app.models.resource import Resource

    with app.app_context():
        row = Resource(
            slug=slug,
            name="A Resource",
            status=status,
            description=[{"type": "paragraph", "text": "Details."}],
            external_url="https://example.com/resource.pdf",
        )
        db.session.add(row)
        db.session.commit()
        return row.id


def _resource_payload(**overrides):
    payload = {
        "name": "A Resource",
        "description": [{"type": "paragraph", "text": "Details."}],
        "externalUrl": "https://example.com/resource.pdf",
        "status": "published",
    }
    payload.update(overrides)
    return payload


class TestResourceUpdateIntegration:
    def test_published_rename_creates_redirect_in_same_transaction(self, client, app, admin_token):
        _make_resource_row(app, "old-resource-slug", status="published")

        resp = client.put(
            "/api/v1/resources/old-resource-slug",
            json=_resource_payload(slug="new-resource-slug"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "resource", "old-resource-slug").to_slug == "new-resource-slug"

    def test_draft_rename_creates_no_redirect(self, client, app, admin_token):
        _make_resource_row(app, "draft-resource-slug", status="draft")

        resp = client.put(
            "/api/v1/resources/draft-resource-slug",
            json=_resource_payload(slug="renamed-draft-resource-slug", status="draft"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "resource", "draft-resource-slug") is None

    def test_published_renamed_and_archived_in_same_save_creates_no_redirect(self, client, app, admin_token):
        _make_resource_row(app, "soon-archived-resource", status="published")

        resp = client.put(
            "/api/v1/resources/soon-archived-resource",
            json=_resource_payload(slug="archived-resource-new-slug", status="archived"),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert _redirect_row(app, "resource", "soon-archived-resource") is None

    def test_failed_publish_validation_persists_neither_slug_nor_redirect(self, client, app, admin_token):
        """access_type=circle_only with no protected_file_path fails
        _validate_publish (app/api/v1/resources.py) AFTER the slug has
        already been reassigned in memory but BEFORE db.session.commit()
        — since this app has no exception-time rollback handler, the
        whole pending change (slug reassignment AND any redirect) is
        simply never flushed. Proves the atomic-failure property section
        21 calls for explicitly, through the real endpoint rather than
        the lower-level helper alone.
        """
        from app.models.resource import Resource

        resource_id = _make_resource_row(app, "stable-resource-slug", status="published")

        resp = client.put(
            "/api/v1/resources/stable-resource-slug",
            json=_resource_payload(
                slug="should-never-apply-slug",
                accessType="circle_only",
                externalUrl=None,
            ),
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

        with app.app_context():
            fresh = db.session.get(Resource, resource_id)
            assert fresh.slug == "stable-resource-slug"

        assert _redirect_row(app, "resource", "stable-resource-slug") is None
        assert _redirect_row(app, "resource", "should-never-apply-slug") is None
