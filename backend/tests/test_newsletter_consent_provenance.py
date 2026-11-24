"""Newsletter consent provenance, suppression rules and no enumeration
(double opt-in, Step 14)."""
import re
from datetime import datetime, timezone
from unittest.mock import patch


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


def _post(client, email, placement="newsletter-popup", consent=True):
    """Sign up; returns (response, confirmation link token or None)."""
    sent = []
    with patch("app.services.email.send_email", side_effect=lambda to, s, t, *a, **k: sent.append(t) or True):
        resp = client.post("/api/v1/newsletter/subscribe", json={"email": email, "placement": placement,
                                                                  "consent": consent,
                                                                  "acquisition": {"source": "direct"}})
    token = re.search(r"/newsletter/confirm/(\S+)", sent[-1]).group(1) if sent else None
    return resp, token


def _confirm(client, token):
    return client.post("/api/v1/newsletter/confirm", json={"token": token})


def test_consent_and_confirmation_are_recorded(client, app):
    resp, token = _post(client, "popup@example.com")
    assert resp.status_code == 201
    row = _sub(app, "popup@example.com")
    assert row.status == "pending" and row.confirmed_at is None and row.consent_at is None
    assert _confirm(client, token).status_code == 200
    row = _sub(app, "popup@example.com")
    assert row.status == "active" and row.confirmed_at is not None and row.placement == "newsletter-popup"
    assert row.consent_version == "newsletter-v2" and row.consent_at is not None
    assert row.consent_source == "newsletter-popup" and row.acquisition == {"source": "direct"}


def test_resubscribe_after_unsubscribe_needs_fresh_confirmation(client, app):
    _, token = _post(client, "back@example.com")
    _confirm(client, token)
    first = _sub(app, "back@example.com").consent_at
    _set_status(app, "back@example.com", "unsubscribed")
    _, token = _post(client, "back@example.com", placement="jobs-listing")
    assert _sub(app, "back@example.com").status == "unsubscribed"
    _confirm(client, token)
    row = _sub(app, "back@example.com")
    assert row.status == "active" and row.unsubscribed_at is None
    assert row.consent_at > first and row.consent_source == "jobs-listing"


def test_bounced_and_complained_stay_suppressed_without_confirmation(client, app):
    for status in ("bounced", "complained"):
        email = f"{status}@example.com"
        _, token = _post(client, email)
        _confirm(client, token)
        before = _sub(app, email).consent_at
        _set_status(app, email, status)
        _post(client, email)
        row = _sub(app, email)
        assert row.status == status and row.consent_at == before  # nothing changes until they click


def test_response_never_reveals_list_state(client, app):
    _, token = _post(client, "known@example.com")
    _confirm(client, token)
    _post(client, "suppressed@example.com")
    _set_status(app, "suppressed@example.com", "bounced")
    shapes = []
    for email in ("brand-new@example.com", "known@example.com", "suppressed@example.com"):
        resp, _ = _post(client, email)
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        shapes.append((set(data), data["status"]))
    assert shapes[0] == shapes[1] == shapes[2] == ({"email", "status"}, "confirmation_required")


def test_no_ip_or_browser_identity_stored():
    from app.models.newsletter import NewsletterConfirmation, NewsletterSubscriber, NewsletterSubscriberEvent

    for model in (NewsletterSubscriber, NewsletterConfirmation, NewsletterSubscriberEvent):
        columns = set(model.__table__.columns.keys())
        assert not any(k in columns for k in ("ip", "ip_address", "user_agent", "fingerprint"))


def test_checkbox_opt_in_records_its_own_version(client, app):
    from app.extensions import db
    from app.services.newsletter import request_subscription

    sent = []
    with app.app_context(), patch("app.services.email.send_email",
                                  side_effect=lambda to, s, t, *a, **k: sent.append(t) or True):
        request_subscription("box@example.com", placement="resource_download", consent_version="checkbox-opt-in-v1")
        db.session.commit()
    assert _sub(app, "box@example.com").status == "pending"
    _confirm(client, re.search(r"/newsletter/confirm/(\S+)", sent[-1]).group(1))
    row = _sub(app, "box@example.com")
    assert row.consent_version == "checkbox-opt-in-v1" and row.consent_source == "resource_download"
