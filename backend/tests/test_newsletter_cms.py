import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "newsletter-manager@example.com",
    "password": "supersecret1",
    "first_name": "Naliaka",
    "last_name": "Wafula",
    "country_code": "US",
}

ADMIN_PAYLOAD = {
    "email": "newsletter-admin@example.com",
    "password": "supersecret1",
    "first_name": "Site",
    "last_name": "Admin",
    "country_code": "US",
}

NO_PERMISSION_PAYLOAD = {
    "email": "newsletter-nobody@example.com",
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
    """A newsletter_manager — full CMS access but NOT subscriber export."""
    return _register_with_role(client, app, MANAGER_PAYLOAD, "newsletter_manager")


@pytest.fixture()
def admin_token(client, app):
    """A full admin — has newsletter.manage AND newsletter.export."""
    return _register_with_role(client, app, ADMIN_PAYLOAD, "admin")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


def _make_topic(app, slug="careers", name="Career"):
    from app.extensions import db
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic.query.filter_by(slug=slug).first()
        if topic is None:
            topic = Topic(slug=slug, name=name)
            db.session.add(topic)
            db.session.commit()
        return topic.slug


def _set_subscriber_status(app, email, status):
    from app.extensions import db
    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
        subscriber.status = status
        db.session.commit()


def _base_issue_payload(**overrides):
    payload = {
        "title": "Issue 60 internal",
        "subject": "The comeback nobody scripted",
        "preheader": "A great issue this week.",
        "content": [{"type": "paragraph", "text": "Hello subscribers."}],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Public subscribe / unsubscribe / resubscribe
# ---------------------------------------------------------------------------


def test_subscribe_creates_subscriber_with_consent_fields(client):
    resp = client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "reader@example.com", "firstName": "Reader", "placement": "footer"},
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["email"] == "reader@example.com"
    assert data["status"] == "active"
    assert data["subscribedAt"]
    # Public response is a privacy-trimmed confirmation, not the full record.
    assert set(data.keys()) == {"email", "status", "subscribedAt"}


def test_subscribe_invalid_email_rejected(client):
    resp = client.post("/api/v1/newsletter/subscribe", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_duplicate_subscribe_is_case_insensitive_and_does_not_duplicate(client, app):
    first = client.post("/api/v1/newsletter/subscribe", json={"email": "Person@Example.COM"})
    assert first.status_code == 201
    second = client.post("/api/v1/newsletter/subscribe", json={"email": "person@example.com", "firstName": "Later"})
    assert second.status_code == 201

    from app.extensions import db
    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        matches = NewsletterSubscriber.query.filter_by(email="person@example.com").all()
        assert len(matches) == 1
        assert matches[0].first_name == "Later"


def test_unsubscribe_by_email_preserves_record_and_sets_timestamp(client, app):
    client.post("/api/v1/newsletter/subscribe", json={"email": "leaving@example.com"})
    resp = client.post("/api/v1/newsletter/unsubscribe", json={"email": "leaving@example.com"})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "unsubscribed"

    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        subscriber = NewsletterSubscriber.query.filter_by(email="leaving@example.com").first()
        assert subscriber is not None
        assert subscriber.status == "unsubscribed"
        assert subscriber.unsubscribed_at is not None


def test_unsubscribe_unknown_email_returns_404(client):
    resp = client.post("/api/v1/newsletter/unsubscribe", json={"email": "never-subscribed@example.com"})
    assert resp.status_code == 404


def test_unsubscribe_by_token_works_and_is_idempotent(client, app):
    client.post("/api/v1/newsletter/subscribe", json={"email": "tokenflow@example.com"})

    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        token = NewsletterSubscriber.query.filter_by(email="tokenflow@example.com").first().unsubscribe_token

    first = client.get(f"/api/v1/newsletter/unsubscribe/{token}")
    assert first.status_code == 200
    assert first.get_json()["data"]["status"] == "unsubscribed"

    # A second click on the same link is a harmless no-op, not an error.
    second = client.get(f"/api/v1/newsletter/unsubscribe/{token}")
    assert second.status_code == 200
    assert second.get_json()["data"]["status"] == "unsubscribed"


def test_unsubscribe_by_invalid_token_returns_404_not_a_raw_db_error(client):
    resp = client.get("/api/v1/newsletter/unsubscribe/not-a-real-token")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "not_found"


def test_explicit_resubscribe_reactivates_unsubscribed_address(client, app):
    client.post("/api/v1/newsletter/subscribe", json={"email": "comeback@example.com"})
    client.post("/api/v1/newsletter/unsubscribe", json={"email": "comeback@example.com"})

    resp = client.post("/api/v1/newsletter/subscribe", json={"email": "comeback@example.com"})
    assert resp.status_code == 201
    assert resp.get_json()["data"]["status"] == "active"

    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        subscriber = NewsletterSubscriber.query.filter_by(email="comeback@example.com").first()
        assert subscriber.unsubscribed_at is None


def test_ordinary_subscribe_does_not_reactivate_bounced_address(client, app):
    client.post("/api/v1/newsletter/subscribe", json={"email": "bounced@example.com"})
    _set_subscriber_status(app, "bounced@example.com", "bounced")

    resp = client.post("/api/v1/newsletter/subscribe", json={"email": "bounced@example.com"})
    assert resp.status_code == 201

    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        subscriber = NewsletterSubscriber.query.filter_by(email="bounced@example.com").first()
        assert subscriber.status == "bounced"


def test_subscribe_with_interests(client, app):
    topic_slug = _make_topic(app)
    resp = client.post(
        "/api/v1/newsletter/subscribe", json={"email": "curious@example.com", "topicSlugs": [topic_slug]}
    )
    assert resp.status_code == 201

    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        subscriber = NewsletterSubscriber.query.filter_by(email="curious@example.com").first()
        assert [t.slug for t in subscriber.interests] == [topic_slug]


# ---------------------------------------------------------------------------
# Admin subscriber management
# ---------------------------------------------------------------------------


def test_subscriber_list_requires_permission(client, no_permission_token):
    resp = client.get("/api/v1/newsletter/subscribers", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_subscriber_list_requires_authentication(client):
    resp = client.get("/api/v1/newsletter/subscribers")
    assert resp.status_code == 401


def test_subscriber_list_and_filters(client, manager_token):
    client.post("/api/v1/newsletter/subscribe", json={"email": "active-one@example.com"})
    client.post("/api/v1/newsletter/subscribe", json={"email": "will-leave@example.com"})
    client.post("/api/v1/newsletter/unsubscribe", json={"email": "will-leave@example.com"})

    all_resp = client.get("/api/v1/newsletter/subscribers", headers=auth_headers(manager_token))
    emails = {s["email"] for s in all_resp.get_json()["data"]}
    assert "active-one@example.com" in emails
    assert "will-leave@example.com" in emails

    unsub_resp = client.get("/api/v1/newsletter/subscribers?status=unsubscribed", headers=auth_headers(manager_token))
    unsub_emails = {s["email"] for s in unsub_resp.get_json()["data"]}
    assert unsub_emails == {"will-leave@example.com"}

    search_resp = client.get("/api/v1/newsletter/subscribers?q=active-one", headers=auth_headers(manager_token))
    assert {s["email"] for s in search_resp.get_json()["data"]} == {"active-one@example.com"}


def test_subscriber_dump_never_includes_unsubscribe_token(client, manager_token):
    client.post("/api/v1/newsletter/subscribe", json={"email": "notoken@example.com"})
    resp = client.get("/api/v1/newsletter/subscribers?q=notoken", headers=auth_headers(manager_token))
    row = resp.get_json()["data"][0]
    assert "unsubscribe_token" not in row


def test_admin_can_update_voluntary_subscriber_fields(client, app, manager_token):
    client.post("/api/v1/newsletter/subscribe", json={"email": "editable@example.com"})
    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        subscriber_id = NewsletterSubscriber.query.filter_by(email="editable@example.com").first().id

    resp = client.patch(
        f"/api/v1/newsletter/subscribers/{subscriber_id}",
        json={"firstName": "Updated", "lastName": "Name"},
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["first_name"] == "Updated"
    assert resp.get_json()["data"]["last_name"] == "Name"


def test_admin_suppress_and_reactivate_subscriber(client, app, manager_token):
    client.post("/api/v1/newsletter/subscribe", json={"email": "manual-suppress@example.com"})
    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        subscriber_id = NewsletterSubscriber.query.filter_by(email="manual-suppress@example.com").first().id

    suppress_resp = client.post(
        f"/api/v1/newsletter/subscribers/{subscriber_id}/suppress", headers=auth_headers(manager_token)
    )
    assert suppress_resp.status_code == 200
    assert suppress_resp.get_json()["data"]["status"] == "unsubscribed"

    # A deliberate admin reactivation is allowed even from a suppressed state.
    _set_subscriber_status(app, "manual-suppress@example.com", "complained")
    reactivate_resp = client.post(
        f"/api/v1/newsletter/subscribers/{subscriber_id}/reactivate", headers=auth_headers(manager_token)
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.get_json()["data"]["status"] == "active"


def test_subscriber_export_requires_stricter_permission_than_manage(client, manager_token, admin_token):
    client.post("/api/v1/newsletter/subscribe", json={"email": "exportable@example.com"})

    denied = client.get("/api/v1/newsletter/subscribers/export", headers=auth_headers(manager_token))
    assert denied.status_code == 403

    allowed = client.get("/api/v1/newsletter/subscribers/export", headers=auth_headers(admin_token))
    assert allowed.status_code == 200
    assert allowed.headers["Content-Type"].startswith("text/csv")
    assert "exportable@example.com" in allowed.get_data(as_text=True)
    assert "unsubscribe_token" not in allowed.get_data(as_text=True).lower()


# ---------------------------------------------------------------------------
# Newsletter issues / campaigns
# ---------------------------------------------------------------------------


def test_issue_create_requires_permission(client):
    resp = client.post("/api/v1/newsletter/issues", json=_base_issue_payload())
    assert resp.status_code in (401, 403)


def test_issue_create_and_update_persists_structured_content(client, manager_token):
    create = client.post("/api/v1/newsletter/issues", json=_base_issue_payload(), headers=auth_headers(manager_token))
    assert create.status_code == 201
    issue = create.get_json()["data"]
    assert issue["status"] == "draft"
    assert issue["content"] == [{"type": "paragraph", "text": "Hello subscribers."}]

    blocks = [
        {"type": "heading", "level": 2, "text": "This week"},
        {"type": "paragraph", "text": "A story worth your time."},
        {"type": "button", "label": "Read more", "url": "https://example.com/article"},
    ]
    update = client.put(
        f"/api/v1/newsletter/issues/{issue['slug']}",
        json=_base_issue_payload(content=blocks, title="Issue 60 revised"),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["content"] == blocks
    assert update.get_json()["data"]["title"] == "Issue 60 revised"

    reopened = client.get(f"/api/v1/newsletter/issues/{issue['slug']}", headers=auth_headers(manager_token))
    assert reopened.get_json()["data"]["content"] == blocks


def test_issue_featured_article_relationship(client, app, manager_token):
    from app.extensions import db
    from app.models.article import Article
    from app.models.people import Author
    from app.services.slugs import generate_unique_slug

    with app.app_context():
        author = Author(slug="test-author", name="Test Author")
        db.session.add(author)
        db.session.flush()
        article = Article(title="A Story Worth Reading", status="published", content=[], author_id=author.id)
        article.slug = generate_unique_slug(Article, article.title)
        db.session.add(article)
        db.session.commit()
        article_slug = article.slug

    resp = client.post(
        "/api/v1/newsletter/issues",
        json=_base_issue_payload(featuredArticleSlug=article_slug),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["featured_article"]["slug"] == article_slug


def test_issue_unknown_featured_article_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/newsletter/issues",
        json=_base_issue_payload(featuredArticleSlug="does-not-exist"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 404


def test_issue_status_cannot_be_set_to_sent_via_generic_save(client, manager_token):
    resp = client.post(
        "/api/v1/newsletter/issues", json=_base_issue_payload(status="sent"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_issue_scheduled_requires_content_subject_and_scheduled_at(client, manager_token):
    resp = client.post(
        "/api/v1/newsletter/issues",
        json=_base_issue_payload(status="scheduled", content=[]),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422

    resp2 = client.post(
        "/api/v1/newsletter/issues",
        json=_base_issue_payload(status="scheduled"),
        headers=auth_headers(manager_token),
    )
    assert resp2.status_code == 422  # missing scheduled_at

    resp3 = client.post(
        "/api/v1/newsletter/issues",
        json=_base_issue_payload(status="scheduled", scheduledAt="2026-12-01T09:00:00+00:00"),
        headers=auth_headers(manager_token),
    )
    assert resp3.status_code == 201
    assert resp3.get_json()["data"]["status"] == "scheduled"


def test_audience_estimate_reflects_active_subscribers(client, app, manager_token):
    topic_slug = _make_topic(app, slug="leadership", name="Leadership")
    client.post("/api/v1/newsletter/subscribe", json={"email": "leader1@example.com", "topicSlugs": [topic_slug]})
    client.post("/api/v1/newsletter/subscribe", json={"email": "generalist@example.com"})

    all_active = client.post(
        "/api/v1/newsletter/audience-estimate", json={}, headers=auth_headers(manager_token)
    )
    assert all_active.status_code == 200
    assert all_active.get_json()["data"]["estimatedRecipients"] == 2

    filtered = client.post(
        "/api/v1/newsletter/audience-estimate",
        json={"audienceFilter": {"topicSlugs": [topic_slug]}},
        headers=auth_headers(manager_token),
    )
    assert filtered.get_json()["data"]["estimatedRecipients"] == 1


def test_mark_sent_is_explicit_and_honest(client, manager_token):
    create = client.post("/api/v1/newsletter/issues", json=_base_issue_payload(), headers=auth_headers(manager_token))
    slug = create.get_json()["data"]["slug"]
    assert create.get_json()["data"]["sent_at"] is None

    mark = client.post(f"/api/v1/newsletter/issues/{slug}/mark-sent", headers=auth_headers(manager_token))
    assert mark.status_code == 200
    assert mark.get_json()["data"]["status"] == "sent"
    assert mark.get_json()["data"]["sent_at"] is not None

    again = client.post(f"/api/v1/newsletter/issues/{slug}/mark-sent", headers=auth_headers(manager_token))
    assert again.status_code == 409


def test_mark_sent_requires_content(client, manager_token):
    create = client.post(
        "/api/v1/newsletter/issues", json=_base_issue_payload(content=[]), headers=auth_headers(manager_token)
    )
    slug = create.get_json()["data"]["slug"]
    resp = client.post(f"/api/v1/newsletter/issues/{slug}/mark-sent", headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_archive_issue(client, manager_token):
    create = client.post("/api/v1/newsletter/issues", json=_base_issue_payload(), headers=auth_headers(manager_token))
    slug = create.get_json()["data"]["slug"]
    resp = client.post(f"/api/v1/newsletter/issues/{slug}/archive", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "archived"


def test_public_archive_only_shows_sent_issues(client, manager_token):
    draft = client.post(
        "/api/v1/newsletter/issues", json=_base_issue_payload(title="Draft One"), headers=auth_headers(manager_token)
    ).get_json()["data"]
    to_send = client.post(
        "/api/v1/newsletter/issues", json=_base_issue_payload(title="Sent One", subject="Sent subject"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    client.post(f"/api/v1/newsletter/issues/{to_send['slug']}/mark-sent", headers=auth_headers(manager_token))

    public_list = client.get("/api/v1/newsletter/issues")
    subjects = {i["subject"] for i in public_list.get_json()["data"]}
    assert "Sent subject" in subjects
    assert "The comeback nobody scripted" not in subjects or draft["subject"] not in subjects

    draft_detail = client.get(f"/api/v1/newsletter/issues/{draft['slug']}")
    assert draft_detail.status_code == 404

    sent_detail = client.get(f"/api/v1/newsletter/issues/{to_send['slug']}")
    assert sent_detail.status_code == 200
    # Public serializer excludes internal-only fields.
    assert "title" not in sent_detail.get_json()["data"]
    assert "status" not in sent_detail.get_json()["data"]
    assert "audience_filter" not in sent_detail.get_json()["data"]


def test_draft_issue_visible_to_editor_via_detail(client, manager_token):
    create = client.post("/api/v1/newsletter/issues", json=_base_issue_payload(), headers=auth_headers(manager_token))
    slug = create.get_json()["data"]["slug"]
    resp = client.get(f"/api/v1/newsletter/issues/{slug}", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "draft"


def test_overview_requires_permission_and_reports_real_counts(client, manager_token):
    denied = client.get("/api/v1/newsletter/overview")
    assert denied.status_code == 401

    client.post("/api/v1/newsletter/subscribe", json={"email": "count-me@example.com"})
    client.post("/api/v1/newsletter/issues", json=_base_issue_payload(), headers=auth_headers(manager_token))

    resp = client.get("/api/v1/newsletter/overview", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["activeSubscribers"] >= 1
    assert data["draftIssues"] >= 1
