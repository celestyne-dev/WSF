import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "story-editor@example.com",
    "password": "supersecret1",
    "first_name": "Ella",
    "last_name": "Editor",
    "country_code": "US",
}

ADMIN_PAYLOAD = {
    "email": "story-admin@example.com",
    "password": "supersecret1",
    "first_name": "Site",
    "last_name": "Admin",
    "country_code": "US",
}

NO_PERMISSION_PAYLOAD = {
    "email": "story-nobody@example.com",
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
def editor_token(client, app):
    return _register_with_role(client, app, EDITOR_PAYLOAD, "editor")


@pytest.fixture()
def admin_token(client, app):
    return _register_with_role(client, app, ADMIN_PAYLOAD, "admin")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login", json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


def _get_editor_id(app):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=EDITOR_PAYLOAD["email"]).first().id


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


def _make_person(app, slug="amara-diallo", name="Amara Diallo"):
    from app.extensions import db
    from app.models.people import Person

    with app.app_context():
        person = Person.query.filter_by(slug=slug).first()
        if person is None:
            person = Person(slug=slug, name=name)
            db.session.add(person)
            db.session.commit()
        return person.id


def _make_organization(app, slug="acme-co", name="Acme Co"):
    from app.extensions import db
    from app.models.people import Organization

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if org is None:
            org = Organization(slug=slug, name=name)
            db.session.add(org)
            db.session.commit()
        return org.id


def _make_author(app, slug="wsf-editorial", name="WSF Editorial"):
    from app.extensions import db
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug=slug).first()
        if author is None:
            author = Author(slug=slug, name=name)
            db.session.add(author)
            db.session.commit()
        return author.id


def _base_payload(**overrides):
    payload = {
        "firstName": "Amara",
        "lastName": "Diallo",
        "email": "amara@example.com",
        "countryCode": "KE",
        "title": "How I Rebuilt My Career",
        "summary": "After ten years raising three children, I went back to school.",
        "body": "Paragraph one.\n\nParagraph two.",
        "consentReviewGiven": True,
        "consentContactGiven": True,
        "consentAccuracyConfirmed": True,
    }
    payload.update(overrides)
    return payload


def _get_submission_by_email(app, email):
    from app.models.submissions import StorySubmission

    with app.app_context():
        return StorySubmission.query.filter_by(email=email.strip().lower()).first()


class TestPublicSubmission:
    def test_creates_submission_and_returns_only_reference(self, client):
        resp = client.post("/api/v1/submissions", json=_base_payload())
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert set(data.keys()) == {"reference"}
        assert data["reference"].startswith("WSF-STORY-")

    def test_creates_real_db_record_with_defaults(self, client, app):
        client.post("/api/v1/submissions", json=_base_payload())
        submission = _get_submission_by_email(app, "amara@example.com")
        assert submission is not None
        assert submission.status == "submitted"
        assert submission.subject_is_submitter is True
        assert submission.ai_involvement == "none"
        assert submission.verification_status == "unverified"

    def test_missing_required_field_rejected(self, client):
        payload = _base_payload()
        del payload["title"]
        resp = client.post("/api/v1/submissions", json=payload)
        assert resp.status_code == 422

    def test_invalid_email_rejected(self, client):
        resp = client.post("/api/v1/submissions", json=_base_payload(email="not-an-email"))
        assert resp.status_code == 422

    def test_invalid_country_rejected(self, client):
        resp = client.post("/api/v1/submissions", json=_base_payload(countryCode="ZZ"))
        assert resp.status_code == 422

    def test_invalid_url_rejected(self, client):
        resp = client.post("/api/v1/submissions", json=_base_payload(linkedinUrl="javascript:alert(1)"))
        assert resp.status_code == 422

    def test_missing_consent_rejected(self, client):
        payload = _base_payload()
        payload["consentAccuracyConfirmed"] = False
        resp = client.post("/api/v1/submissions", json=payload)
        assert resp.status_code == 422

    def test_topics_attached_by_slug(self, client, app):
        slug = _make_topic(app)
        client.post("/api/v1/submissions", json=_base_payload(email="topics@example.com", topicSlugs=[slug]))
        from app.models.submissions import StorySubmission

        with app.app_context():
            submission = StorySubmission.query.filter_by(email="topics@example.com").first()
            assert [t.slug for t in submission.topics] == [slug]

    def test_subject_about_another_person_requires_subject_name(self, client):
        payload = _base_payload(email="subject@example.com", subjectIsSubmitter=False)
        resp = client.post("/api/v1/submissions", json=payload)
        assert resp.status_code == 422

    def test_subject_about_another_person_accepted_with_name(self, client, app):
        payload = _base_payload(
            email="subject2@example.com", subjectIsSubmitter=False, subjectName="Grace Wanjiru", subjectRelationship="Colleague"
        )
        resp = client.post("/api/v1/submissions", json=payload)
        assert resp.status_code == 201
        submission = _get_submission_by_email(app, "subject2@example.com")
        assert submission.subject_permission_status == "not_applicable"

    def test_ai_provenance_field_stored(self, client, app):
        payload = _base_payload(email="ai@example.com", aiInvolvement="ai_assisted", aiProvenanceNote="Used AI to tighten grammar.")
        client.post("/api/v1/submissions", json=payload)
        submission = _get_submission_by_email(app, "ai@example.com")
        assert submission.ai_involvement == "ai_assisted"
        assert submission.ai_provenance_note == "Used AI to tighten grammar."

    def test_repeated_click_does_not_create_duplicate_row(self, client, app):
        payload = _base_payload(email="dupclick@example.com")
        client.post("/api/v1/submissions", json=payload)
        client.post("/api/v1/submissions", json=payload)
        from app.models.submissions import StorySubmission

        with app.app_context():
            count = StorySubmission.query.filter_by(email="dupclick@example.com").count()
        assert count == 1

    def test_two_different_stories_same_email_both_created(self, client, app):
        client.post("/api/v1/submissions", json=_base_payload(email="prolific@example.com", title="Story One"))
        client.post("/api/v1/submissions", json=_base_payload(email="prolific@example.com", title="Story Two"))
        from app.models.submissions import StorySubmission

        with app.app_context():
            count = StorySubmission.query.filter_by(email="prolific@example.com").count()
        assert count == 2

    def test_public_cannot_list_submissions(self, client):
        resp = client.get("/api/v1/submissions")
        assert resp.status_code == 401

    def test_public_cannot_read_a_submission(self, client, app):
        client.post("/api/v1/submissions", json=_base_payload(email="private@example.com"))
        submission = _get_submission_by_email(app, "private@example.com")
        resp = client.get(f"/api/v1/submissions/{submission.id}")
        assert resp.status_code == 401


class TestAdminSubmissions:
    def test_list_requires_permission(self, client, no_permission_token):
        resp = client.get("/api/v1/submissions", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

    def test_editor_role_can_list(self, client, editor_token):
        resp = client.get("/api/v1/submissions", headers=auth_headers(editor_token))
        assert resp.status_code == 200

    def test_list_hides_body_and_consent_fields(self, client, editor_token):
        client.post("/api/v1/submissions", json=_base_payload(email="listshape@example.com"))
        resp = client.get("/api/v1/submissions", headers=auth_headers(editor_token))
        row = resp.get_json()["data"][0]
        assert "body" not in row
        assert "consentAccuracyConfirmed" not in row

    def test_detail_shows_full_submission_never_publicly(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="detail@example.com"))
        submission = _get_submission_by_email(app, "detail@example.com")
        resp = client.get(f"/api/v1/submissions/{submission.id}", headers=auth_headers(editor_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["body"] == "Paragraph one.\n\nParagraph two."

    def test_search_by_reference(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="searchref@example.com"))
        submission = _get_submission_by_email(app, "searchref@example.com")
        resp = client.get(
            f"/api/v1/submissions?q={submission.reference}", headers=auth_headers(editor_token)
        )
        assert resp.get_json()["meta"]["total"] == 1

    def test_filter_by_status(self, client, editor_token):
        client.post("/api/v1/submissions", json=_base_payload(email="statusfilter@example.com"))
        resp = client.get("/api/v1/submissions?status=submitted", headers=auth_headers(editor_token))
        assert resp.get_json()["meta"]["total"] >= 1
        resp2 = client.get("/api/v1/submissions?status=declined", headers=auth_headers(editor_token))
        assert resp2.get_json()["meta"]["total"] == 0

    def test_status_transition(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="transition@example.com"))
        submission = _get_submission_by_email(app, "transition@example.com")
        resp = client.patch(
            f"/api/v1/submissions/{submission.id}/status", json={"status": "reviewing"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "reviewing"

    def test_cannot_mark_published_without_linked_published_article(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="nopublish@example.com"))
        submission = _get_submission_by_email(app, "nopublish@example.com")
        resp = client.patch(
            f"/api/v1/submissions/{submission.id}/status", json={"status": "published"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 422

    def test_assign_editor(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="assign@example.com"))
        submission = _get_submission_by_email(app, "assign@example.com")
        editor_id = _get_editor_id(app)
        resp = client.post(
            f"/api/v1/submissions/{submission.id}/assign", json={"editorId": editor_id}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["assigned_editor"]["id"] == editor_id

    def test_internal_note_never_public(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="notes@example.com"))
        submission = _get_submission_by_email(app, "notes@example.com")
        client.post(
            f"/api/v1/submissions/{submission.id}/notes",
            json={"body": "Strong leadership angle."},
            headers=auth_headers(editor_token),
        )
        admin_view = client.get(f"/api/v1/submissions/{submission.id}", headers=auth_headers(editor_token))
        assert admin_view.get_json()["data"]["notes"][0]["body"] == "Strong leadership angle."

    def test_link_existing_person(self, client, editor_token, app):
        person_id = _make_person(app)
        client.post("/api/v1/submissions", json=_base_payload(email="linkperson@example.com"))
        submission = _get_submission_by_email(app, "linkperson@example.com")
        resp = client.patch(
            f"/api/v1/submissions/{submission.id}", json={"personId": person_id}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["person"]["id"] == person_id

    def test_link_existing_organization(self, client, editor_token, app):
        org_id = _make_organization(app)
        client.post("/api/v1/submissions", json=_base_payload(email="linkorg@example.com"))
        submission = _get_submission_by_email(app, "linkorg@example.com")
        resp = client.patch(
            f"/api/v1/submissions/{submission.id}", json={"organizationId": org_id}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["organization"]["id"] == org_id

    def test_withdrawal(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="withdraw@example.com"))
        submission = _get_submission_by_email(app, "withdraw@example.com")
        resp = client.patch(
            f"/api/v1/submissions/{submission.id}/status", json={"status": "withdrawn"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "withdrawn"

    def test_archive(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="archive@example.com"))
        submission = _get_submission_by_email(app, "archive@example.com")
        resp = client.patch(
            f"/api/v1/submissions/{submission.id}/status", json={"status": "archived"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "archived"

    def test_delete_allowed_for_early_status(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="deleteok@example.com"))
        submission = _get_submission_by_email(app, "deleteok@example.com")
        resp = client.delete(f"/api/v1/submissions/{submission.id}", headers=auth_headers(editor_token))
        assert resp.status_code == 200

    def test_delete_blocked_once_approved(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="deleteblocked@example.com"))
        submission = _get_submission_by_email(app, "deleteblocked@example.com")
        client.patch(
            f"/api/v1/submissions/{submission.id}/status", json={"status": "reviewing"}, headers=auth_headers(editor_token)
        )
        client.patch(
            f"/api/v1/submissions/{submission.id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        resp = client.delete(f"/api/v1/submissions/{submission.id}", headers=auth_headers(editor_token))
        assert resp.status_code == 409

    def test_delete_blocked_with_notes(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="deletenotes@example.com"))
        submission = _get_submission_by_email(app, "deletenotes@example.com")
        client.post(
            f"/api/v1/submissions/{submission.id}/notes", json={"body": "Note"}, headers=auth_headers(editor_token)
        )
        resp = client.delete(f"/api/v1/submissions/{submission.id}", headers=auth_headers(editor_token))
        assert resp.status_code == 409

    def test_history_records_actions(self, client, editor_token, app):
        client.post("/api/v1/submissions", json=_base_payload(email="history@example.com"))
        submission = _get_submission_by_email(app, "history@example.com")
        client.patch(
            f"/api/v1/submissions/{submission.id}/status", json={"status": "reviewing"}, headers=auth_headers(editor_token)
        )
        resp = client.get(f"/api/v1/submissions/{submission.id}/history", headers=auth_headers(editor_token))
        actions = [e["action"] for e in resp.get_json()["data"]]
        assert "submission.received" in actions
        assert "submission.status_changed" in actions


class TestArticleHandoff:
    def _approved_submission(self, client, app, email="handoff@example.com"):
        client.post("/api/v1/submissions", json=_base_payload(email=email))
        submission = _get_submission_by_email(app, email)
        return submission.id

    def test_requires_approved_status(self, client, editor_token, app):
        submission_id = self._approved_submission(client, app, "notapproved@example.com")
        author_id = _make_author(app)
        resp = client.post(
            f"/api/v1/submissions/{submission_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 409

    def test_creates_draft_article_and_preserves_submission(self, client, editor_token, app):
        submission_id = self._approved_submission(client, app, "convert@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/submissions/{submission_id}/status", json={"status": "reviewing"}, headers=auth_headers(editor_token)
        )
        client.patch(
            f"/api/v1/submissions/{submission_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )

        resp = client.post(
            f"/api/v1/submissions/{submission_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        article = body["article"]
        assert article["status"] == "draft"
        assert body["submission"]["status"] == "converted"

        from app.extensions import db
        from app.models.article import Article
        from app.models.submissions import StorySubmission

        with app.app_context():
            fresh = db.session.get(StorySubmission, submission_id)
            assert fresh.body == "Paragraph one.\n\nParagraph two."  # original preserved verbatim
            assert fresh.status == "converted"

            created = db.session.get(Article, article["id"])
            assert created.source_submission_id == submission_id
            assert created.status == "draft"

    def test_cannot_convert_twice(self, client, editor_token, app):
        submission_id = self._approved_submission(client, app, "onceonly@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/submissions/{submission_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        client.post(
            f"/api/v1/submissions/{submission_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        second = client.post(
            f"/api/v1/submissions/{submission_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        assert second.status_code == 409

    def test_does_not_auto_create_author(self, client, editor_token, app):
        submission_id = self._approved_submission(client, app, "noautoauthor@example.com")
        client.patch(
            f"/api/v1/submissions/{submission_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        from app.models.people import Author

        with app.app_context():
            before = Author.query.count()

        resp = client.post(
            f"/api/v1/submissions/{submission_id}/convert-to-article",
            json={"authorId": 999999},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 422

        with app.app_context():
            after = Author.query.count()
        assert before == after

    def test_published_status_derives_from_linked_article(self, client, editor_token, app):
        submission_id = self._approved_submission(client, app, "derivedpublish@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/submissions/{submission_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        convert = client.post(
            f"/api/v1/submissions/{submission_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        article_id = convert.get_json()["data"]["article"]["id"]

        from app.extensions import db
        from app.models.article import Article

        with app.app_context():
            article = db.session.get(Article, article_id)
            article.status = "published"
            db.session.commit()

        detail = client.get(f"/api/v1/submissions/{submission_id}", headers=auth_headers(editor_token))
        assert detail.get_json()["data"]["status"] == "published"

    def test_public_article_schema_never_exposes_submission_fields(self, client, editor_token, app):
        submission_id = self._approved_submission(client, app, "noleak@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/submissions/{submission_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        convert = client.post(
            f"/api/v1/submissions/{submission_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        article = convert.get_json()["data"]["article"]

        from app.extensions import db
        from app.models.article import Article

        with app.app_context():
            full = db.session.get(Article, article["id"])
            full.status = "published"
            db.session.commit()

        public_resp = client.get(f"/api/v1/articles/{article['slug']}")
        assert public_resp.status_code == 200
        assert "sourceSubmissionId" not in public_resp.get_json()["data"]
        assert "source_submission_id" not in public_resp.get_json()["data"]
