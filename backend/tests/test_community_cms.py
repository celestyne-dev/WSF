import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "community-manager@example.com",
    "password": "supersecret1",
    "first_name": "Diana",
    "last_name": "Kioko",
    "country_code": "KE",
}

ADMIN_PAYLOAD = {
    "email": "community-admin@example.com",
    "password": "supersecret1",
    "first_name": "Site",
    "last_name": "Admin",
    "country_code": "US",
}

MODERATOR_PAYLOAD = {
    "email": "community-moderator@example.com",
    "password": "supersecret1",
    "first_name": "Mod",
    "last_name": "Erator",
    "country_code": "GB",
}

NO_PERMISSION_PAYLOAD = {
    "email": "community-nobody@example.com",
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
    return _register_with_role(client, app, MANAGER_PAYLOAD, "community_manager")


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


def _make_page(app, status="draft", **overrides):
    from app.extensions import db
    from app.models.community import CommunityPage

    with app.app_context():
        page = db.session.get(CommunityPage, 1)
        if page is None:
            page = CommunityPage(id=1)
            db.session.add(page)
        page.hero_heading = overrides.get("hero_heading", "The WSF Community")
        page.status = status
        for key, value in overrides.items():
            setattr(page, key, value)
        db.session.commit()


def _base_join_payload(**overrides):
    payload = {
        "firstName": "Amara",
        "lastName": "Diallo",
        "email": "amara@example.com",
        "countryCode": "KE",
        "interestSlugs": ["leadership"],
        "consentGiven": True,
    }
    payload.update(overrides)
    return payload


def _get_member_by_email(app, email):
    from app.models.community import Member

    with app.app_context():
        return Member.query.filter_by(email=email.strip().lower()).first()


class TestPublicJoin:
    def test_join_creates_active_member(self, client, app):
        _make_topic(app)
        resp = client.post("/api/v1/community/join", json=_base_join_payload())
        assert resp.status_code == 201
        member = _get_member_by_email(app, "amara@example.com")
        assert member is not None
        assert member.status == "active"
        assert member.consent_given is True
        assert member.consent_at is not None

    def test_join_requires_consent(self, client, app):
        _make_topic(app)
        resp = client.post("/api/v1/community/join", json=_base_join_payload(consentGiven=False))
        assert resp.status_code == 422

    def test_join_requires_valid_email(self, client, app):
        _make_topic(app)
        resp = client.post("/api/v1/community/join", json=_base_join_payload(email="not-an-email"))
        assert resp.status_code == 422

    def test_join_requires_first_last_name_and_country(self, client, app):
        resp = client.post("/api/v1/community/join", json={"consentGiven": True})
        assert resp.status_code == 422

    def test_join_rejects_unknown_interest_slug_silently_ignored(self, client, app):
        # Unknown slugs are simply not resolved to a Topic — no error, no
        # arbitrary taxonomy created.
        resp = client.post("/api/v1/community/join", json=_base_join_payload(interestSlugs=["not-a-real-topic"]))
        assert resp.status_code == 201
        from app.models.community import Member

        with app.app_context():
            member = Member.query.filter_by(email="amara@example.com").first()
            assert member.interests == []

    def test_email_normalized_lowercase(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="Person@Example.COM"))
        member = _get_member_by_email(app, "person@example.com")
        assert member is not None
        assert member.email == "person@example.com"

    def test_duplicate_case_insensitive_email_does_not_create_second_record(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="dup@example.com"))
        resp = client.post("/api/v1/community/join", json=_base_join_payload(email="Dup@Example.com"))
        assert resp.status_code == 200
        from app.extensions import db
        from app.models.community import Member

        with app.app_context():
            assert Member.query.filter_by(email="dup@example.com").count() == 1

    def test_duplicate_active_member_acknowledged_not_duplicated(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="active@example.com"))
        resp = client.post("/api/v1/community/join", json=_base_join_payload(email="active@example.com"))
        assert resp.status_code == 200
        assert "already" in resp.get_json()["data"]["message"].lower()

    def test_rejoin_reactivates_left_member(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="left@example.com"))
        from app.extensions import db
        from app.models.community import Member

        with app.app_context():
            m = Member.query.filter_by(email="left@example.com").first()
            m.status = "left"
            db.session.commit()

        resp = client.post("/api/v1/community/join", json=_base_join_payload(email="left@example.com"))
        assert resp.status_code == 200
        assert "welcome back" in resp.get_json()["data"]["message"].lower()
        with app.app_context():
            m = Member.query.filter_by(email="left@example.com").first()
            assert m.status == "active"

    def test_declined_member_not_silently_reactivated(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="declined@example.com"))
        from app.extensions import db
        from app.models.community import Member

        with app.app_context():
            m = Member.query.filter_by(email="declined@example.com").first()
            m.status = "declined"
            db.session.commit()

        resp = client.post("/api/v1/community/join", json=_base_join_payload(email="declined@example.com"))
        assert resp.status_code == 200
        with app.app_context():
            m = Member.query.filter_by(email="declined@example.com").first()
            assert m.status == "declined"

    def test_join_does_not_auto_populate_directory_opt_in(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="privacy@example.com"))
        member = _get_member_by_email(app, "privacy@example.com")
        assert member.directory_opt_in is False

    def test_join_does_not_subscribe_to_newsletter_by_default(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="nonews@example.com"))
        from app.models.newsletter import NewsletterSubscriber

        with app.app_context():
            assert NewsletterSubscriber.query.filter_by(email="nonews@example.com").first() is None

    def test_join_with_newsletter_opt_in_subscribes_via_existing_service(self, client, app):
        _make_topic(app)
        client.post(
            "/api/v1/community/join",
            json=_base_join_payload(email="wantsnews@example.com", subscribeNewsletter=True),
        )
        from app.models.newsletter import NewsletterSubscriber

        with app.app_context():
            sub = NewsletterSubscriber.query.filter_by(email="wantsnews@example.com").first()
            assert sub is not None
            assert sub.status == "active"

    def test_join_stores_controlled_source(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="src@example.com", source="LinkedIn"))
        member = _get_member_by_email(app, "src@example.com")
        assert member.source == "LinkedIn"

    def test_join_rejects_arbitrary_source(self, client, app):
        resp = client.post(
            "/api/v1/community/join", json=_base_join_payload(email="badsrc@example.com", source="<script>hack")
        )
        assert resp.status_code == 422


class TestPublicCommunityPage:
    def test_404_when_not_published(self, client, app):
        resp = client.get("/api/v1/community/public")
        assert resp.status_code == 404

    def test_returns_published_page(self, client, app):
        _make_page(app, status="published")
        resp = client.get("/api/v1/community/public")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["page"]["hero"]["heading"] == "The WSF Community"

    def test_metrics_omitted_when_no_active_members(self, client, app):
        _make_page(app, status="published")
        resp = client.get("/api/v1/community/public")
        assert resp.get_json()["data"]["metrics"] is None

    def test_metrics_reflect_real_active_member_count(self, client, app):
        _make_topic(app)
        _make_page(app, status="published")
        client.post("/api/v1/community/join", json=_base_join_payload(email="metric1@example.com"))
        resp = client.get("/api/v1/community/public")
        metrics = resp.get_json()["data"]["metrics"]
        assert metrics["memberCount"] == 1


class TestPublicDirectory:
    def test_directory_excludes_non_opted_in_members(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="notlisted@example.com"))
        resp = client.get("/api/v1/community/directory")
        assert resp.get_json()["data"] == []

    def test_directory_includes_active_opted_in_members(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="listed@example.com"))
        member = _get_member_by_email(app, "listed@example.com")
        client.patch(
            f"/api/v1/community/members/{member.id}", json={"directoryOptIn": True},
            headers=auth_headers(manager_token),
        )
        resp = client.get("/api/v1/community/directory")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Amara Diallo"
        assert "email" not in data[0]

    def test_directory_excludes_inactive_members_even_if_opted_in(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="inactive@example.com"))
        member = _get_member_by_email(app, "inactive@example.com")
        client.patch(
            f"/api/v1/community/members/{member.id}", json={"directoryOptIn": True},
            headers=auth_headers(manager_token),
        )
        client.patch(
            f"/api/v1/community/members/{member.id}/status", json={"status": "paused"},
            headers=auth_headers(manager_token),
        )
        resp = client.get("/api/v1/community/directory")
        assert resp.get_json()["data"] == []


class TestAdminMembers:
    def test_list_requires_permission(self, client, app, no_permission_token):
        resp = client.get("/api/v1/community/members", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

    def test_moderator_can_list_members(self, client, app, moderator_token):
        resp = client.get("/api/v1/community/members", headers=auth_headers(moderator_token))
        assert resp.status_code == 200

    def test_list_and_search(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="searchme@example.com"))
        resp = client.get("/api/v1/community/members?q=Amara", headers=auth_headers(manager_token))
        assert resp.status_code == 200
        assert len(resp.get_json()["data"]) == 1

    def test_filter_by_status(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="statusfilter@example.com"))
        resp = client.get("/api/v1/community/members?status=active", headers=auth_headers(manager_token))
        assert len(resp.get_json()["data"]) == 1
        resp = client.get("/api/v1/community/members?status=declined", headers=auth_headers(manager_token))
        assert len(resp.get_json()["data"]) == 0

    def test_filter_by_country(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="country@example.com", countryCode="KE"))
        resp = client.get("/api/v1/community/members?country=KE", headers=auth_headers(manager_token))
        assert len(resp.get_json()["data"]) == 1
        resp = client.get("/api/v1/community/members?country=US", headers=auth_headers(manager_token))
        assert len(resp.get_json()["data"]) == 0

    def test_admin_serializer_includes_email_and_notes_field(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="fullrecord@example.com"))
        member = _get_member_by_email(app, "fullrecord@example.com")
        resp = client.get(f"/api/v1/community/members/{member.id}", headers=auth_headers(manager_token))
        data = resp.get_json()["data"]
        assert data["email"] == "fullrecord@example.com"
        assert "notes" in data

    def test_update_member_partial_preserves_other_fields(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="partial@example.com"))
        member = _get_member_by_email(app, "partial@example.com")
        resp = client.patch(
            f"/api/v1/community/members/{member.id}", json={"professionalTitle": "CEO"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["professional_title"] == "CEO"
        assert data["first_name"] == "Amara"

    def test_update_member_interests_replaces_list(self, client, app, manager_token):
        _make_topic(app, slug="leadership", name="Leadership")
        _make_topic(app, slug="career", name="Career")
        client.post("/api/v1/community/join", json=_base_join_payload(email="interests@example.com"))
        member = _get_member_by_email(app, "interests@example.com")
        resp = client.patch(
            f"/api/v1/community/members/{member.id}", json={"interestSlugs": ["career"]},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        assert [t["slug"] for t in resp.get_json()["data"]["interests"]] == ["career"]

    def test_update_email_conflict_rejected(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="one@example.com"))
        client.post("/api/v1/community/join", json=_base_join_payload(email="two@example.com"))
        member_two = _get_member_by_email(app, "two@example.com")
        resp = client.patch(
            f"/api/v1/community/members/{member_two.id}", json={"email": "one@example.com"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 409

    def test_status_change_sets_left_at(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="willleave@example.com"))
        member = _get_member_by_email(app, "willleave@example.com")
        resp = client.patch(
            f"/api/v1/community/members/{member.id}/status", json={"status": "left"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "left"
        assert data["left_at"] is not None

    def test_status_change_invalid_value_rejected(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="badstatus@example.com"))
        member = _get_member_by_email(app, "badstatus@example.com")
        resp = client.patch(
            f"/api/v1/community/members/{member.id}/status", json={"status": "not-a-status"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_internal_note_never_public(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="notedmember@example.com"))
        member = _get_member_by_email(app, "notedmember@example.com")
        client.patch(
            f"/api/v1/community/members/{member.id}", json={"directoryOptIn": True},
            headers=auth_headers(manager_token),
        )
        resp = client.post(
            f"/api/v1/community/members/{member.id}/notes", json={"body": "Interested in leadership workshops"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["notes"][0]["body"] == "Interested in leadership workshops"

        directory = client.get("/api/v1/community/directory")
        assert "notes" not in directory.get_json()["data"][0]
        assert "Interested" not in str(directory.get_json())

    def test_history_records_status_and_note_actions(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="history@example.com"))
        member = _get_member_by_email(app, "history@example.com")
        client.patch(
            f"/api/v1/community/members/{member.id}/status", json={"status": "paused"},
            headers=auth_headers(manager_token),
        )
        client.post(
            f"/api/v1/community/members/{member.id}/notes", json={"body": "note"},
            headers=auth_headers(manager_token),
        )
        resp = client.get(f"/api/v1/community/members/{member.id}/history", headers=auth_headers(manager_token))
        actions = {e["action"] for e in resp.get_json()["data"]}
        assert "member.status_change" in actions
        assert "member.note_add" in actions

    def test_delete_restricted_for_active_member(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="cantdelete@example.com"))
        member = _get_member_by_email(app, "cantdelete@example.com")
        resp = client.delete(f"/api/v1/community/members/{member.id}", headers=auth_headers(manager_token))
        assert resp.status_code == 409

    def test_delete_allowed_for_declined_member_without_notes(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="deleteme@example.com"))
        member = _get_member_by_email(app, "deleteme@example.com")
        client.patch(
            f"/api/v1/community/members/{member.id}/status", json={"status": "declined"},
            headers=auth_headers(manager_token),
        )
        resp = client.delete(f"/api/v1/community/members/{member.id}", headers=auth_headers(manager_token))
        assert resp.status_code == 204

    def test_export_requires_export_permission(self, client, app, moderator_token):
        # Moderator has community.manage but not community.export.
        resp = client.get("/api/v1/community/members/export", headers=auth_headers(moderator_token))
        assert resp.status_code == 403

    def test_export_succeeds_for_manager(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="exportme@example.com"))
        resp = client.get("/api/v1/community/members/export", headers=auth_headers(manager_token))
        assert resp.status_code == 200
        assert b"exportme@example.com" in resp.data
        assert "Internal" not in resp.data.decode("utf-8")

    def test_admin_role_has_community_permissions(self, client, app, admin_token):
        resp = client.get("/api/v1/community/members", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        resp = client.get("/api/v1/community/members/export", headers=auth_headers(admin_token))
        assert resp.status_code == 200


class TestPersonLink:
    def test_link_member_to_person(self, client, app, manager_token):
        from app.extensions import db
        from app.models.people import Person

        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="linked@example.com"))
        member = _get_member_by_email(app, "linked@example.com")

        with app.app_context():
            person = Person(slug="amara-diallo", name="Amara Diallo", status="published")
            db.session.add(person)
            db.session.commit()
            person_id = person.id

        resp = client.patch(
            f"/api/v1/community/members/{member.id}", json={"personId": person_id},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["person"]["slug"] == "amara-diallo"


class TestAdminCommunityPage:
    def test_get_requires_permission(self, client, app, no_permission_token):
        _make_page(app)
        resp = client.get("/api/v1/community/page", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

    def test_patch_updates_fields(self, client, app, manager_token):
        _make_page(app)
        resp = client.patch(
            "/api/v1/community/page", json={"heroHeading": "Updated Heading"}, headers=auth_headers(manager_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["hero_heading"] == "Updated Heading"

    def test_patch_cannot_set_status(self, client, app, manager_token):
        _make_page(app, status="draft")
        client.patch("/api/v1/community/page", json={"status": "published"}, headers=auth_headers(manager_token))
        resp = client.get("/api/v1/community/page", headers=auth_headers(manager_token))
        assert resp.get_json()["data"]["status"] == "draft"

    def test_status_action_publishes(self, client, app, manager_token):
        _make_page(app, status="draft")
        resp = client.patch(
            "/api/v1/community/page/status", json={"status": "published"}, headers=auth_headers(manager_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "published"

    def test_patch_sanitizes_content_blocks(self, client, app, manager_token):
        _make_page(app)
        resp = client.patch(
            "/api/v1/community/page",
            json={"introContent": [{"type": "paragraph", "text": "<script>alert(1)</script>Hello"}]},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        assert "<script>" not in resp.get_json()["data"]["intro_content"][0]["text"]

    def test_patch_validates_benefit_shape(self, client, app, manager_token):
        _make_page(app)
        resp = client.patch(
            "/api/v1/community/page", json={"benefits": [{"description": "missing a title"}]},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422
