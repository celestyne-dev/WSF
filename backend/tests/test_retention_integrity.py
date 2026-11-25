"""Batch 4 corrections, Fixes 2, 4 and 5: unverified-account retention,
payment vs entitlement retention, deletion blockers, purge isolation,
erased-comment restoration, certificate name defaults."""
from unittest.mock import patch

from app.extensions import db
from app.models.circle import CirclePayment, CirclePlan, CircleSubscription
from app.models.user import User
from app.services import retention as svc
from tests.conftest import auth_headers
from tests.test_retention import NOW, _run, _user, ago


def _plan(slug="plan", **kw):
    plan = CirclePlan(name="P", slug=slug, price=10, currency="KES", status="active", billing_interval="monthly", **kw)
    db.session.add(plan)
    db.session.flush()
    return plan


def test_unverified_new_accounts_deleted_after_30_days_with_exclusions(app):
    with app.app_context():
        old = _user("old-unverified@example.invalid", created=ago(days=31))
        old.email_verification_required = True
        recent = _user("recent-unverified@example.invalid", created=ago(days=5))
        recent.email_verification_required = True
        staff = _user("staff-unverified@example.invalid", created=ago(days=60), role="editor")
        staff.email_verification_required = True
        paid = _user("paid-unverified@example.invalid", created=ago(days=60))
        paid.email_verification_required = True
        db.session.add(CircleSubscription(user_id=paid.id, plan_id=_plan().id, status="expired", source="manual"))
        verified = _user("verified@example.invalid", created=ago(days=60))
        verified.email_verification_required, verified.email_verified_at = True, ago(days=59)
        db.session.commit()
    assert _run(app)["unverified_accounts"] == 1
    with app.app_context():
        left = {u.email for u in User.query.all()}
        assert "old-unverified@example.invalid" not in left
        assert {"recent-unverified@example.invalid", "staff-unverified@example.invalid",
                "paid-unverified@example.invalid", "verified@example.invalid"} <= left


def test_old_payments_go_but_entitlements_stay(app):
    from app.models.resource import Resource, ResourcePurchase

    with app.app_context():
        u = _user("buyer@example.invalid", created=ago(days=8 * 365), last_login=ago(days=1))
        plan = _plan()
        active = CircleSubscription(user_id=u.id, plan_id=plan.id, status="active", source="manual",
                                    payment_reference="REF-A", created_at=ago(days=7 * 365))
        ended = CircleSubscription(user_id=None, plan_id=plan.id, status="expired", source="manual",
                                   provider_customer_id="CUS", payment_reference="REF-E",
                                   ended_at=ago(days=7 * 365), created_at=ago(days=8 * 365))
        res = Resource(name="Toolkit", slug="toolkit", status="published")
        db.session.add_all([active, ended, res])
        db.session.flush()
        purchase = ResourcePurchase(user_id=u.id, resource_id=res.id, payment_reference="OLD-R",
                                    purchased_at=ago(days=7 * 365))
        db.session.add(purchase)
        db.session.add(CirclePayment(reference="OLD-C", plan_id=plan.id, amount_subunits=1000, currency="KES",
                                     billing_interval="monthly", customer_email="buyer@example.invalid",
                                     status="verified", created_at=ago(days=7 * 365)))
        db.session.commit()
        ids = (active.id, ended.id, purchase.id)
    _run(app)
    with app.app_context():
        a, e, p = (db.session.get(CircleSubscription, ids[0]), db.session.get(CircleSubscription, ids[1]),
                   db.session.get(ResourcePurchase, ids[2]))
        assert CirclePayment.query.count() == 0                      # accounting record past 6 years
        assert a is not None and a.status == "active" and a.payment_reference == "REF-A"  # live entitlement untouched
        assert p is not None                                          # permanent purchase untouched
        assert e is not None and e.provider_customer_id is None and e.payment_reference is None  # minimised only


def _externally_billed_member(app, email):
    with app.app_context():
        u = _user(email, created=ago(days=4 * 365), last_login=ago(days=4 * 365))
        db.session.add(CircleSubscription(user_id=u.id, plan_id=_plan(slug=email[:5]).id, status="past_due",
                                          source="manual", provider_subscription_id="SUB-EXT"))
        db.session.commit()
        return u.id


def test_external_recurring_billing_blocks_automatic_deletion(app, client):
    uid = _externally_billed_member(app, "recurring@example.invalid")
    from app.services.account_privacy import deletion_blockers

    with app.app_context():
        assert "external_recurring_billing" in deletion_blockers(db.session.get(User, uid))
        assert uid not in {u.id for u in svc._inactive_candidates()}
    token = client.post("/api/v1/auth/login", json={"email": "recurring@example.invalid",
                                                    "password": "supersecret1"}).get_json()["data"]["access_token"]
    with patch("app.services.email.send_email", return_value=True):
        res = client.post("/api/v1/account/deletion", headers=auth_headers(token), json={"password": "supersecret1"})
    assert res.status_code == 409 and res.get_json()["error"]["code"] == "deletion_needs_review"
    with app.app_context():
        from app.models.privacy import PrivacyRequest

        assert db.session.get(User, uid).deletion_scheduled_for is None
        assert PrivacyRequest.query.filter_by(user_id=uid, request_type="deletion", status="open").count() == 1


def test_one_failing_purge_does_not_stop_others(app):
    with app.app_context():
        for email in ("bad@example.invalid", "good@example.invalid"):
            u = _user(email, created=ago(days=31))
            u.email_verification_required = True
        db.session.commit()
    real = svc.__dict__.get("_purge_one")
    from app.services import account_privacy

    original = account_privacy.purge_user

    def flaky(user):
        if user.email.startswith("bad"):
            raise RuntimeError("boom")
        return original(user)

    with patch("app.services.account_privacy.purge_user", side_effect=flaky):
        result = _run(app)
    assert real is not None and result["unverified_accounts"] == 1
    assert all(v != "error" for v in result.values())
    with app.app_context():
        assert {u.email for u in User.query.all()} >= {"bad@example.invalid"}
        assert User.query.filter_by(email="good@example.invalid").count() == 0


def test_erased_removed_comment_cannot_be_restored(app):
    from app.models.article import Article
    from app.models.comment import Comment
    from app.models.people import Author
    from app.services.comments import CommentError, approve_comment

    with app.app_context():
        mod = _user("mod@example.invalid", role="moderator")
        author = Author(name="A", slug="a")
        db.session.add(author)
        db.session.flush()
        art = Article(title="T", slug="t", status="published", content=[], author_id=author.id)
        db.session.add(art)
        db.session.flush()
        c = Comment(article_id=art.id, user_id=mod.id, body="x", status="removed", removed_at=ago(days=400),
                    held_reasons=[])
        db.session.add(c)
        db.session.commit()
        svc.run_retention(now=NOW)
        c = db.session.get(Comment, c.id)
        assert c.body is None
        try:
            approve_comment(mod, c)
            raise AssertionError("restored an erased comment")
        except CommentError as exc:
            assert exc.code == "comment_body_erased"
        assert db.session.get(Comment, c.id).status == "removed"


def test_certificate_name_defaults(app, client):
    client.post("/api/v1/auth/register", json={"email": "fresh@example.invalid", "password": "supersecret1",
                                                "first_name": "F", "last_name": "R"})
    with app.app_context():
        assert User.query.filter_by(email="fresh@example.invalid").one().certificate_public_name == "initials"
        # A row that predates the setting (inserted without the column) keeps "full".
        db.session.execute(db.text("INSERT INTO users (uuid, email, password_hash, first_name, last_name, is_active, "
                                   "is_verified, must_change_password, auth_version, created_at, updated_at) VALUES "
                                   "('00000000-0000-0000-0000-000000000001', 'old@example.invalid', 'x', 'O', 'L', true, "
                                   "false, false, 0, now(), now())"))
        db.session.commit()
        assert User.query.filter_by(email="old@example.invalid").one().certificate_public_name == "full"
