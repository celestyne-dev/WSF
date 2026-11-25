"""Batch 4 corrections, Fix 3: newsletter suppression and data integrity."""
from unittest.mock import patch

from app.extensions import db
from app.models.newsletter import NewsletterConfirmation, NewsletterSubscriber
from app.models.taxonomy import Topic
from tests.test_newsletter_doi import _confirm, _events, _row, _signup, admin, outbox  # noqa: F401

EMAIL = "reader@example.invalid"


def _import(client, admin, kind="unsubscribed", email=EMAIL):  # noqa: F811
    return client.post("/api/v1/newsletter/subscribers/suppression-import", headers=admin,
                       json={"provider": "External Service", "csv": f"email\n{email}\n", "kind": kind})


def _unsubscribe(client, app):
    token = _row(app, EMAIL).unsubscribe_token
    assert client.get(f"/api/v1/newsletter/unsubscribe/{token}").status_code == 200


def test_external_suppression_beats_an_earlier_confirmation_link(client, app, admin, outbox):  # noqa: F811
    _signup(client, EMAIL)
    assert _confirm(client, outbox.token()).status_code == 200
    _unsubscribe(client, app)                                   # 1. unsubscribes
    with app.app_context():                                     # (outside the 10-minute resend window)
        NewsletterConfirmation.query.update({"created_at": NewsletterConfirmation.created_at - db.text("interval '1 hour'")},
                                            synchronize_session=False)
        db.session.commit()
    _signup(client, EMAIL)                                      # 2. requests fresh confirmation
    fresh = outbox.token()
    assert _import(client, admin).status_code == 200            # 3. external suppression (already suppressed)
    res = _confirm(client, fresh)                               # 4. earlier link used
    assert res.status_code == 404
    assert _row(app, EMAIL).status == "unsubscribed"            # 5. stays suppressed
    with app.app_context():
        assert NewsletterConfirmation.query.filter_by(confirmed_at=None, superseded_at=None).count() == 0


def test_signup_never_overwrites_an_existing_subscriber_profile(client, app, outbox):  # noqa: F811
    with app.app_context():
        db.session.add(Topic(name="Leadership", slug="leadership"))
        db.session.commit()
    _signup(client, EMAIL, firstName="Real", lastName="Owner")
    _confirm(client, outbox.token())
    _signup(client, EMAIL, firstName="Impostor", lastName="X", topicSlugs=["leadership"])  # active: ignored
    row = _row(app, EMAIL)
    assert (row.first_name, row.last_name) == ("Real", "Owner")
    with app.app_context():
        assert NewsletterSubscriber.query.filter_by(email=EMAIL).one().interests == []
    # A pending address: details are held until the link is confirmed.
    _signup(client, "pending@example.invalid", firstName="Held")
    assert _row(app, "pending@example.invalid").first_name is None
    _confirm(client, outbox.token())
    assert _row(app, "pending@example.invalid").first_name == "Held"


def test_hard_bounce_needs_consent_confirmation_and_review(client, app, admin, outbox):  # noqa: F811
    _signup(client, EMAIL)
    _confirm(client, outbox.token())
    assert _import(client, admin, kind="bounced").status_code == 200
    assert _row(app, EMAIL).status == "bounced"
    sid = _row(app, EMAIL).id
    review = f"/api/v1/newsletter/subscribers/{sid}/deliverability-review"
    # Staff approval alone never substitutes for the person's consent.
    res = client.post(review, headers=admin, json={"note": "Mailbox checked"})
    assert res.status_code == 409 and res.get_json()["error"]["code"] == "consent_confirmation_required"
    _signup(client, EMAIL)
    res = _confirm(client, outbox.token())
    assert res.get_json()["data"]["result"] == "review_required"
    assert _row(app, EMAIL).status == "bounced"
    assert client.post(review, headers=admin, json={"note": ""}).status_code == 422  # review must be described
    assert client.post(review, headers=admin, json={"note": "Mailbox checked"}).status_code == 200
    assert _row(app, EMAIL).status == "active"
    assert "deliverability_review_approved" in _events(app, EMAIL)
    # Direct admin reactivation stays disabled.
    assert client.post(f"/api/v1/newsletter/subscribers/{sid}/reactivate", headers=admin).status_code == 409


def test_complaint_after_confirmation_voids_the_pending_review(client, app, admin, outbox):  # noqa: F811
    _signup(client, EMAIL)
    _confirm(client, outbox.token())
    _import(client, admin, kind="bounced")
    _signup(client, EMAIL)
    _confirm(client, outbox.token())                            # confirmed, awaiting review
    _import(client, admin, kind="complained")                   # a newer suppression event
    sid = _row(app, EMAIL).id
    res = client.post(f"/api/v1/newsletter/subscribers/{sid}/deliverability-review", headers=admin,
                      json={"note": "checked"})
    assert res.status_code == 409 and _row(app, EMAIL).status == "complained"


def test_confirmation_send_failure_is_truthful(client, app):
    with patch("app.services.email.send_email", return_value=False):
        res = _signup(client, EMAIL)
    assert res.status_code == 503 and res.get_json()["error"]["code"] == "email_send_failed"
    with app.app_context():
        assert NewsletterConfirmation.query.filter_by(superseded_at=None).count() == 0
    with patch("app.services.email.send_email", return_value=True):
        assert _signup(client, EMAIL).status_code == 201  # retry allowed straight away


def test_confirm_page_needs_an_intentional_action():
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[2].joinpath("frontend/src/pages/NewsletterConfirmPage.jsx").read_text()
    assert "useEffect" not in src and "onClick={confirm}" in src
