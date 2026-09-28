"""Admin Notifications & Work Queue — the internal CMS inbox. See
app/models/notification.py and app/services/notifications.py for the
architecture (fan-out per-recipient rows, RBAC-driven recipients, dedupe).
"""
import pytest

from tests.conftest import auth_headers


def _register_and_login(client, app, email, role_name, is_active=True):
    from app.extensions import db
    from app.models.user import Role, User

    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret1", "first_name": "Test", "last_name": "User"},
    )
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if role_name:
            role = Role.query.filter_by(name=role_name).first()
            user.roles.append(role)
        if not is_active:
            user.is_active = False
        db.session.commit()
        user_id = user.id

    if not is_active:
        return None, user_id

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    return login.get_json()["data"]["access_token"], user_id


@pytest.fixture()
def submissions_manager_token(client, app):
    token, _ = _register_and_login(client, app, "notif-submissions-mgr@example.com", "submissions_manager")
    return token


@pytest.fixture()
def analyst_token(client, app):
    """A role with NO submissions.manage — used to prove fan-out doesn't
    over-notify unrelated staff.
    """
    token, _ = _register_and_login(client, app, "notif-analyst@example.com", "analyst")
    return token


@pytest.fixture()
def super_admin_token(client, app):
    token, _ = _register_and_login(client, app, "notif-superadmin@example.com", "super_admin")
    return token


@pytest.fixture()
def editor_token(client, app):
    token, _ = _register_and_login(client, app, "notif-editor@example.com", "editor")
    return token


@pytest.fixture()
def author_user_token(client, app):
    token, _ = _register_and_login(client, app, "notif-author@example.com", "author")
    return token


@pytest.fixture()
def author_slug(client, editor_token):
    resp = client.post(
        "/api/v1/authors",
        json={"name": "Notif Byline Author", "role": "Contributor", "countryCode": "NG"},
        headers=auth_headers(editor_token),
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]["slug"]


def _create_draft(client, token, author_slug, title="Notification Test Article"):
    resp = client.post(
        "/api/v1/articles",
        json={"title": title, "authorSlug": author_slug, "content": [{"type": "paragraph", "text": "Body."}]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]["slug"]


def _story_payload(email, title):
    return {
        "firstName": "Fictional",
        "lastName": "Submitter",
        "email": email,
        "countryCode": "KE",
        "title": title,
        "summary": "A fictional one-line summary of this test story submission.",
        "body": "A fictional test story body long enough to pass validation for this automated test.",
        "storyType": "personal_story",
        "consentReviewGiven": True,
        "consentContactGiven": True,
        "consentAccuracyConfirmed": True,
    }


def _nomination_payload(email):
    return {
        "nomineeName": "Fictional Nominee",
        "countryCode": "KE",
        "achievements": "A fictional description of the nominee's achievements, long enough to validate.",
        "nominatorName": "Fictional Nominator",
        "nominatorEmail": email,
        "consentAccuracyConfirmed": True,
        "consentReviewGiven": True,
        "consentContactGiven": True,
    }


# ---------------------------------------------------------------------------
# Core API — listing, unread count, read/unread, archive, mark-all-read
# ---------------------------------------------------------------------------


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/v1/admin/notifications").status_code == 401
    assert client.get("/api/v1/admin/notifications/unread-count").status_code == 401
    assert client.patch("/api/v1/admin/notifications/1/read").status_code == 401
    assert client.post("/api/v1/admin/notifications/mark-all-read").status_code == 401


def test_story_submission_creates_notification_for_recipient(client, app, submissions_manager_token):
    resp = client.post(
        "/api/v1/submissions",
        json=_story_payload("fictional-submitter@example.com", "A Fictional Test Story"),
        headers={},
    )
    assert resp.status_code == 201

    listing = client.get("/api/v1/admin/notifications", headers=auth_headers(submissions_manager_token))
    assert listing.status_code == 200
    items = listing.get_json()["data"]
    assert len(items) == 1
    assert items[0]["notification_type"] == "story_submission_received"
    assert items[0]["entity_type"] == "story_submission"
    assert items[0]["is_read"] is False
    assert items[0]["title"] == "New story submission"


def test_unread_count_lightweight_endpoint(client, submissions_manager_token):
    before = client.get("/api/v1/admin/notifications/unread-count", headers=auth_headers(submissions_manager_token))
    assert before.get_json()["data"]["count"] == 0

    client.post(
        "/api/v1/submissions",
        json=_story_payload("fictional-submitter-2@example.com", "Another Fictional Story"),
    )
    after = client.get("/api/v1/admin/notifications/unread-count", headers=auth_headers(submissions_manager_token))
    assert after.get_json()["data"]["count"] == 1


def test_mark_read_unread_and_all_read(client, submissions_manager_token):
    client.post(
        "/api/v1/submissions",
        json=_story_payload("mark-read-test@example.com", "Mark Read Test Story"),
    )
    items = client.get("/api/v1/admin/notifications", headers=auth_headers(submissions_manager_token)).get_json()["data"]
    notification_id = items[0]["id"]

    read_resp = client.patch(f"/api/v1/admin/notifications/{notification_id}/read", headers=auth_headers(submissions_manager_token))
    assert read_resp.status_code == 200
    assert read_resp.get_json()["data"]["is_read"] is True

    unread_resp = client.patch(f"/api/v1/admin/notifications/{notification_id}/unread", headers=auth_headers(submissions_manager_token))
    assert unread_resp.get_json()["data"]["is_read"] is False

    mark_all = client.post("/api/v1/admin/notifications/mark-all-read", headers=auth_headers(submissions_manager_token))
    assert mark_all.status_code == 200
    assert mark_all.get_json()["data"]["updated"] == 1

    unread_count = client.get("/api/v1/admin/notifications/unread-count", headers=auth_headers(submissions_manager_token))
    assert unread_count.get_json()["data"]["count"] == 0


def test_archive_removes_from_default_inbox_but_visible_in_archived_filter(client, submissions_manager_token):
    client.post(
        "/api/v1/submissions",
        json=_story_payload("archive-test@example.com", "Archive Test Story"),
    )
    items = client.get("/api/v1/admin/notifications", headers=auth_headers(submissions_manager_token)).get_json()["data"]
    notification_id = items[0]["id"]

    archive_resp = client.patch(f"/api/v1/admin/notifications/{notification_id}/archive", headers=auth_headers(submissions_manager_token))
    assert archive_resp.status_code == 200
    assert archive_resp.get_json()["data"]["is_archived"] is True

    default_inbox = client.get("/api/v1/admin/notifications", headers=auth_headers(submissions_manager_token)).get_json()["data"]
    assert notification_id not in [n["id"] for n in default_inbox]

    archived_view = client.get("/api/v1/admin/notifications?filter=archived", headers=auth_headers(submissions_manager_token)).get_json()["data"]
    assert notification_id in [n["id"] for n in archived_view]

    # Source record untouched.
    from app.extensions import db
    from app.models.submissions import StorySubmission
    with client.application.app_context():
        submission = StorySubmission.query.filter_by(email="archive-test@example.com").first()
        assert submission is not None
        assert submission.status == "submitted"


def test_pagination_and_unread_filter(client, submissions_manager_token):
    for i in range(3):
        client.post(
            "/api/v1/submissions",
            json=_story_payload(f"pagination-test-{i}@example.com", f"Pagination Test Story {i}"),
        )
    listing = client.get("/api/v1/admin/notifications?per_page=2&page=1", headers=auth_headers(submissions_manager_token))
    body = listing.get_json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 3

    unread = client.get("/api/v1/admin/notifications?filter=unread", headers=auth_headers(submissions_manager_token)).get_json()["data"]
    assert len(unread) == 3


# ---------------------------------------------------------------------------
# Security — per-user ownership
# ---------------------------------------------------------------------------


def test_user_cannot_access_another_users_notification(client, app, submissions_manager_token):
    client.post(
        "/api/v1/submissions",
        json=_story_payload("ownership-test@example.com", "Ownership Test Story"),
    )
    items = client.get("/api/v1/admin/notifications", headers=auth_headers(submissions_manager_token)).get_json()["data"]
    notification_id = items[0]["id"]

    token2, _ = _register_and_login(client, app, "notif-other-submissions-mgr@example.com", "submissions_manager")
    other_listing = client.get("/api/v1/admin/notifications", headers=auth_headers(token2)).get_json()["data"]
    assert notification_id not in [n["id"] for n in other_listing]

    forbidden = client.patch(f"/api/v1/admin/notifications/{notification_id}/read", headers=auth_headers(token2))
    assert forbidden.status_code == 404  # never reveals it belongs to someone else


# ---------------------------------------------------------------------------
# Recipient permission fan-out
# ---------------------------------------------------------------------------


def test_recipient_fanout_permission_holder_yes_unrelated_no_inactive_no_superadmin_yes(client, app):
    submissions_token, _ = _register_and_login(client, app, "fanout-submissions-mgr@example.com", "submissions_manager")
    analyst_token, _ = _register_and_login(client, app, "fanout-analyst@example.com", "analyst")
    superadmin_token, _ = _register_and_login(client, app, "fanout-superadmin@example.com", "super_admin")
    _, inactive_user_id = _register_and_login(client, app, "fanout-inactive-mgr@example.com", "submissions_manager", is_active=False)

    resp = client.post(
        "/api/v1/submissions",
        json=_story_payload("fanout-test@example.com", "Fanout Test Story"),
    )
    assert resp.status_code == 201

    submissions_mgr_items = client.get("/api/v1/admin/notifications", headers=auth_headers(submissions_token)).get_json()["data"]
    assert len(submissions_mgr_items) == 1

    analyst_items = client.get("/api/v1/admin/notifications", headers=auth_headers(analyst_token)).get_json()["data"]
    assert len(analyst_items) == 0

    superadmin_items = client.get("/api/v1/admin/notifications", headers=auth_headers(superadmin_token)).get_json()["data"]
    assert len(superadmin_items) == 1

    from app.models.notification import Notification
    with app.app_context():
        inactive_notifications = Notification.query.filter_by(recipient_user_id=inactive_user_id).count()
        assert inactive_notifications == 0


# ---------------------------------------------------------------------------
# Article review integration
# ---------------------------------------------------------------------------


def test_article_submit_review_notifies_publish_tier_not_author(client, app, editor_token, author_user_token, author_slug):
    slug = _create_draft(client, author_user_token, author_slug)
    resp = client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(author_user_token))
    assert resp.status_code == 200

    editor_items = client.get("/api/v1/admin/notifications", headers=auth_headers(editor_token)).get_json()["data"]
    assert len(editor_items) == 1
    assert editor_items[0]["notification_type"] == "article_review_requested"
    assert editor_items[0]["entity_type"] == "article"

    author_items = client.get("/api/v1/admin/notifications", headers=auth_headers(author_user_token)).get_json()["data"]
    assert len(author_items) == 0  # the requester is never notified of their own action


def test_article_repeated_review_request_does_not_silently_disappear(client, app, editor_token, author_user_token, author_slug):
    slug = _create_draft(client, author_user_token, author_slug)
    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(author_user_token))
    client.post(f"/api/v1/articles/{slug}/request-changes", json={}, headers=auth_headers(editor_token))
    client.post(f"/api/v1/articles/{slug}/move-to-draft", headers=auth_headers(author_user_token))
    second = client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(author_user_token))
    assert second.status_code == 200

    editor_items = client.get("/api/v1/admin/notifications", headers=auth_headers(editor_token)).get_json()["data"]
    review_requested = [n for n in editor_items if n["notification_type"] == "article_review_requested"]
    assert len(review_requested) == 2  # a later, genuinely new request is not swallowed


def test_article_approval_notifies_creator_not_approver(client, app, editor_token, author_user_token, author_slug):
    slug = _create_draft(client, author_user_token, author_slug)
    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(author_user_token))
    client.patch(f"/api/v1/admin/notifications/1/read", headers=auth_headers(editor_token))  # noise, ignore result

    approve = client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(editor_token))
    assert approve.status_code == 200

    author_items = client.get("/api/v1/admin/notifications", headers=auth_headers(author_user_token)).get_json()["data"]
    approved = [n for n in author_items if n["notification_type"] == "article_approved"]
    assert len(approved) == 1

    editor_items = client.get("/api/v1/admin/notifications", headers=auth_headers(editor_token)).get_json()["data"]
    self_approved = [n for n in editor_items if n["notification_type"] == "article_approved"]
    assert len(self_approved) == 0


# ---------------------------------------------------------------------------
# Public submission integrations (Nomination / Contact / Directory / Mentorship / Partnership)
# ---------------------------------------------------------------------------


def test_nomination_received_notifies_nominations_manager(client, app):
    token, _ = _register_and_login(client, app, "notif-nominations-mgr@example.com", "nominations_manager")
    resp = client.post(
        "/api/v1/nominations",
        json=_nomination_payload("fictional-nominator@example.com"),
    )
    assert resp.status_code == 201
    items = client.get("/api/v1/admin/notifications", headers=auth_headers(token)).get_json()["data"]
    assert len(items) == 1
    assert items[0]["notification_type"] == "nomination_received"
    assert items[0]["entity_type"] == "nomination"


def test_contact_inquiry_notifies_contact_manager_without_full_message(client, app):
    token, _ = _register_and_login(client, app, "notif-contact-mgr@example.com", "moderator")
    resp = client.post(
        "/api/v1/contact",
        json={
            "firstName": "Fictional",
            "lastName": "Contact",
            "email": "fictional-contact@example.com",
            "inquiryType": "general",
            "subject": "A private subject line nobody else should see verbatim",
            "message": "A fictional private message body that must never be copied into a notification.",
            "privacyAcknowledged": True,
        },
    )
    assert resp.status_code == 201
    items = client.get("/api/v1/admin/notifications", headers=auth_headers(token)).get_json()["data"]
    assert len(items) == 1
    notif = items[0]
    assert notif["notification_type"] == "contact_inquiry_received"
    assert "private message body" not in notif["message"]
    assert "private subject line" not in notif["message"]


def test_directory_submission_notifies_directory_manager(client, app):
    token, _ = _register_and_login(client, app, "notif-directory-mgr@example.com", "directory_manager")
    resp = client.post(
        "/api/v1/directory/submit",
        json={
            "businessName": "Fictional Demo Business",
            "listingType": "business",
            "ownershipClassification": "women_led",
            "keyServices": ["Consulting"],
            "serviceModes": ["remote"],
            "categoryIds": [],
            "submitterName": "Fictional Submitter",
            "submitterEmail": "fictional-directory-submitter@example.com",
        },
    )
    assert resp.status_code == 201
    items = client.get("/api/v1/admin/notifications", headers=auth_headers(token)).get_json()["data"]
    assert len(items) == 1
    assert items[0]["notification_type"] == "directory_submission_received"


def test_mentorship_application_notifies_mentorship_manager(client, app):
    token, _ = _register_and_login(client, app, "notif-mentorship-mgr@example.com", "mentorship_manager")

    with app.app_context():
        from app.extensions import db
        from app.models.mentorship import MentorshipProgram

        program = MentorshipProgram(
            slug="fictional-mentorship-program-notif",
            name="Fictional Mentorship Program",
            status="applications_open",
            public_visible=True,
        )
        db.session.add(program)
        db.session.commit()
        program_id = program.id

    resp = client.post(
        "/api/v1/mentorship/applications",
        json={
            "programId": program_id,
            "role": "mentee",
            "email": "fictional-mentee@example.com",
            "firstName": "Fictional",
            "lastName": "Mentee",
            "countryCode": "KE",
            "goalsText": "A fictional goals statement long enough to pass validation for this test.",
            "consentGiven": True,
        },
    )
    assert resp.status_code == 201
    items = client.get("/api/v1/admin/notifications", headers=auth_headers(token)).get_json()["data"]
    assert len(items) == 1
    assert items[0]["notification_type"] == "mentorship_application_received"


def test_partnership_inquiry_notifies_partnerships_manager(client, app):
    token, _ = _register_and_login(client, app, "notif-partnerships-mgr@example.com", "partnerships_manager")
    resp = client.post(
        "/api/v1/partnerships/inquiries",
        json={
            "company": "Fictional Demo Partner Org",
            "contactName": "Fictional Contact",
            "email": "fictional-partnership@example.com",
            "partnershipType": "Brand Partnership",
            "message": "A fictional partnership inquiry message long enough to validate this test case.",
            "consentGiven": True,
        },
    )
    assert resp.status_code == 201
    items = client.get("/api/v1/admin/notifications", headers=auth_headers(token)).get_json()["data"]
    assert len(items) == 1
    assert items[0]["notification_type"] == "partnership_inquiry_received"


# ---------------------------------------------------------------------------
# Dedupe / idempotency
# ---------------------------------------------------------------------------


def test_calling_notify_helper_twice_for_same_entity_does_not_duplicate(client, app, submissions_manager_token):
    with app.app_context():
        from app.models.submissions import StorySubmission
        from app.services.notifications import notify_story_submission_received
        from datetime import datetime, timezone

        submission = StorySubmission(
            first_name="A",
            last_name="B",
            email="dedupe-test@example.com",
            country_code="KE",
            title="Dedupe Test Story",
            body="Fictional body.",
            story_type="personal_story",
            consent_review_given=True,
            consent_contact_given=True,
            consent_accuracy_confirmed=True,
            consent_recorded_at=datetime.now(timezone.utc),
        )
        from app.extensions import db
        db.session.add(submission)
        db.session.flush()
        submission.reference = f"WSF-STORY-DEDUPE-{submission.id}"
        db.session.commit()

        notify_story_submission_received(submission)
        notify_story_submission_received(submission)

    items = client.get("/api/v1/admin/notifications", headers=auth_headers(submissions_manager_token)).get_json()["data"]
    assert len(items) == 1


# ---------------------------------------------------------------------------
# Source entity missing/unavailable
# ---------------------------------------------------------------------------


def test_listing_does_not_crash_when_source_entity_deleted(client, app, submissions_manager_token):
    client.post(
        "/api/v1/submissions",
        json=_story_payload("source-missing-test@example.com", "Source Missing Test Story"),
    )
    with app.app_context():
        from app.extensions import db
        from app.models.submissions import StorySubmission

        submission = StorySubmission.query.filter_by(email="source-missing-test@example.com").first()
        db.session.delete(submission)
        db.session.commit()

    listing = client.get("/api/v1/admin/notifications", headers=auth_headers(submissions_manager_token))
    assert listing.status_code == 200
    assert len(listing.get_json()["data"]) == 1  # the notification row itself is untouched
