"""Focused tests for the optional one-to-one Member.user_id account link
and the self-service join/leave/rejoin/update + admin link/unlink
endpoints it enables. See app/models/community.py (Member.user_id),
app/services/community_accounts.py, and the /community/me* and
/community/members/<id>/link-account resources in app/api/v1/community.py.
"""
import pytest

from tests.conftest import auth_headers

USER1 = {
    "email": "acctlink-user1@example.com", "password": "supersecret1",
    "first_name": "Amina", "last_name": "Diallo", "country_code": "KE",
}
USER2 = {
    "email": "acctlink-user2@example.com", "password": "supersecret1",
    "first_name": "Beatrice", "last_name": "Mwangi", "country_code": "NG",
}
MANAGER_PAYLOAD = {
    "email": "acctlink-manager@example.com", "password": "supersecret1",
    "first_name": "Diana", "last_name": "Kioko", "country_code": "KE",
}
NO_PERMISSION_PAYLOAD = {
    "email": "acctlink-nobody@example.com", "password": "supersecret1",
    "first_name": "No", "last_name": "Permission", "country_code": "US",
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
def user1_token(client):
    return _register(client, USER1)


@pytest.fixture()
def user2_token(client):
    return _register(client, USER2)


@pytest.fixture()
def manager_token(client, app):
    return _register_with_role(client, app, MANAGER_PAYLOAD, "community_manager")


@pytest.fixture()
def no_permission_token(client):
    return _register(client, NO_PERMISSION_PAYLOAD)


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


def _base_join_payload(**overrides):
    payload = {
        "firstName": "Legacy", "lastName": "Member", "email": "legacy@example.com",
        "countryCode": "KE", "interestSlugs": [], "consentGiven": True,
    }
    payload.update(overrides)
    return payload


def _get_member_by_email(app, email):
    from app.models.community import Member

    with app.app_context():
        return Member.query.filter_by(email=email.strip().lower()).first()


def _get_member_by_user_email(app, email):
    from app.models.community import Member
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            return None
        return Member.query.filter_by(user_id=user.id).first()


def _get_user(app, email):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first()


def _set_member_status(app, member_id, status):
    from app.extensions import db
    from app.models.community import Member

    with app.app_context():
        member = db.session.get(Member, member_id)
        member.status = status
        db.session.commit()


def _set_member_field(app, member_id, **fields):
    from app.extensions import db
    from app.models.community import Member

    with app.app_context():
        member = db.session.get(Member, member_id)
        for key, value in fields.items():
            setattr(member, key, value)
        db.session.commit()


class TestAccountVsMemberSeparation:
    # 1. creating User account still does NOT create Member
    def test_register_does_not_create_member(self, client, app, user1_token):
        assert _get_member_by_email(app, USER1["email"]) is None

    # 2. anonymous /community/join still creates unlinked Member; 56. existing
    # anonymous duplicate/reactivation behavior remains valid
    def test_anonymous_join_creates_unlinked_member_and_reactivates(self, client, app):
        _make_topic(app)
        resp = client.post("/api/v1/community/join", json=_base_join_payload())
        assert resp.status_code == 201
        member = _get_member_by_email(app, "legacy@example.com")
        assert member.user_id is None

        _set_member_status(app, member.id, "left")
        again = client.post("/api/v1/community/join", json=_base_join_payload())
        assert again.status_code == 200
        assert "reactivated" in again.get_json()["data"]["message"].lower()
        reloaded = _get_member_by_email(app, "legacy@example.com")
        assert reloaded.status == "active"
        assert reloaded.user_id is None


class TestAuthenticatedJoin:
    # 3,4,8,9: explicit join creates a linked Member; works for any active
    # user, no community.manage, no pre-existing Community membership.
    def test_authenticated_join_creates_linked_member(self, client, app, user1_token):
        _make_topic(app)
        resp = client.post(
            "/api/v1/community/me/join",
            json={"countryCode": "KE", "interestSlugs": ["leadership"], "consentGiven": True},
            headers=auth_headers(user1_token),
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["status"] == "active"
        assert data["membershipType"] == "Community Member"
        assert data["email"] == USER1["email"]

        member = _get_member_by_user_email(app, USER1["email"])
        assert member is not None
        assert member.source == "Community page"
        assert member.directory_opt_in is False

    # 5. request cannot choose a different email
    def test_authenticated_join_rejects_email_override(self, client, user1_token):
        resp = client.post(
            "/api/v1/community/me/join",
            json={"email": "someone-else@example.com", "consentGiven": True},
            headers=auth_headers(user1_token),
        )
        assert resp.status_code == 422

    # 6. consent still explicitly required
    def test_authenticated_join_requires_consent(self, client, user1_token):
        resp = client.post("/api/v1/community/me/join", json={}, headers=auth_headers(user1_token))
        assert resp.status_code == 422

    # 7. directory opt-in defaults false
    def test_authenticated_join_directory_defaults_false(self, client, app, user1_token):
        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        member = _get_member_by_user_email(app, USER1["email"])
        assert member.directory_opt_in is False

    # join rejects an unknown interest slug outright — the whole request
    # fails, and no Member is created (contrast with the separate,
    # deliberately lenient anonymous /community/join flow).
    def test_authenticated_join_rejects_unknown_interest_slug(self, client, app, user1_token):
        resp = client.post(
            "/api/v1/community/me/join",
            json={"consentGiven": True, "interestSlugs": ["not-a-real-slug"]},
            headers=auth_headers(user1_token),
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_interest"
        assert _get_member_by_user_email(app, USER1["email"]) is None

    # mixed valid + invalid slugs also rejects the whole join — never
    # creates a Member with only the valid interest kept.
    def test_authenticated_join_rejects_mixed_valid_invalid_slugs(self, client, app, user1_token):
        _make_topic(app)
        resp = client.post(
            "/api/v1/community/me/join",
            json={"consentGiven": True, "interestSlugs": ["leadership", "not-a-real-slug"]},
            headers=auth_headers(user1_token),
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_interest"
        assert _get_member_by_user_email(app, USER1["email"]) is None

    # 10. duplicate authenticated join is idempotent — never mutates status
    def test_duplicate_authenticated_join_is_idempotent(self, client, app, user1_token):
        first = client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        member_id = first.get_json()["data"]["id"]
        _set_member_status(app, member_id, "paused")

        second = client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        assert second.status_code == 200
        assert second.get_json()["data"]["id"] == member_id
        assert second.get_json()["data"]["status"] == "paused"  # untouched, not reactivated

    # 42,43,44. legacy same-email Member is never auto-claimed; safe generic conflict
    def test_authenticated_join_with_legacy_email_conflict(self, client, app):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="shared@example.com"))
        legacy = _get_member_by_email(app, "shared@example.com")

        token = _register(client, {
            "email": "shared@example.com", "password": "supersecret1",
            "first_name": "New", "last_name": "Account", "country_code": "KE",
        })
        resp = client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(token))
        assert resp.status_code == 409
        body = resp.get_json()
        assert body["error"]["code"] == "membership_link_required"
        # No internal details leaked — only a generic message + code, never
        # the legacy Member's id/status/private state.
        assert set(body["error"].keys()) <= {"message", "code"}
        assert legacy.id is not None  # sanity: the legacy row genuinely exists


class TestOwnerUniqueness:
    # 11. one User cannot own two Member rows (DB constraint)
    def test_user_cannot_own_two_members(self, app, user1_token):
        from sqlalchemy.exc import IntegrityError

        from app.extensions import db
        from app.models.community import Member
        from app.models.user import User

        with app.app_context():
            user = User.query.filter_by(email=USER1["email"]).first()
            db.session.add(Member(first_name="A", last_name="One", email="link-a@example.com", user_id=user.id, status="active"))
            db.session.commit()
            db.session.add(Member(first_name="B", last_name="Two", email="link-b@example.com", user_id=user.id, status="active"))
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()


class TestGetMe:
    # 13,14,15. owned-only lookup, never by email, never cross-account
    def test_get_me_scoped_to_current_user_only(self, client, app, user1_token, user2_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email=USER2["email"]))

        mine = client.get("/api/v1/community/me", headers=auth_headers(user1_token))
        assert mine.status_code == 200
        assert mine.get_json()["data"]["joined"] is False

        hers = client.get("/api/v1/community/me", headers=auth_headers(user2_token))
        assert hers.get_json()["data"]["joined"] is False  # not auto-claimed by matching email

        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        mine_again = client.get("/api/v1/community/me", headers=auth_headers(user1_token))
        assert mine_again.get_json()["data"]["joined"] is True
        assert mine_again.get_json()["data"]["member"]["email"] == USER1["email"]

        her_view = client.get("/api/v1/community/me", headers=auth_headers(user2_token))
        assert her_view.get_json()["data"]["joined"] is False


class TestSelfUpdate:
    @pytest.fixture()
    def joined_member(self, client, app, user1_token):
        _make_topic(app)
        resp = client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        return resp.get_json()["data"]

    # 16,22,23. owner can update allowed profile fields; country/URLs validate;
    # a valid interest slug is accepted.
    def test_owner_can_update_allowed_fields(self, client, app, user1_token, joined_member):
        resp = client.patch(
            "/api/v1/community/me",
            json={
                "professionalTitle": "Engineer", "countryCode": "NG", "city": "Lagos",
                "websiteUrl": "https://example.com", "interestSlugs": ["leadership"],
                "directoryOptIn": True, "communityUpdatesOptIn": False,
            },
            headers=auth_headers(user1_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["professionalTitle"] == "Engineer"
        assert data["country"]["code"] == "NG"
        assert data["directoryOptIn"] is True
        assert [i["slug"] for i in data["interests"]] == ["leadership"]

    def test_owner_update_rejects_invalid_country(self, client, joined_member, user1_token):
        resp = client.patch("/api/v1/community/me", json={"countryCode": "ZZ"}, headers=auth_headers(user1_token))
        assert resp.status_code == 422

    # 21. PATCH rejects an unknown interest slug outright — never a silent
    # partial apply that keeps only the valid ones.
    def test_owner_update_rejects_unknown_interest_slug(self, client, app, user1_token, joined_member):
        resp = client.patch(
            "/api/v1/community/me", json={"interestSlugs": ["not-a-real-slug"]}, headers=auth_headers(user1_token),
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_interest"

    # mixed valid + invalid slugs rejects the WHOLE update
    def test_owner_update_mixed_valid_invalid_slugs_rejects_whole_request(self, client, app, user1_token, joined_member):
        resp = client.patch(
            "/api/v1/community/me",
            json={"professionalTitle": "Should not apply", "interestSlugs": ["leadership", "not-a-real-slug"]},
            headers=auth_headers(user1_token),
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_interest"

    # a failed PATCH (unknown slug) leaves EVERYTHING — including other
    # fields in the same request and existing interests — unchanged.
    def test_owner_update_failure_leaves_member_unchanged(self, client, app, user1_token, joined_member):
        client.patch("/api/v1/community/me", json={"interestSlugs": ["leadership"]}, headers=auth_headers(user1_token))

        failed = client.patch(
            "/api/v1/community/me",
            json={"professionalTitle": "Should not apply", "interestSlugs": ["leadership", "not-a-real-slug"]},
            headers=auth_headers(user1_token),
        )
        assert failed.status_code == 422

        unchanged = client.get("/api/v1/community/me", headers=auth_headers(user1_token)).get_json()["data"]["member"]
        assert unchanged["professionalTitle"] != "Should not apply"
        assert [i["slug"] for i in unchanged["interests"]] == ["leadership"]

    # empty list is valid and clears interests
    def test_owner_update_empty_interest_list_clears_interests(self, client, app, user1_token, joined_member):
        client.patch("/api/v1/community/me", json={"interestSlugs": ["leadership"]}, headers=auth_headers(user1_token))
        resp = client.patch("/api/v1/community/me", json={"interestSlugs": []}, headers=auth_headers(user1_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["interests"] == []

    # duplicate valid slugs in the request never create duplicate associations
    def test_owner_update_duplicate_valid_slugs_no_duplicate_associations(self, client, app, user1_token, joined_member):
        resp = client.patch(
            "/api/v1/community/me", json={"interestSlugs": ["leadership", "leadership"]}, headers=auth_headers(user1_token),
        )
        assert resp.status_code == 200
        assert [i["slug"] for i in resp.get_json()["data"]["interests"]] == ["leadership"]

    def test_owner_update_rejects_invalid_url(self, client, joined_member, user1_token):
        resp = client.patch("/api/v1/community/me", json={"websiteUrl": "not-a-url"}, headers=auth_headers(user1_token))
        assert resp.status_code == 422

    # 17,18,19,20. forbidden self-service fields
    @pytest.mark.parametrize(
        "payload",
        [
            {"membershipType": "Premium Member"},
            {"status": "paused"},
            {"userId": 99999},
            {"email": "hijack@example.com"},
            {"source": "Hacked"},
            {"adminTags": ["vip"]},
        ],
    )
    def test_owner_cannot_update_forbidden_fields(self, client, joined_member, user1_token, payload):
        resp = client.patch("/api/v1/community/me", json=payload, headers=auth_headers(user1_token))
        assert resp.status_code == 422


class TestPublicDirectoryPrivacy:
    # 24,25,53. directory opt-in controls visibility; never leaks account data
    def test_directory_opt_in_controls_visibility_and_hides_account_fields(self, client, app, user1_token):
        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        client.patch("/api/v1/community/me", json={"directoryOptIn": True}, headers=auth_headers(user1_token))

        listed = client.get("/api/v1/community/directory").get_json()["data"]
        assert len(listed) == 1
        entry = listed[0]
        assert "user_id" not in entry
        assert "email" not in entry
        assert "user" not in entry

        client.patch("/api/v1/community/me", json={"directoryOptIn": False}, headers=auth_headers(user1_token))
        hidden = client.get("/api/v1/community/directory").get_json()["data"]
        assert hidden == []


class TestLeaveAndRejoin:
    @pytest.fixture()
    def joined(self, client, app, user1_token):
        client.post(
            "/api/v1/community/me/join",
            json={"consentGiven": True, "subscribeNewsletter": True},
            headers=auth_headers(user1_token),
        )
        client.patch("/api/v1/community/me", json={"directoryOptIn": True}, headers=auth_headers(user1_token))
        return _get_member_by_user_email(app, USER1["email"])

    # 26,27,28. leave sets status/left_at, forces directory off
    def test_leave_sets_status_and_clears_directory(self, client, app, user1_token, joined):
        resp = client.post("/api/v1/community/me/leave", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "left"
        assert data["leftAt"] is not None
        assert data["directoryOptIn"] is False

    # 29,30,31,32,33. leaving never touches User/Saved/Events/Learning/Newsletter
    def test_leave_does_not_touch_other_account_data(self, client, app, user1_token, joined):
        from app.extensions import db
        from app.models.event_registration import EventRegistration
        from app.models.learning import LearningProgram
        from app.models.learning_enrollment import LearningEnrollment
        from app.models.newsletter import NewsletterSubscriber
        from app.models.opportunity import Event
        from app.models.saved_item import SavedItem
        from app.models.user import User
        from datetime import date, timedelta

        with app.app_context():
            user = User.query.filter_by(email=USER1["email"]).first()
            db.session.add(SavedItem(user_id=user.id, content_type="article", content_id=1))
            event = Event(slug="acctlink-evt", title="Test Event", status="published", date=date.today() + timedelta(days=5))
            db.session.add(event)
            db.session.commit()
            db.session.add(EventRegistration(event_id=event.id, user_id=user.id, status="registered"))
            program = LearningProgram(title="Test Program", slug="acctlink-program")
            db.session.add(program)
            db.session.commit()
            db.session.add(LearningEnrollment(learning_program_id=program.id, user_id=user.id, status="active"))
            db.session.commit()

        client.post("/api/v1/community/me/leave", headers=auth_headers(user1_token))

        with app.app_context():
            reloaded_user = User.query.filter_by(email=USER1["email"]).first()
            assert reloaded_user is not None
            assert SavedItem.query.filter_by(user_id=reloaded_user.id).count() == 1
            assert EventRegistration.query.filter_by(user_id=reloaded_user.id).count() == 1
            assert LearningEnrollment.query.filter_by(user_id=reloaded_user.id).count() == 1
            subscriber = NewsletterSubscriber.query.filter_by(email=USER1["email"]).first()
            assert subscriber is not None
            assert subscriber.status == "active"

    # 34,35,36. rejoin reuses same row, keeps user_id, never restores directory
    def test_rejoin_from_left_reuses_row_and_keeps_directory_off(self, client, app, user1_token, joined):
        client.post("/api/v1/community/me/leave", headers=auth_headers(user1_token))
        _set_member_field(app, joined.id, directory_opt_in=True)  # simulate pre-existing true

        resp = client.post("/api/v1/community/me/rejoin", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["id"] == joined.id
        assert data["status"] == "active"
        assert data["leftAt"] is None
        assert data["directoryOptIn"] is False

        member = _get_member_by_user_email(app, USER1["email"])
        assert member.user_id is not None

    # 37. inactive member can rejoin
    def test_rejoin_from_inactive_allowed(self, client, app, user1_token, joined):
        _set_member_status(app, joined.id, "inactive")
        resp = client.post("/api/v1/community/me/rejoin", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "active"

    # 38,39,40,41. paused/pending/declined/archived cannot self-rejoin
    @pytest.mark.parametrize("status", ["paused", "pending", "declined", "archived"])
    def test_cannot_self_rejoin_from_staff_controlled_states(self, client, app, user1_token, joined, status):
        _set_member_status(app, joined.id, status)
        resp = client.post("/api/v1/community/me/rejoin", headers=auth_headers(user1_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "rejoin_not_allowed"
        member = _get_member_by_user_email(app, USER1["email"])
        assert member.status == status


class TestAdminAccountLinking:
    # 45,48. community.manage staff can link exact-email matching user; preserves history
    def test_manager_can_link_exact_email_match(self, client, app, manager_token):
        _make_topic(app)
        client.post("/api/v1/community/join", json=_base_join_payload(email="toclaim@example.com"))
        member = _get_member_by_email(app, "toclaim@example.com")
        _register(client, {
            "email": "toclaim@example.com", "password": "supersecret1",
            "first_name": "Claimed", "last_name": "User", "country_code": "KE",
        })
        user = _get_user(app, "toclaim@example.com")

        resp = client.post(f"/api/v1/community/members/{member.id}/link-account", headers=auth_headers(manager_token))
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["status"] == member.status
        assert body["linked_account"]["id"] == user.id
        assert body["linked_account"]["email"] == "toclaim@example.com"

    # 46. link fails if no matching user
    def test_link_fails_when_no_matching_user(self, client, app, manager_token):
        client.post("/api/v1/community/join", json=_base_join_payload(email="nomatch@example.com"))
        member = _get_member_by_email(app, "nomatch@example.com")
        resp = client.post(f"/api/v1/community/members/{member.id}/link-account", headers=auth_headers(manager_token))
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "no_matching_account"

    # already-linked Member guard
    def test_link_fails_when_member_already_linked(self, client, app, manager_token, user1_token):
        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        member = _get_member_by_user_email(app, USER1["email"])
        resp = client.post(f"/api/v1/community/members/{member.id}/link-account", headers=auth_headers(manager_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "already_linked"

    # 12,47. cannot attach a User already linked to a different Member
    def test_link_fails_when_user_already_linked_to_different_member(self, client, app, manager_token, user1_token):
        from app.extensions import db
        from app.models.user import User

        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        with app.app_context():
            user = User.query.filter_by(email=USER1["email"]).first()
            user.email = "acctlink-user1-new@example.com"
            db.session.commit()

        client.post("/api/v1/community/join", json=_base_join_payload(email="acctlink-user1-new@example.com"))
        other_member = _get_member_by_email(app, "acctlink-user1-new@example.com")
        resp = client.post(f"/api/v1/community/members/{other_member.id}/link-account", headers=auth_headers(manager_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "account_already_linked"

    # 49,50. unlink preserves both records
    def test_manager_can_unlink_preserving_both_records(self, client, app, manager_token, user1_token):
        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        member = _get_member_by_user_email(app, USER1["email"])

        resp = client.delete(f"/api/v1/community/members/{member.id}/link-account", headers=auth_headers(manager_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["linked_account"] is None

        with app.app_context():
            from app.extensions import db
            from app.models.community import Member
            from app.models.user import User

            assert db.session.get(Member, member.id) is not None
            assert User.query.filter_by(email=USER1["email"]).first() is not None

    # 51. link/unlink audited with safe metadata
    def test_link_and_unlink_are_audited_safely(self, client, app, manager_token, user1_token):
        from app.models.audit import AuditLog

        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        member = _get_member_by_user_email(app, USER1["email"])
        client.delete(f"/api/v1/community/members/{member.id}/link-account", headers=auth_headers(manager_token))

        client.post("/api/v1/community/join", json=_base_join_payload(email="reaudit@example.com"))
        legacy = _get_member_by_email(app, "reaudit@example.com")
        _register(client, {
            "email": "reaudit@example.com", "password": "supersecret1",
            "first_name": "Re", "last_name": "Audit", "country_code": "KE",
        })
        client.post(f"/api/v1/community/members/{legacy.id}/link-account", headers=auth_headers(manager_token))

        with app.app_context():
            entries = AuditLog.query.filter(AuditLog.action.in_(["member.link_account", "member.unlink_account"])).all()
            assert len(entries) == 2
            for entry in entries:
                assert "password" not in str(entry.changes).lower()
                assert "token" not in str(entry.changes).lower()

    # 52. linked Member email cannot be changed away from the linked User's email
    def test_linked_member_email_is_locked_to_account_email(self, client, app, manager_token, user1_token):
        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        member = _get_member_by_user_email(app, USER1["email"])

        blocked = client.patch(
            f"/api/v1/community/members/{member.id}", json={"email": "different@example.com"}, headers=auth_headers(manager_token)
        )
        assert blocked.status_code == 409
        assert blocked.get_json()["error"]["code"] == "linked_email_locked"

        unchanged = client.patch(
            f"/api/v1/community/members/{member.id}", json={"email": USER1["email"]}, headers=auth_headers(manager_token)
        )
        assert unchanged.status_code == 200

    # 55. unauthorized staff cannot link/unlink
    def test_unauthorized_staff_cannot_link_or_unlink(self, client, app, no_permission_token):
        client.post("/api/v1/community/join", json=_base_join_payload(email="guarded@example.com"))
        member = _get_member_by_email(app, "guarded@example.com")
        resp = client.post(f"/api/v1/community/members/{member.id}/link-account", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403
        resp2 = client.delete(f"/api/v1/community/members/{member.id}/link-account", headers=auth_headers(no_permission_token))
        assert resp2.status_code == 403

    # 54. linked-account metadata only shown to authorized staff (admin GET is already permission-gated)
    def test_member_detail_shows_linked_account_only_to_authorized_staff(self, client, app, manager_token, no_permission_token, user1_token):
        client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        member = _get_member_by_user_email(app, USER1["email"])

        as_manager = client.get(f"/api/v1/community/members/{member.id}", headers=auth_headers(manager_token))
        assert as_manager.status_code == 200
        assert as_manager.get_json()["data"]["linked_account"]["email"] == USER1["email"]

        as_nobody = client.get(f"/api/v1/community/members/{member.id}", headers=auth_headers(no_permission_token))
        assert as_nobody.status_code == 403


class TestMembershipTypeNotEntitlement:
    # confirms membership_type can never be set by a self-service request —
    # it always defaults to "Community Member" and is never attached to any
    # commercial/entitlement logic in this module.
    def test_authenticated_join_always_sets_community_member_type(self, client, app, user1_token):
        resp = client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["membershipType"] == "Community Member"


class TestRegressions:
    # 57. existing admin status workflow remains valid
    def test_existing_status_workflow_unaffected(self, client, app, manager_token):
        client.post("/api/v1/community/join", json=_base_join_payload(email="statuscheck@example.com"))
        member = _get_member_by_email(app, "statuscheck@example.com")
        resp = client.patch(f"/api/v1/community/members/{member.id}/status", json={"status": "paused"}, headers=auth_headers(manager_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "paused"

    # 58. existing Member export remains protected
    def test_export_still_protected(self, client, app, manager_token, no_permission_token):
        allowed = client.get("/api/v1/community/members/export", headers=auth_headers(manager_token))
        assert allowed.status_code == 200
        denied = client.get("/api/v1/community/members/export", headers=auth_headers(no_permission_token))
        assert denied.status_code == 403

    # 59. forced-password-change rules remain consistent on the new endpoints
    def test_must_change_password_blocks_me_endpoint(self, client, app, user1_token):
        from app.extensions import db
        from app.models.user import User

        with app.app_context():
            user = User.query.filter_by(email=USER1["email"]).first()
            user.must_change_password = True
            db.session.commit()

        resp = client.get("/api/v1/community/me", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "password_change_required"

    # 60. account/session behavior remains intact
    def test_auth_me_unaffected_by_this_module(self, client, user1_token):
        resp = client.get("/api/v1/auth/me", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["email"] == USER1["email"]
