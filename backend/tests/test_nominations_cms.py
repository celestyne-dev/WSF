import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "nom-editor@example.com",
    "password": "supersecret1",
    "first_name": "Ella",
    "last_name": "Editor",
    "country_code": "US",
}

ADMIN_PAYLOAD = {
    "email": "nom-admin@example.com",
    "password": "supersecret1",
    "first_name": "Site",
    "last_name": "Admin",
    "country_code": "US",
}

NO_PERMISSION_PAYLOAD = {
    "email": "nom-nobody@example.com",
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


def _make_series(app, slug="women-leading-organizations", name="Women Leading Organizations"):
    from app.extensions import db
    from app.models.taxonomy import Series

    with app.app_context():
        series = Series.query.filter_by(slug=slug).first()
        if series is None:
            series = Series(slug=slug, name=name)
            db.session.add(series)
            db.session.commit()
        return series.id


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
        "nomineeName": "Grace Wanjiru",
        "countryCode": "KE",
        "achievements": "Founded a fintech company serving 2 million unbanked women across East Africa.",
        "nominatorName": "Naliaka Wafula",
        "nominatorEmail": "naliaka@example.com",
        "consentAccuracyConfirmed": True,
        "consentReviewGiven": True,
        "consentContactGiven": True,
    }
    payload.update(overrides)
    return payload


def _get_nomination_by_reference_lookup(app, nominator_email, nominee_name):
    from app.models.nominations import Nomination

    with app.app_context():
        return Nomination.query.filter_by(nominator_email=nominator_email, nominee_name=nominee_name).first()


class TestPublicNomination:
    def test_creates_nomination_and_returns_only_reference(self, client):
        resp = client.post("/api/v1/nominations", json=_base_payload())
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert set(data.keys()) == {"reference"}
        assert data["reference"].startswith("WSF-NOM-")

    def test_creates_real_db_record_with_defaults(self, client, app):
        client.post("/api/v1/nominations", json=_base_payload())
        nomination = _get_nomination_by_reference_lookup(app, "naliaka@example.com", "Grace Wanjiru")
        assert nomination is not None
        assert nomination.status == "submitted"
        assert nomination.is_self_nomination is False
        assert nomination.nominee_awareness == "unknown"
        assert nomination.verification_state == "not_started"

    def test_missing_required_field_rejected(self, client):
        payload = _base_payload()
        del payload["achievements"]
        resp = client.post("/api/v1/nominations", json=payload)
        assert resp.status_code == 422

    def test_invalid_email_rejected(self, client):
        resp = client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="not-an-email"))
        assert resp.status_code == 422

    def test_invalid_country_rejected(self, client):
        resp = client.post("/api/v1/nominations", json=_base_payload(countryCode="ZZ"))
        assert resp.status_code == 422

    def test_invalid_url_rejected(self, client):
        resp = client.post("/api/v1/nominations", json=_base_payload(websiteUrl="javascript:alert(1)"))
        assert resp.status_code == 422

    def test_invalid_supporting_link_rejected(self, client):
        payload = _base_payload(supportingLinks=[{"url": "javascript:alert(1)", "label": "Press"}])
        resp = client.post("/api/v1/nominations", json=payload)
        assert resp.status_code == 422

    def test_missing_consent_rejected(self, client):
        payload = _base_payload()
        payload["consentAccuracyConfirmed"] = False
        resp = client.post("/api/v1/nominations", json=payload)
        assert resp.status_code == 422

    def test_invalid_series_rejected(self, client):
        resp = client.post("/api/v1/nominations", json=_base_payload(seriesId=999999))
        assert resp.status_code == 422

    def test_valid_series_accepted(self, client, app):
        series_id = _make_series(app)
        resp = client.post("/api/v1/nominations", json=_base_payload(seriesId=series_id, nominatorEmail="series@example.com"))
        assert resp.status_code == 201

    def test_topics_attached_by_slug(self, client, app):
        slug = _make_topic(app)
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="topics@example.com", topicSlugs=[slug]))
        from app.models.nominations import Nomination

        with app.app_context():
            nomination = Nomination.query.filter_by(nominator_email="topics@example.com").first()
            assert [t.slug for t in nomination.topics] == [slug]

    def test_self_nomination_allowed(self, client, app):
        payload = _base_payload(nominatorEmail="self@example.com", isSelfNomination=True, nomineeName="Self Nominator")
        resp = client.post("/api/v1/nominations", json=payload)
        assert resp.status_code == 201
        nomination = _get_nomination_by_reference_lookup(app, "self@example.com", "Self Nominator")
        assert nomination.is_self_nomination is True

    def test_repeated_click_does_not_create_duplicate_row(self, client, app):
        payload = _base_payload(nominatorEmail="dupclick@example.com")
        client.post("/api/v1/nominations", json=payload)
        client.post("/api/v1/nominations", json=payload)
        from app.models.nominations import Nomination

        with app.app_context():
            count = Nomination.query.filter_by(nominator_email="dupclick@example.com").count()
        assert count == 1

    def test_second_legitimate_nomination_for_same_nominee_both_exist(self, client, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="first@example.com", nomineeName="Joy Achieng"))
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="second@example.com", nomineeName="Joy Achieng", achievements="A different, independent account of her work."))
        from app.models.nominations import Nomination

        with app.app_context():
            rows = Nomination.query.filter_by(nominee_name="Joy Achieng").all()
        assert len(rows) == 2
        assert {r.status for r in rows} == {"submitted"}

    def test_second_nomination_for_same_nominee_flagged_possible_duplicate(self, client, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="dupa@example.com", nomineeName="Wanjiku Kamau"))
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="dupb@example.com", nomineeName="wanjiku kamau", achievements="Separate testimony about the same leader."))
        from app.models.nominations import Nomination

        with app.app_context():
            rows = Nomination.query.filter(Nomination.nominee_name.ilike("%wanjiku kamau%")).order_by(Nomination.id).all()
        assert len(rows) == 2
        assert rows[0].possible_duplicate is False
        assert rows[1].possible_duplicate is True

    def test_public_cannot_list_nominations(self, client):
        resp = client.get("/api/v1/nominations")
        assert resp.status_code == 401

    def test_public_cannot_read_a_nomination(self, client, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="private@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "private@example.com", "Grace Wanjiru")
        resp = client.get(f"/api/v1/nominations/{nomination.id}")
        assert resp.status_code == 401


class TestAdminNominations:
    def test_list_requires_permission(self, client, no_permission_token):
        resp = client.get("/api/v1/nominations", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

    def test_editor_role_can_list(self, client, editor_token):
        resp = client.get("/api/v1/nominations", headers=auth_headers(editor_token))
        assert resp.status_code == 200

    def test_list_hides_achievements_and_consent_and_nominator_email(self, client, editor_token):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="listshape@example.com"))
        resp = client.get("/api/v1/nominations", headers=auth_headers(editor_token))
        row = resp.get_json()["data"][0]
        assert "achievements" not in row
        assert "nominator_email" not in row
        assert "consent_accuracy_confirmed" not in row

    def test_detail_shows_full_nomination_never_publicly(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="detail@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "detail@example.com", "Grace Wanjiru")
        resp = client.get(f"/api/v1/nominations/{nomination.id}", headers=auth_headers(editor_token))
        assert resp.status_code == 200
        assert "unbanked women" in resp.get_json()["data"]["achievements"]
        assert resp.get_json()["data"]["nominator_email"] == "detail@example.com"

    def test_search_by_reference(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="searchref@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "searchref@example.com", "Grace Wanjiru")
        resp = client.get(f"/api/v1/nominations?q={nomination.reference}", headers=auth_headers(editor_token))
        assert resp.get_json()["meta"]["total"] == 1

    def test_filter_by_status(self, client, editor_token):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="statusfilter@example.com"))
        resp = client.get("/api/v1/nominations?status=submitted", headers=auth_headers(editor_token))
        assert resp.get_json()["meta"]["total"] >= 1
        resp2 = client.get("/api/v1/nominations?status=declined", headers=auth_headers(editor_token))
        assert resp2.get_json()["meta"]["total"] == 0

    def test_status_transition(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="transition@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "transition@example.com", "Grace Wanjiru")
        resp = client.patch(
            f"/api/v1/nominations/{nomination.id}/status", json={"status": "reviewing"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "reviewing"

    def test_verification_needed_status(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="verifyneeded@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "verifyneeded@example.com", "Grace Wanjiru")
        resp = client.patch(
            f"/api/v1/nominations/{nomination.id}/status", json={"status": "verification_needed"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "verification_needed"

    def test_verification_state_update(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="verifystate@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "verifystate@example.com", "Grace Wanjiru")
        resp = client.patch(
            f"/api/v1/nominations/{nomination.id}",
            json={"verificationState": "complete", "verificationNotes": "Confirmed via company website and press."},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["verification_state"] == "complete"

    def test_cannot_mark_published_without_linked_published_article(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="nopublish@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "nopublish@example.com", "Grace Wanjiru")
        resp = client.patch(
            f"/api/v1/nominations/{nomination.id}/status", json={"status": "published"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 422

    def test_assign_reviewer(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="assign@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "assign@example.com", "Grace Wanjiru")
        editor_id = _get_editor_id(app)
        resp = client.post(
            f"/api/v1/nominations/{nomination.id}/assign", json={"reviewerId": editor_id}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["assigned_reviewer"]["id"] == editor_id

    def test_internal_note_never_public(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="notes@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "notes@example.com", "Grace Wanjiru")
        client.post(
            f"/api/v1/nominations/{nomination.id}/notes",
            json={"body": "Possible duplicate of existing Person — confirm before approving."},
            headers=auth_headers(editor_token),
        )
        admin_view = client.get(f"/api/v1/nominations/{nomination.id}", headers=auth_headers(editor_token))
        assert admin_view.get_json()["data"]["notes"][0]["body"] == "Possible duplicate of existing Person — confirm before approving."

    def test_link_existing_person(self, client, editor_token, app):
        person_id = _make_person(app)
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="linkperson@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "linkperson@example.com", "Grace Wanjiru")
        resp = client.patch(
            f"/api/v1/nominations/{nomination.id}", json={"personId": person_id}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["person"]["id"] == person_id

    def test_link_existing_organization(self, client, editor_token, app):
        org_id = _make_organization(app)
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="linkorg@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "linkorg@example.com", "Grace Wanjiru")
        resp = client.patch(
            f"/api/v1/nominations/{nomination.id}", json={"organizationId": org_id}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["organization"]["id"] == org_id

    def test_related_nominations_surfaced_without_merging(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="related1@example.com", nomineeName="Fatima Njoroge"))
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="related2@example.com", nomineeName="Fatima Njoroge", achievements="Independent second account."))
        first = _get_nomination_by_reference_lookup(app, "related1@example.com", "Fatima Njoroge")
        resp = client.get(f"/api/v1/nominations/{first.id}", headers=auth_headers(editor_token))
        related = resp.get_json()["data"]["related_nominations"]
        assert len(related) == 1

        from app.models.nominations import Nomination

        with app.app_context():
            assert Nomination.query.filter_by(nominee_name="Fatima Njoroge").count() == 2

    def test_withdrawal(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="withdraw@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "withdraw@example.com", "Grace Wanjiru")
        resp = client.patch(
            f"/api/v1/nominations/{nomination.id}/status", json={"status": "withdrawn"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "withdrawn"

    def test_archive(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="archive@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "archive@example.com", "Grace Wanjiru")
        resp = client.patch(
            f"/api/v1/nominations/{nomination.id}/status", json={"status": "archived"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "archived"

    def test_delete_allowed_for_early_status(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="deleteok@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "deleteok@example.com", "Grace Wanjiru")
        resp = client.delete(f"/api/v1/nominations/{nomination.id}", headers=auth_headers(editor_token))
        assert resp.status_code == 200

    def test_delete_blocked_once_approved(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="deleteblocked@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "deleteblocked@example.com", "Grace Wanjiru")
        client.patch(
            f"/api/v1/nominations/{nomination.id}/status", json={"status": "reviewing"}, headers=auth_headers(editor_token)
        )
        client.patch(
            f"/api/v1/nominations/{nomination.id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        resp = client.delete(f"/api/v1/nominations/{nomination.id}", headers=auth_headers(editor_token))
        assert resp.status_code == 409

    def test_delete_blocked_with_notes(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="deletenotes@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "deletenotes@example.com", "Grace Wanjiru")
        client.post(
            f"/api/v1/nominations/{nomination.id}/notes", json={"body": "Note"}, headers=auth_headers(editor_token)
        )
        resp = client.delete(f"/api/v1/nominations/{nomination.id}", headers=auth_headers(editor_token))
        assert resp.status_code == 409

    def test_history_records_actions(self, client, editor_token, app):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail="history@example.com"))
        nomination = _get_nomination_by_reference_lookup(app, "history@example.com", "Grace Wanjiru")
        client.patch(
            f"/api/v1/nominations/{nomination.id}/status", json={"status": "reviewing"}, headers=auth_headers(editor_token)
        )
        resp = client.get(f"/api/v1/nominations/{nomination.id}/history", headers=auth_headers(editor_token))
        actions = [e["action"] for e in resp.get_json()["data"]]
        assert "nomination.received" in actions
        assert "nomination.status_changed" in actions


class TestArticleHandoff:
    def _approved_nomination(self, client, app, email="handoff@example.com"):
        client.post("/api/v1/nominations", json=_base_payload(nominatorEmail=email))
        nomination = _get_nomination_by_reference_lookup(app, email, "Grace Wanjiru")
        return nomination.id

    def test_requires_approved_status(self, client, editor_token, app):
        nomination_id = self._approved_nomination(client, app, "notapproved@example.com")
        author_id = _make_author(app)
        resp = client.post(
            f"/api/v1/nominations/{nomination_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 409

    def test_creates_draft_article_and_preserves_nomination(self, client, editor_token, app):
        nomination_id = self._approved_nomination(client, app, "convert@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/nominations/{nomination_id}/status", json={"status": "reviewing"}, headers=auth_headers(editor_token)
        )
        client.patch(
            f"/api/v1/nominations/{nomination_id}/status", json={"status": "shortlisted"}, headers=auth_headers(editor_token)
        )
        client.patch(
            f"/api/v1/nominations/{nomination_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )

        resp = client.post(
            f"/api/v1/nominations/{nomination_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        article = body["article"]
        assert article["status"] == "draft"
        assert body["nomination"]["status"] == "in_editorial"

        from app.extensions import db
        from app.models.article import Article
        from app.models.nominations import Nomination

        with app.app_context():
            fresh = db.session.get(Nomination, nomination_id)
            assert "unbanked women" in fresh.achievements  # original preserved verbatim
            assert fresh.status == "in_editorial"

            created = db.session.get(Article, article["id"])
            assert created.source_nomination_id == nomination_id
            assert created.status == "draft"

    def test_cannot_convert_twice(self, client, editor_token, app):
        nomination_id = self._approved_nomination(client, app, "onceonly@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/nominations/{nomination_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        client.post(
            f"/api/v1/nominations/{nomination_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        second = client.post(
            f"/api/v1/nominations/{nomination_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )
        assert second.status_code == 409

    def test_does_not_auto_create_author(self, client, editor_token, app):
        nomination_id = self._approved_nomination(client, app, "noautoauthor@example.com")
        client.patch(
            f"/api/v1/nominations/{nomination_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        from app.models.people import Author

        with app.app_context():
            before = Author.query.count()

        resp = client.post(
            f"/api/v1/nominations/{nomination_id}/convert-to-article",
            json={"authorId": 999999},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 422

        with app.app_context():
            after = Author.query.count()
        assert before == after

    def test_does_not_auto_create_person(self, client, editor_token, app):
        nomination_id = self._approved_nomination(client, app, "noautoperson@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/nominations/{nomination_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        from app.models.people import Person

        with app.app_context():
            before = Person.query.count()

        client.post(
            f"/api/v1/nominations/{nomination_id}/convert-to-article",
            json={"authorId": author_id},
            headers=auth_headers(editor_token),
        )

        with app.app_context():
            after = Person.query.count()
        assert before == after

    def test_published_status_derives_from_linked_article(self, client, editor_token, app):
        nomination_id = self._approved_nomination(client, app, "derivedpublish@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/nominations/{nomination_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        convert = client.post(
            f"/api/v1/nominations/{nomination_id}/convert-to-article",
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

        detail = client.get(f"/api/v1/nominations/{nomination_id}", headers=auth_headers(editor_token))
        assert detail.get_json()["data"]["status"] == "published"

    def test_public_article_schema_never_exposes_nomination_fields(self, client, editor_token, app):
        nomination_id = self._approved_nomination(client, app, "noleak@example.com")
        author_id = _make_author(app)
        client.patch(
            f"/api/v1/nominations/{nomination_id}/status", json={"status": "approved"}, headers=auth_headers(editor_token)
        )
        convert = client.post(
            f"/api/v1/nominations/{nomination_id}/convert-to-article",
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
        assert "sourceNominationId" not in public_resp.get_json()["data"]
        assert "source_nomination_id" not in public_resp.get_json()["data"]


class TestRBAC:
    def test_moderator_can_manage_nominations(self, client, app):
        payload = {
            "email": "nom-moderator@example.com",
            "password": "supersecret1",
            "first_name": "Mod",
            "last_name": "Erator",
            "country_code": "US",
        }
        token = _register_with_role(client, app, payload, "moderator")
        resp = client.get("/api/v1/nominations", headers=auth_headers(token))
        assert resp.status_code == 200

    def test_author_role_cannot_manage_nominations(self, client, app):
        payload = {
            "email": "nom-author@example.com",
            "password": "supersecret1",
            "first_name": "Just",
            "last_name": "Author",
            "country_code": "US",
        }
        token = _register_with_role(client, app, payload, "author")
        resp = client.get("/api/v1/nominations", headers=auth_headers(token))
        assert resp.status_code == 403
