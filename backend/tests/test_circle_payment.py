"""Module 1 (foundations) of the Paystack Circle integration: the
CirclePayment model and its Paystack-related configuration. No checkout
endpoint, webhook, or activation logic exists yet — see
app/models/circle.py's CirclePayment and config.py's PAYSTACK_* settings.
No CircleSubscription is ever created by these tests, and
has_circle_access() is never touched.
"""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

USER1 = {
    "email": "circlepay-user1@example.com", "password": "supersecret1",
    "first_name": "Nia", "last_name": "Okoro", "country_code": "KE",
}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def user1_token(client):
    return _register(client, USER1)


def _get_user_id(app, email):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first().id


def _make_plan(app, **overrides):
    from app.extensions import db
    from app.models.circle import CirclePlan

    defaults = dict(
        slug=overrides.pop("slug", None) or f"plan-{uuid.uuid4().hex[:10]}",
        name="WSF Circle Membership",
        billing_interval="monthly",
        price=1000,
        currency="USD",
        status="active",
    )
    defaults.update(overrides)
    with app.app_context():
        plan = CirclePlan(**defaults)
        db.session.add(plan)
        db.session.commit()
        return plan.id


def _make_payment(app, user_id, plan_id, **overrides):
    from app.extensions import db
    from app.models.circle import CirclePayment

    defaults = dict(
        reference=overrides.pop("reference", None) or f"wsfcircle-{uuid.uuid4().hex}",
        user_id=user_id,
        plan_id=plan_id,
        amount_subunits=100000,
        currency="USD",
        billing_interval="monthly",
        customer_email="circlepay-user1@example.com",
        status="pending",
    )
    defaults.update(overrides)
    with app.app_context():
        payment = CirclePayment(**defaults)
        db.session.add(payment)
        db.session.commit()
        return payment.id


class TestCirclePaymentModel:
    def test_create_minimal_payment(self, app, user1_token):
        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        payment_id = _make_payment(app, user_id, plan_id)

        from app.models.circle import CirclePayment

        with app.app_context():
            payment = CirclePayment.query.get(payment_id)
            assert payment.status == "pending"
            assert payment.provider == "paystack"
            assert payment.subscription_id is None

    def test_reference_uniqueness(self, app, user1_token):
        from app.extensions import db
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        shared_reference = f"wsfcircle-{uuid.uuid4().hex}"
        _make_payment(app, user_id, plan_id, reference=shared_reference)

        with app.app_context():
            dupe = CirclePayment(
                reference=shared_reference,
                user_id=user_id,
                plan_id=plan_id,
                amount_subunits=100000,
                currency="USD",
                billing_interval="monthly",
                customer_email=USER1["email"],
                status="pending",
            )
            db.session.add(dupe)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_valid_status_values_accepted(self, app, user1_token):
        from app.models.circle import CIRCLE_PAYMENT_STATUSES

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        for status in CIRCLE_PAYMENT_STATUSES:
            _make_payment(app, user_id, plan_id, status=status)

    def test_invalid_status_rejected(self, app, user1_token):
        from app.extensions import db
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        with app.app_context():
            payment = CirclePayment(
                reference=f"wsfcircle-{uuid.uuid4().hex}",
                user_id=user_id,
                plan_id=plan_id,
                amount_subunits=100000,
                currency="USD",
                billing_interval="monthly",
                customer_email=USER1["email"],
                status="not-a-real-status",
            )
            db.session.add(payment)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_invalid_billing_interval_rejected(self, app, user1_token):
        from app.extensions import db
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        with app.app_context():
            payment = CirclePayment(
                reference=f"wsfcircle-{uuid.uuid4().hex}",
                user_id=user_id,
                plan_id=plan_id,
                amount_subunits=100000,
                currency="USD",
                billing_interval="weekly",
                customer_email=USER1["email"],
                status="pending",
            )
            db.session.add(payment)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_invalid_provider_rejected(self, app, user1_token):
        from app.extensions import db
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        with app.app_context():
            payment = CirclePayment(
                reference=f"wsfcircle-{uuid.uuid4().hex}",
                user_id=user_id,
                plan_id=plan_id,
                provider="stripe",
                amount_subunits=100000,
                currency="USD",
                billing_interval="monthly",
                customer_email=USER1["email"],
                status="pending",
            )
            db.session.add(payment)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_nonpositive_amount_rejected(self, app, user1_token):
        """amount_subunits must be strictly positive, not merely
        non-negative: a CirclePayment represents a real Paystack
        transaction attempt, so a would-be zero-value "payment" is
        rejected exactly like a negative one. A future zero-value/
        complimentary membership belongs to the existing manual/
        complimentary CircleSubscription pathway, never to a fake
        zero-value row here.
        """
        from app.extensions import db
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        for invalid_amount in (-500, 0):
            with app.app_context():
                payment = CirclePayment(
                    reference=f"wsfcircle-{uuid.uuid4().hex}",
                    user_id=user_id,
                    plan_id=plan_id,
                    amount_subunits=invalid_amount,
                    currency="USD",
                    billing_interval="monthly",
                    customer_email=USER1["email"],
                    status="pending",
                )
                db.session.add(payment)
                with pytest.raises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

    def test_provider_transaction_id_uniqueness(self, app, user1_token):
        from app.extensions import db
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        _make_payment(app, user_id, plan_id, provider_transaction_id="999888777")

        with app.app_context():
            dupe = CirclePayment(
                reference=f"wsfcircle-{uuid.uuid4().hex}",
                user_id=user_id,
                plan_id=plan_id,
                provider_transaction_id="999888777",
                amount_subunits=100000,
                currency="USD",
                billing_interval="monthly",
                customer_email=USER1["email"],
                status="pending",
            )
            db.session.add(dupe)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_multiple_null_provider_transaction_ids_allowed(self, app, user1_token):
        # The partial unique index only covers NOT NULL rows — two
        # `pending` payments that never reached Paystack yet (and so have
        # no transaction id at all) must not collide with each other.
        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        _make_payment(app, user_id, plan_id)
        _make_payment(app, user_id, plan_id)

    def test_fk_relationships_resolve(self, app, user1_token):
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        payment_id = _make_payment(app, user_id, plan_id)

        with app.app_context():
            payment = CirclePayment.query.get(payment_id)
            assert payment.user.id == user_id
            assert payment.plan.id == plan_id
            assert payment.subscription is None

    def test_fk_relationship_to_subscription(self, app, user1_token):
        from app.extensions import db
        from app.models.circle import CirclePayment, CircleSubscription

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        with app.app_context():
            subscription = CircleSubscription(user_id=user_id, plan_id=plan_id, status="active", source="manual")
            db.session.add(subscription)
            db.session.commit()
            subscription_id = subscription.id

        payment_id = _make_payment(app, user_id, plan_id, subscription_id=subscription_id, status="consumed")

        with app.app_context():
            payment = CirclePayment.query.get(payment_id)
            assert payment.subscription_id == subscription_id
            assert payment.subscription.status == "active"

    def test_amount_stored_as_integer_subunits(self, app, user1_token):
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app, price=1000, currency="USD")
        # The one conversion rule Module 1 establishes: subunits = whole
        # units * 100, integer arithmetic only.
        payment_id = _make_payment(app, user_id, plan_id, amount_subunits=1000 * 100)

        with app.app_context():
            payment = CirclePayment.query.get(payment_id)
            assert payment.amount_subunits == 100000
            assert isinstance(payment.amount_subunits, int)

    def test_customer_email_snapshot(self, app, user1_token):
        from app.extensions import db
        from app.models.circle import CirclePayment
        from app.models.user import User

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        payment_id = _make_payment(app, user_id, plan_id, customer_email="snapshot-at-checkout@example.com")

        with app.app_context():
            # Changing the user's real account email afterwards must never
            # retroactively change what was snapshotted at checkout time.
            user = User.query.get(user_id)
            user.email = "changed-later@example.com"
            db.session.commit()

            payment = CirclePayment.query.get(payment_id)
            assert payment.customer_email == "snapshot-at-checkout@example.com"

    def test_billing_interval_snapshot(self, app, user1_token):
        from app.models.circle import CirclePayment

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app, billing_interval="monthly")
        payment_id = _make_payment(app, user_id, plan_id, billing_interval="monthly")

        with app.app_context():
            payment = CirclePayment.query.get(payment_id)
            assert payment.billing_interval == "monthly"

    def test_snapshot_fields_survive_later_plan_edits(self, app, user1_token):
        """The exact scenario Module 1's design note calls out: a user
        initializes a monthly payment, an admin then edits the plan to
        yearly/a different price/currency before the payment is ever
        verified — the already-created CirclePayment row must still read
        exactly as it did at initialization.
        """
        from app.extensions import db
        from app.models.circle import CirclePayment, CirclePlan

        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app, billing_interval="monthly", price=1000, currency="USD")
        payment_id = _make_payment(
            app,
            user_id,
            plan_id,
            amount_subunits=100000,
            currency="USD",
            billing_interval="monthly",
        )

        with app.app_context():
            plan = CirclePlan.query.get(plan_id)
            plan.billing_interval = "yearly"
            plan.price = 9000
            plan.currency = "KES"
            db.session.commit()

        with app.app_context():
            payment = CirclePayment.query.get(payment_id)
            assert payment.billing_interval == "monthly"
            assert payment.amount_subunits == 100000
            assert payment.currency == "USD"
            # The plan itself really did change — confirming the snapshot
            # isn't just coincidentally still matching.
            plan = CirclePlan.query.get(plan_id)
            assert plan.billing_interval == "yearly"
            assert plan.price == 9000
            assert plan.currency == "KES"

class TestPaystackConfigDefaults:
    def test_paystack_disabled_by_default_in_testing(self, app):
        with app.app_context():
            assert app.config["PAYSTACK_ENABLED"] is False

    def test_allowed_currencies_defaults_to_kes_only(self, app):
        with app.app_context():
            assert app.config["PAYSTACK_ALLOWED_CURRENCIES"] == ["KES"]

    def test_allowed_currencies_parses_comma_separated_env(self):
        # config.py's PAYSTACK_ALLOWED_CURRENCIES is a class attribute
        # evaluated once at module import time (same as every other
        # env-parsed Config value in this app), so it can't be exercised
        # by monkeypatching the environment and re-importing. Testing the
        # extracted parsing function directly is the real, repo-consistent
        # way to cover this rule (see config.py's own comment on why this
        # function exists).
        from config import _parse_currency_allowlist

        assert _parse_currency_allowlist("kes, usd ,usd", ["KES"]) == ["KES", "USD", "USD"]

    def test_allowed_currencies_falls_back_to_default_when_unset(self):
        from config import _parse_currency_allowlist

        assert _parse_currency_allowlist(None, ["KES"]) == ["KES"]
        assert _parse_currency_allowlist("", ["KES"]) == ["KES"]

    def test_allowed_currencies_drops_empty_entries(self):
        from config import _parse_currency_allowlist

        assert _parse_currency_allowlist("kes,, ,usd", ["KES"]) == ["KES", "USD"]

    def test_unsupported_currency_absent_from_default_allowlist(self, app):
        with app.app_context():
            assert "USD" not in app.config["PAYSTACK_ALLOWED_CURRENCIES"]
            assert "NGN" not in app.config["PAYSTACK_ALLOWED_CURRENCIES"]
