"""Newsletter consent provenance, resubscribe rules and no enumeration."""
from datetime import datetime, timezone


def _sub(app, email):
    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        return NewsletterSubscriber.query.filter_by(email=email).first()


def _set_status(app, email, status):
    from app.extensions import db
    from app.models.newsletter import NewsletterSubscriber

    with app.app_context():
        row = NewsletterSubscriber.query.filter_by(email=email).first()
        row.status = status
        if status == "unsubscribed":
            row.unsubscribed_at = datetime.now(timezone.utc)
        db.session.commit()


def _post(client, email, placement="newsletter-popup"):
    return client.post("/api/v1/newsletter/subscribe", json={"email": email, "placement": placement,
                                                              "acquisition": {"source": "direct"}})


def test_signup_records_consent_time_version_and_placement(client, app):
    resp = _post(client, "popup@example.com")
    assert resp.status_code == 201
    row = _sub(app, "popup@example.com")
    assert row.status == "active" and row.placement == "newsletter-popup"
    assert row.consent_version == "newsletter-v1" and row.consent_at is not None
    assert row.acquisition == {"source": "direct"}


def test_resubscribe_after_unsubscribe_gets_fresh_consent(client, app):
    _post(client, "back@example.com")
    first = _sub(app, "back@example.com").consent_at
    _set_status(app, "back@example.com", "unsubscribed")
    _post(client, "back@example.com", placement="jobs-listing")
    row = _sub(app, "back@example.com")
    assert row.status == "active" and row.unsubscribed_at is None
    assert row.consent_at > first and row.placement == "jobs-listing"


def test_bounced_and_complained_stay_suppressed(client, app):
    for status in ("bounced", "complained"):
        email = f"{status}@example.com"
        _post(client, email)
        before = _sub(app, email).consent_at
        _set_status(app, email, status)
        _post(client, email)
        row = _sub(app, email)
        assert row.status == status and row.consent_at == before  # no new consent recorded either


def test_response_never_reveals_list_state(client, app):
    _post(client, "known@example.com")
    _set_status(app, "known@example.com", "bounced")
    shapes = []
    for email in ("brand-new@example.com", "known@example.com"):
        resp = _post(client, email)
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        shapes.append((set(data), data["status"]))
    assert shapes[0] == shapes[1] == ({"email", "status", "subscribedAt"}, "subscribed")


def test_no_ip_or_browser_identity_stored():
    from app.models.newsletter import NewsletterSubscriber

    columns = set(NewsletterSubscriber.__table__.columns.keys())
    assert not any(k in columns for k in ("ip", "ip_address", "user_agent", "fingerprint"))


def test_checkbox_opt_in_records_its_own_version(app):
    from app.extensions import db
    from app.services.newsletter import upsert_subscriber

    with app.app_context():
        upsert_subscriber("box@example.com", placement="resource_download", consent_version="checkbox-opt-in-v1")
        db.session.commit()
    assert _sub(app, "box@example.com").consent_version == "checkbox-opt-in-v1"
