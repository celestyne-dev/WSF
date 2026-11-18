"""WSF Circle Lifetime membership: a first-class `lifetime` billing interval
on the existing CirclePlan / CircleSubscription / CirclePayment
architecture — one Paystack transaction, no renewal, NULL period end,
yearly-level benefits, idempotent activation, duplicate-purchase
protection, revocation, and unchanged monthly/yearly behaviour.
Paystack is always mocked; nothing makes a real network call."""
import hashlib
import hmac
import importlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from app.extensions import db
from tests.conftest import auth_headers

_SECRET = "sk_test_lifetimesecret"
_WEBHOOK_URL = "/api/v1/webhooks/paystack"
USER = {"email": "lifetime-member@example.com", "password": "supersecret1", "first_name": "Wanjiru", "last_name": "Kamau"}
ADMIN = {"email": "lifetime-admin@example.com", "password": "supersecret1", "first_name": "Ada", "last_name": "Admin"}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    return client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]


@pytest.fixture()
def user_token(client):
    return _register(client, USER)


@pytest.fixture()
def admin_headers(client, app):
    from app.models.user import Role, User

    token = _register(client, ADMIN)
    with app.app_context():
        user = User.query.filter_by(email=ADMIN["email"]).first()
        user.roles.append(Role.query.filter_by(name="admin").first())
        db.session.commit()
    token = client.post("/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}).get_json()["data"]["access_token"]
    return auth_headers(token)


def _enable_paystack(app, currencies=("USD", "KES")):
    app.config["PAYSTACK_ENABLED"] = True
    app.config["PAYSTACK_SECRET_KEY"] = _SECRET
    app.config["PAYSTACK_ALLOWED_CURRENCIES"] = list(currencies)


def _user(app, email=USER["email"]):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first()


def _plan(app, interval="lifetime", prices=(("USD", 29900),), **extra):
    from app.models.circle import CirclePlan, CirclePlanPrice

    with app.app_context():
        plan = CirclePlan(slug=f"plan-{uuid.uuid4().hex[:8]}", name=f"WSF Circle {interval.title()}", billing_interval=interval,
                          price=0, currency=prices[0][0] if prices else "USD", status="active", **extra)
        for currency, minor in prices:
            plan.prices.append(CirclePlanPrice(currency=currency, amount_minor=minor, enabled=True))
        db.session.add(plan)
        db.session.commit()
        return plan.id, plan.slug


def _subscription(app, user_id, plan_id, **fields):
    from app.models.circle import CircleSubscription

    defaults = dict(status="active", source="manual", starts_at=datetime.now(timezone.utc) - timedelta(days=1))
    defaults.update(fields)
    with app.app_context():
        sub = CircleSubscription(user_id=user_id, plan_id=plan_id, **defaults)
        db.session.add(sub)
        db.session.commit()
        return sub.id


def _mock_init(**kwargs):
    return {"authorization_url": "https://checkout.paystack.com/x", "access_code": "x", "reference": kwargs["reference"]}


def _success(payment, **overrides):
    result = {"status": "success", "amount": payment.amount_subunits, "currency": payment.currency,
              "customer_email": payment.customer_email, "provider_transaction_id": str(uuid.uuid4().int)[:12],
              "channel": "card", "paid_at": "2026-11-01T10:00:00.000Z", "gateway_response": "Successful",
              "reference": payment.reference}
    result.update(overrides)
    return result


def _payment(app, reference):
    from app.models.circle import CirclePayment

    with app.app_context():
        return CirclePayment.query.filter_by(reference=reference).first()


def _checkout(client, token, slug, currency=None):
    body = {"currency": currency} if currency else {}
    with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as init:
        resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", json=body, headers=auth_headers(token))
    return resp, init


def _current(app, user_id):
    from app.models.circle import CircleSubscription

    with app.app_context():
        return CircleSubscription.query.filter(CircleSubscription.user_id == user_id,
                                               CircleSubscription.status.in_(("pending", "active", "past_due"))).first()


def _has_access(app, user_id, yearly=False):
    from app.models.user import User
    from app.services.circle import has_circle_access, has_yearly_circle_access

    with app.app_context():
        user = db.session.get(User, user_id)
        return has_yearly_circle_access(user) if yearly else has_circle_access(user)


def _buy_lifetime(client, app, token, slug, currency=None):
    resp, init = _checkout(client, token, slug, currency)
    assert resp.status_code in (200, 201), resp.get_json()
    reference = init.call_args.kwargs["reference"]
    payment = _payment(app, reference)
    with patch("app.services.circle_payments.verify_transaction", return_value=_success(payment)):
        status = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(token))
    return reference, init, status


# --- plans --------------------------------------------------------------------------


class TestLifetimePlans:
    def test_create_update_and_serialize_lifetime_plan(self, client, app, admin_headers):
        body = {"name": "Lifetime", "billingInterval": "lifetime", "currency": "USD", "status": "active",
                "prices": [{"currency": "USD", "amount": "299.00", "enabled": True}, {"currency": "KES", "amount": "35000", "enabled": True}],
                "benefits": ["Lifetime access to WSF Circle membership benefits."]}
        resp = client.post("/api/v1/circle/plans", json=body, headers=admin_headers)
        assert resp.status_code == 201, resp.get_json()
        slug = resp.get_json()["data"]["slug"]
        assert resp.get_json()["data"]["billing_interval"] == "lifetime"
        assert {p["currency"] for p in resp.get_json()["data"]["prices"]} == {"USD", "KES"}
        upd = client.patch(f"/api/v1/circle/plans/{slug}", json={"name": "Lifetime Circle", "displayOrder": 3}, headers=admin_headers)
        assert upd.status_code == 200 and upd.get_json()["data"]["name"] == "Lifetime Circle"
        public = client.get("/api/v1/circle/plans").get_json()["data"]
        plan = next(p for p in public if p["slug"] == slug)
        assert plan["billingInterval"] == "lifetime" and plan["isLifetime"] is True and plan["recurring"] is False
        assert [p["formatted"] for p in plan["prices"]]

    def test_inactive_lifetime_plan_is_hidden_and_not_purchasable(self, client, app, admin_headers, user_token):
        _enable_paystack(app)
        plan_id, slug = _plan(app)
        client.patch(f"/api/v1/circle/plans/{slug}", json={"status": "archived"}, headers=admin_headers)
        assert slug not in [p["slug"] for p in client.get("/api/v1/circle/plans").get_json()["data"]]
        resp, _ = _checkout(client, user_token, slug)
        assert resp.status_code in (404, 422)

    def test_lifetime_rejects_recurring_billing_metadata(self, client, app, admin_headers):
        body = {"name": "L", "billingInterval": "lifetime", "currency": "USD", "manageBillingUrl": "https://billing.example.com"}
        resp = client.post("/api/v1/circle/plans", json=body, headers=admin_headers)
        assert resp.status_code == 422 and "manage-billing" in resp.get_json()["error"]["message"]

    def test_interval_cannot_cross_lifetime_once_referenced(self, client, app, admin_headers, user_token):
        plan_id, slug = _plan(app, interval="monthly")
        _subscription(app, _user(app).id, plan_id, current_period_end=datetime.now(timezone.utc) + timedelta(days=20))
        resp = client.patch(f"/api/v1/circle/plans/{slug}", json={"billingInterval": "lifetime"}, headers=admin_headers)
        assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "billing_interval_locked"
        # An unreferenced plan may still be switched.
        _pid, free_slug = _plan(app, interval="monthly")
        assert client.patch(f"/api/v1/circle/plans/{free_slug}", json={"billingInterval": "lifetime"}, headers=admin_headers).status_code == 200

    def test_unknown_interval_rejected(self, client, app, admin_headers):
        resp = client.post("/api/v1/circle/plans", json={"name": "X", "billingInterval": "weekly", "currency": "USD"}, headers=admin_headers)
        assert resp.status_code == 422


# --- checkout -----------------------------------------------------------------------


class TestLifetimeCheckout:
    def test_one_time_transaction_with_server_amount_and_currency(self, client, app, user_token):
        _enable_paystack(app)
        _pid, slug = _plan(app, prices=(("USD", 29900), ("KES", 3500000)))
        resp, init = _checkout(client, user_token, slug, currency="KES")
        assert resp.status_code in (200, 201), resp.get_json()
        kwargs = init.call_args.kwargs
        assert kwargs["amount_subunits"] == 3500000 and kwargs["currency"] == "KES"
        # A plain one-time transaction: no Paystack plan/subscription code.
        assert "plan" not in kwargs and "plan_code" not in kwargs
        payment = _payment(app, kwargs["reference"])
        assert payment.billing_interval == "lifetime" and payment.amount_subunits == 3500000

    def test_unsupported_currency_rejected(self, client, app, user_token):
        _enable_paystack(app, currencies=("USD",))
        _pid, slug = _plan(app, prices=(("USD", 29900), ("KES", 3500000)))
        resp, init = _checkout(client, user_token, slug, currency="KES")
        assert resp.status_code in (422, 503)
        init.assert_not_called()
        resp, init = _checkout(client, user_token, slug, currency="EUR")
        assert resp.status_code == 422 and init.call_count == 0

    def test_client_cannot_choose_amount_or_interval(self, client, app, user_token):
        _enable_paystack(app)
        _pid, slug = _plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as init:
            client.post(f"/api/v1/circle/plans/{slug}/checkout",
                        json={"amount": 1, "billingInterval": "monthly", "isLifetime": False}, headers=auth_headers(user_token))
        assert init.call_args.kwargs["amount_subunits"] == 29900
        assert _payment(app, init.call_args.kwargs["reference"]).billing_interval == "lifetime"

    def test_verified_payment_activates_lifetime_without_expiry(self, client, app, user_token):
        _enable_paystack(app)
        _pid, slug = _plan(app)
        reference, _init, status = _buy_lifetime(client, app, user_token, slug)
        assert status.get_json()["data"]["membershipActivated"] is True
        sub = _current(app, _user(app).id)
        assert sub.status == "active" and sub.current_period_end is None and sub.cancel_at_period_end is False
        assert _has_access(app, _user(app).id) and _has_access(app, _user(app).id, yearly=True)

    def test_failed_verification_grants_nothing(self, client, app, user_token):
        _enable_paystack(app)
        _pid, slug = _plan(app)
        resp, init = _checkout(client, user_token, slug)
        reference = init.call_args.kwargs["reference"]
        with patch("app.services.circle_payments.verify_transaction", return_value=_success(_payment(app, reference), status="failed")):
            client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user_token))
        assert _current(app, _user(app).id) is None and not _has_access(app, _user(app).id)

    def test_amount_mismatch_never_activates(self, client, app, user_token):
        _enable_paystack(app)
        _pid, slug = _plan(app)
        resp, init = _checkout(client, user_token, slug)
        reference = init.call_args.kwargs["reference"]
        with patch("app.services.circle_payments.verify_transaction", return_value=_success(_payment(app, reference), amount=100)):
            client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user_token))
        assert _current(app, _user(app).id) is None

    def test_duplicate_callback_and_webhook_are_idempotent(self, client, app, user_token):
        from app.models.circle import CircleSubscription

        _enable_paystack(app)
        _pid, slug = _plan(app)
        reference, _init, _status = _buy_lifetime(client, app, user_token, slug)
        payment = _payment(app, reference)
        body = json.dumps({"event": "charge.success", "data": {"reference": reference}}).encode()
        signature = hmac.new(_SECRET.encode(), body, hashlib.sha512).hexdigest()
        with patch("app.services.circle_payments.verify_transaction", return_value=_success(payment)):
            for _ in range(2):
                hook = client.post(_WEBHOOK_URL, data=body, headers={"Content-Type": "application/json", "x-paystack-signature": signature})
                assert hook.status_code == 200
            again = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user_token))
        assert again.get_json()["data"]["status"] == "consumed"
        with app.app_context():
            assert CircleSubscription.query.filter_by(user_id=_user(app).id).count() == 1
        assert _current(app, _user(app).id).current_period_end is None

    def test_webhook_alone_activates_lifetime(self, client, app, user_token):
        _enable_paystack(app)
        _pid, slug = _plan(app)
        resp, init = _checkout(client, user_token, slug)
        reference = init.call_args.kwargs["reference"]
        body = json.dumps({"event": "charge.success", "data": {"reference": reference}}).encode()
        signature = hmac.new(_SECRET.encode(), body, hashlib.sha512).hexdigest()
        with patch("app.services.circle_payments.verify_transaction", return_value=_success(_payment(app, reference))):
            assert client.post(_WEBHOOK_URL, data=body, headers={"Content-Type": "application/json", "x-paystack-signature": signature}).status_code == 200
        assert _current(app, _user(app).id).current_period_end is None

    def test_bad_signature_webhook_never_activates(self, client, app, user_token):
        _enable_paystack(app)
        _pid, slug = _plan(app)
        resp, init = _checkout(client, user_token, slug)
        reference = init.call_args.kwargs["reference"]
        body = json.dumps({"event": "charge.success", "data": {"reference": reference}}).encode()
        resp = client.post(_WEBHOOK_URL, data=body, headers={"Content-Type": "application/json", "x-paystack-signature": "0" * 128})
        assert resp.status_code in (400, 401)
        assert _current(app, _user(app).id) is None


# --- membership ---------------------------------------------------------------------


class TestLifetimeMembership:
    def test_access_survives_long_date_progression(self, client, app, user_token):
        from app.models.user import User
        from app.services.circle import has_circle_access

        plan_id, _slug = _plan(app)
        _subscription(app, _user(app).id, plan_id)
        far_future = datetime.now(timezone.utc) + timedelta(days=365 * 40)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return far_future

        with app.app_context(), patch("app.services.circle.datetime", _FrozenDatetime):
            assert has_circle_access(db.session.get(User, _user(app).id)) is True

    def test_revocation_and_inactive_states_remove_access(self, client, app, admin_headers):
        plan_id, _slug = _plan(app)
        uid = _user_after_register(client, app)
        sub_id = _subscription(app, uid, plan_id)
        assert _has_access(app, uid)
        resp = client.patch(f"/api/v1/circle/subscriptions/{sub_id}", json={"status": "revoked"}, headers=admin_headers)
        assert resp.status_code == 200
        assert not _has_access(app, uid) and not _has_access(app, uid, yearly=True)

    @pytest.mark.parametrize("status", ["pending", "past_due"])
    def test_non_active_lifetime_has_no_access(self, client, app, status):
        plan_id, _slug = _plan(app)
        uid = _user_after_register(client, app)
        _subscription(app, uid, plan_id, status=status)
        assert not _has_access(app, uid)

    def test_admin_cannot_give_lifetime_a_period_end(self, client, app, admin_headers):
        plan_id, _slug = _plan(app)
        uid = _user_after_register(client, app)
        resp = client.post("/api/v1/circle/subscriptions", json={
            "email": USER["email"], "planId": plan_id, "status": "active", "source": "manual",
            "currentPeriodEnd": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}, headers=admin_headers)
        assert resp.status_code == 422
        sub_id = _subscription(app, uid, plan_id)
        resp = client.patch(f"/api/v1/circle/subscriptions/{sub_id}", json={"cancelAtPeriodEnd": True}, headers=admin_headers)
        assert resp.status_code == 422
        detail = client.get(f"/api/v1/circle/subscriptions/{sub_id}", headers=admin_headers).get_json()["data"]
        assert detail["current_period_end"] is None and detail["plan"]["billing_interval"] == "lifetime"

    def test_owner_payload_marks_lifetime_without_renewal(self, client, app, user_token):
        plan_id, _slug = _plan(app)
        _subscription(app, _user(app).id, plan_id)
        me = client.get("/api/v1/circle/me", headers=auth_headers(user_token)).get_json()["data"]
        assert me["hasAccess"] is True and me["yearlyLevelAccess"] is True
        assert me["subscription"]["isLifetime"] is True
        assert me["subscription"]["currentPeriodEnd"] is None and me["subscription"]["cancelAtPeriodEnd"] is False


def _user_after_register(client, app):
    _register(client, USER)
    return _user(app).id


# --- duplicate purchase protection -------------------------------------------------------


class TestDuplicatePurchase:
    def test_active_lifetime_member_cannot_buy_again(self, client, app, user_token):
        _enable_paystack(app)
        plan_id, slug = _plan(app)
        _subscription(app, _user(app).id, plan_id)
        resp, init = _checkout(client, user_token, slug)
        assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "lifetime_membership_active"
        assert resp.get_json()["error"]["message"] == "You already have Lifetime WSF Circle access."
        init.assert_not_called()
        _mid, monthly_slug = _plan(app, interval="monthly", prices=(("USD", 1500),))
        resp, init = _checkout(client, user_token, monthly_slug)
        assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "lifetime_membership_active"

    @pytest.mark.parametrize("interval", ["monthly", "yearly"])
    def test_recurring_member_buying_lifetime_is_deferred_safely(self, client, app, user_token, interval):
        _enable_paystack(app)
        current_id, _ = _plan(app, interval=interval, prices=(("USD", 1500),))
        _subscription(app, _user(app).id, current_id, current_period_end=datetime.now(timezone.utc) + timedelta(days=20))
        _lid, lifetime_slug = _plan(app)
        resp, init = _checkout(client, user_token, lifetime_slug)
        assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "lifetime_upgrade_unavailable"
        init.assert_not_called()


# --- yearly-level benefits across gated entity types -------------------------------------


def _member(app, client, interval):
    plan_id, _ = _plan(app, interval=interval, prices=(("USD", 1500),))
    uid = _user_after_register(client, app)
    end = None if interval == "lifetime" else datetime.now(timezone.utc) + timedelta(days=20)
    _subscription(app, uid, plan_id, current_period_end=end)
    return uid


class TestYearlyLevelBenefits:
    @pytest.mark.parametrize("interval, yearly_ok", [("monthly", False), ("yearly", True), ("lifetime", True)])
    def test_yearly_only_resource(self, client, app, interval, yearly_ok):
        from app.models.resource import Resource
        from app.models.user import User
        from app.services.resource_access import check_resource_access
        from app.utils.responses import ApiError

        uid = _member(app, client, interval)
        with app.app_context():
            resource = Resource(slug="bonus", name="Bonus", status="published", description=[], access_type="circle_only",
                                circle_access_level="yearly_members")
            db.session.add(resource)
            db.session.commit()
            user = db.session.get(User, uid)
            if yearly_ok:
                check_resource_access(resource, user)
            else:
                with pytest.raises(ApiError):
                    check_resource_access(resource, user)

    @pytest.mark.parametrize("interval", ["monthly", "yearly", "lifetime"])
    def test_every_circle_gate_accepts_active_members(self, client, app, interval):
        from app.models.learning import LearningProgram
        from app.models.opportunity import Event, Job, Opportunity
        from app.models.resource import Resource
        from app.models.user import User
        from app.services.event_access import can_access_event
        from app.services.job_access import can_access_job_application
        from app.services.learning_access import can_access_program_content
        from app.services.opportunity_access import can_access_opportunity_application
        from app.services.resource_access import check_resource_access

        uid = _member(app, client, interval)
        with app.app_context():
            user = db.session.get(User, uid)
            today = datetime.now(timezone.utc).date()
            resource = Resource(slug="c", name="C", status="published", description=[], access_type="circle_only")
            premium = Resource(slug="p", name="P", status="published", description=[], access_type="premium")
            program = LearningProgram(slug="lp", title="LP", status="published", access_type="circle_only")
            event = Event(slug="ev", title="EV", status="published", description=[], date=today, access_type="circle_only")
            job = Job(slug="jb", title="JB", company_name="Co", status="published", description=[], access_type="circle_only")
            opp = Opportunity(slug="op", title="OP", status="published", description=[], access_type="circle_only")
            db.session.add_all([resource, premium, program, event, job, opp])
            db.session.commit()
            check_resource_access(resource, user)
            check_resource_access(premium, user)
            assert can_access_program_content(program, user)
            assert can_access_event(event, user)
            assert can_access_job_application(job, user)
            assert can_access_opportunity_application(opp, user)

    def test_owner_payload_yearly_level_flag(self, client, app):
        for interval, expected in (("monthly", False),):
            uid = _member(app, client, interval)
            token = client.post("/api/v1/auth/login", json={"email": USER["email"], "password": USER["password"]}).get_json()["data"]["access_token"]
            assert client.get("/api/v1/circle/me", headers=auth_headers(token)).get_json()["data"]["yearlyLevelAccess"] is expected


# --- monthly / yearly regression ----------------------------------------------------------


class TestRecurringRegression:
    @pytest.mark.parametrize("interval, delta_days", [("monthly", (27, 32)), ("yearly", (364, 367))])
    def test_recurring_plans_still_get_a_period_end_and_renew(self, client, app, user_token, interval, delta_days):
        _enable_paystack(app)
        _pid, slug = _plan(app, interval=interval, prices=(("USD", 1500),))
        reference, _init, status = _buy_lifetime(client, app, user_token, slug)
        sub = _current(app, _user(app).id)
        days = (sub.current_period_end - sub.current_period_start).days
        assert delta_days[0] <= days <= delta_days[1]
        first_end = sub.current_period_end
        # Same-plan renewal still extends from the current end.
        _ref2, _i2, _s2 = _buy_lifetime(client, app, user_token, slug)
        assert _current(app, _user(app).id).current_period_end > first_end

    def test_add_billing_interval_rules(self):
        from app.services.circle_payments import _add_billing_interval

        start = datetime(2026, 1, 31, tzinfo=timezone.utc)
        assert _add_billing_interval(start, "monthly") == datetime(2026, 2, 28, tzinfo=timezone.utc)
        assert _add_billing_interval(start, "yearly") == datetime(2027, 1, 31, tzinfo=timezone.utc)
        assert _add_billing_interval(start, "lifetime") is None


# --- migration -------------------------------------------------------------------------------


class TestLifetimeMigration:
    def test_widen_and_restore_billing_interval_checks(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module = importlib.import_module("migrations.versions.b5e8c1f6a3d7_circle_lifetime_billing")
        assert module.down_revision == "a4d7b0e5f2c6"
        engine = sa.create_engine("sqlite://")
        with engine.begin() as conn:
            for table, name in module._TABLES:
                conn.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, billing_interval VARCHAR(10) NOT NULL, "
                                     f"CONSTRAINT {name} CHECK ({module._check(module._PREVIOUS)}))"))
                conn.execute(sa.text(f"INSERT INTO {table} (billing_interval) VALUES ('monthly'), ('yearly')"))
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()
            conn.execute(sa.text("INSERT INTO circle_plans (billing_interval) VALUES ('lifetime')"))
            with pytest.raises(RuntimeError):
                with Operations.context(MigrationContext.configure(conn)):
                    module.downgrade()
            conn.execute(sa.text("DELETE FROM circle_plans WHERE billing_interval = 'lifetime'"))
            with Operations.context(MigrationContext.configure(conn)):
                module.downgrade()
            assert conn.execute(sa.text("SELECT billing_interval FROM circle_plans ORDER BY id")).scalars().all() == ["monthly", "yearly"]
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(sa.text("INSERT INTO circle_payments (billing_interval) VALUES ('lifetime')"))
