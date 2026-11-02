"""WSF Checkout Phase 1 — global payment settings, multi-currency pricing
and Paystack method controls: money/currency utilities, payment settings
validation, provider capability resolution, server-authoritative checkout
terms, admin pricing, public price payloads and the legacy-price migration.
Paystack is always mocked — nothing here makes a real request.
"""
import importlib
import json
import os
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from app.extensions import db
from tests.conftest import auth_headers

USER = {"email": "phase1-buyer@example.com", "password": "supersecret1", "first_name": "Ama", "last_name": "Buyer",
        "country_code": "US"}
ADMIN = {"email": "phase1-admin@example.com", "password": "supersecret1", "first_name": "Ada", "last_name": "Admin",
         "country_code": "US"}
_FAKE_INIT = {"authorization_url": "https://checkout.paystack.com/abc", "access_code": "code"}


def _mock_init(**kwargs):
    return dict(_FAKE_INIT, reference=kwargs["reference"])


def _register(client, payload, app=None, role=None):
    client.post("/api/v1/auth/register", json=payload)
    if role:
        from app.models.user import Role, User

        with app.app_context():
            user = User.query.filter_by(email=payload["email"]).first()
            user.roles.append(Role.query.filter_by(name=role).first())
            db.session.commit()
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def buyer(client):
    return _register(client, USER)


@pytest.fixture()
def admin(client, app):
    return _register(client, ADMIN, app, "super_admin")


@pytest.fixture()
def protected_root(app, tmp_path):
    root = tmp_path / "protected_media"
    root.mkdir()
    app.config["PROTECTED_MEDIA_ROOT"] = str(root)
    return root


def _enable_paystack(app, currencies=("KES", "USD")):
    app.config["PAYSTACK_ENABLED"] = True
    app.config["PAYSTACK_SECRET_KEY"] = "sk_test_dummy"
    app.config["PAYSTACK_ALLOWED_CURRENCIES"] = list(currencies)


def _save_settings(app, settings):
    from app.services.payment_settings import save_payment_settings

    with app.app_context():
        save_payment_settings(settings)
        db.session.commit()


def _settings(enabled=("USD", "KES"), default="USD", paystack=True, card=True, apple_pay=True, mobile_money=True):
    return {"defaultCurrency": default, "enabledCurrencies": list(enabled), "providers": {
        "paystack": {"enabled": paystack, "methods": {"card": card, "apple_pay": apple_pay, "mobile_money": mobile_money}}}}


def _plan(app, prices=(("USD", 2000), ("KES", 250000)), status="active"):
    from app.models.circle import CirclePlan, CirclePlanPrice

    with app.app_context():
        plan = CirclePlan(slug=f"plan-{uuid.uuid4().hex[:8]}", name="Circle Monthly", billing_interval="monthly",
                          price=0, currency="USD", status=status)
        for currency, amount, *enabled in prices:
            plan.prices.append(CirclePlanPrice(currency=currency, amount_minor=amount, enabled=enabled[0] if enabled else True))
        db.session.add(plan)
        db.session.commit()
        return plan.id, plan.slug


def _resource(app, protected_root, prices=(("USD", 900), ("KES", 120000))):
    from app.models.resource import Resource, ResourcePrice

    filename = f"{uuid.uuid4().hex}.pdf"
    (protected_root / filename).write_bytes(b"%PDF-1.4 body")
    with app.app_context():
        resource = Resource(slug=f"res-{uuid.uuid4().hex[:8]}", name="Workbook", access_type="premium",
                            protected_file_path=filename, status="published", published_date=date.today(),
                            description=[], price=0, currency="USD")
        for currency, amount in prices:
            resource.prices.append(ResourcePrice(currency=currency, amount_minor=amount, enabled=True))
        db.session.add(resource)
        db.session.commit()
        return resource.id, resource.slug


def _checkout(client, token, kind, slug, body=None):
    path = f"/api/v1/circle/plans/{slug}/checkout" if kind == "circle" else f"/api/v1/resources/{slug}/checkout"
    target = "app.services.circle_payments.initialize_transaction" if kind == "circle" else "app.services.resource_payments.initialize_transaction"
    with patch(target, side_effect=_mock_init) as mock_init:
        resp = client.post(path, json=body, headers=auth_headers(token)) if body is not None else client.post(path, headers=auth_headers(token))
    return resp, mock_init


# --- money / currency registry --------------------------------------------------------------------


@pytest.mark.parametrize("amount, currency, minor", [
    ("19.99", "USD", 1999), ("20", "USD", 2000), ("0.01", "USD", 1),
    ("2500", "KES", 250000), ("2500.50", "KES", 250050),
    ("2500", "JPY", 2500), (2500, "JPY", 2500), ("1.250", "KWD", 1250), (Decimal("9.00"), "usd", 900),
])
def test_to_minor_units_exact(amount, currency, minor):
    from app.services.money import from_minor_units, to_minor_units

    assert to_minor_units(amount, currency) == minor
    assert to_minor_units(str(from_minor_units(minor, currency)), currency) == minor


@pytest.mark.parametrize("amount, currency", [
    ("19.999", "USD"), ("2500.5", "JPY"), ("1.2505", "KWD"),  # too many decimals: rejected, never rounded
    ("-1", "USD"), (19.99, "USD"), ("abc", "USD"), ("NaN", "USD"), ("Infinity", "USD"), (True, "USD"),
])
def test_to_minor_units_rejects(amount, currency):
    from app.services.money import MoneyError, to_minor_units

    with pytest.raises(MoneyError):
        to_minor_units(amount, currency)


def test_invalid_currency_and_formatting():
    from app.services.currencies import UnknownCurrencyError, currency_catalogue, minor_unit
    from app.services.money import format_money, from_minor_units, legacy_whole_units_to_minor

    for bad in ("ZZZ", "XAU", "US", "", None, "XTS"):
        with pytest.raises(UnknownCurrencyError):
            minor_unit(bad)
    assert (minor_unit("USD"), minor_unit("KES"), minor_unit("JPY"), minor_unit("KWD")) == (2, 2, 0, 3)
    assert from_minor_units(1999, "USD") == Decimal("19.99")
    assert format_money(2000, "USD") == "$20.00"
    assert format_money(250000, "KES") == "KES 2,500.00"
    assert format_money(2500, "JPY") == "JPY 2,500"
    assert legacy_whole_units_to_minor(1000, "KES") == 100000 and legacy_whole_units_to_minor(2500, "JPY") == 2500
    catalogue = currency_catalogue()
    codes = [c["code"] for c in catalogue]
    assert codes[:13] == ["USD", "KES", "EUR", "GBP", "CAD", "AUD", "ZAR", "GHS", "NGN", "JPY", "CHF", "NZD", "SGD"]
    assert len(codes) == len(set(codes)) > 140
    assert all(set(c) == {"code", "name", "symbol", "minorUnit"} for c in catalogue)


# --- payment settings ---------------------------------------------------------------------------------


def test_default_settings_are_conservative_production_defaults(app):
    from app.services.payment_settings import get_payment_settings

    with app.app_context():
        settings = get_payment_settings()
    assert settings["defaultCurrency"] == "USD"
    assert settings["enabledCurrencies"] == ["USD", "KES"]
    assert settings["providers"]["paystack"] == {"enabled": True, "methods": {"card": True, "apple_pay": False, "mobile_money": True}}


@pytest.mark.parametrize("bad, message", [
    ({"enabledCurrencies": ["USD", "ZZZ"]}, "not a valid ISO 4217"),
    ({"enabledCurrencies": ["USD", "usd"]}, "more than once"),
    ({"enabledCurrencies": []}, "at least one currency"),
    ({"defaultCurrency": "EUR"}, "one of the enabled"),
    ({"providers": {"paystack": {"enabled": True, "methods": {"card": True, "ussd": True}}}}, "Unsupported paystack payment method"),
    ({"providers": {"paypal": {"enabled": True, "methods": {}}}}, "Unsupported payment provider"),
    ({"providers": {"paystack": {"enabled": "yes", "methods": {}}}}, "enabled must be true or false"),
    ({"secretKey": "sk_live_x"}, "Unknown payment setting"),
])
def test_settings_validation(bad, message):
    from app.services.payment_settings import PaymentSettingsError, validate_payment_settings

    raw = {**_settings(), **bad}
    with pytest.raises(PaymentSettingsError, match=message):
        validate_payment_settings(raw)


def test_admin_settings_api_saves_and_never_leaks_secrets(client, app, admin, buyer):
    _enable_paystack(app)
    app.config["PAYSTACK_SECRET_KEY"] = "sk_test_SUPERSECRET_value"
    resp = client.put("/api/v1/admin/settings", json={"settings": {"payment_settings": _settings(enabled=("USD", "EUR"))}},
                      headers=auth_headers(admin))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()["data"]["payment_settings"]
    assert body["settings"]["enabledCurrencies"] == ["USD", "EUR"]
    assert body["providers"]["paystack"]["configured"] is True
    assert body["providers"]["paystack"]["currencies"] == ["KES", "USD"]
    assert [m["key"] for m in body["providers"]["paystack"]["methods"]] == ["card", "apple_pay", "mobile_money"]
    for public in (client.get("/api/v1/payments/config").get_json(), body):
        assert "SUPERSECRET" not in json.dumps(public) and "sk_test" not in json.dumps(public)
    bad = client.put("/api/v1/admin/settings", json={"settings": {"payment_settings": _settings(enabled=("USD", "ZZZ"))}},
                     headers=auth_headers(admin))
    assert bad.status_code == 422
    forbidden = client.put("/api/v1/admin/settings", json={"settings": {"payment_settings": _settings()}},
                           headers=auth_headers(buyer))
    assert forbidden.status_code == 403
    config = client.get("/api/v1/payments/config").get_json()["data"]
    assert config["defaultCurrency"] == "USD" and config["enabledCurrencies"] == ["USD", "EUR"]
    assert "providers" not in config


# --- provider capability -------------------------------------------------------------------------------


def _resolve(app, currency, settings=None, transaction="circle_membership"):
    from app.services.payment_settings import resolve_checkout

    with app.app_context():
        if settings:
            _save_settings(app, settings)
        return resolve_checkout(currency, transaction)


def test_usd_and_kes_channels(app):
    _enable_paystack(app)
    usd = _resolve(app, "USD", _settings())
    assert usd == {"provider": "paystack", "currency": "USD", "channels": ["card", "apple_pay"]}
    kes = _resolve(app, "KES")
    assert kes["channels"] == ["card", "apple_pay", "mobile_money"]


@pytest.mark.parametrize("settings, currency", [
    (_settings(enabled=("USD", "KES", "EUR")), "EUR"),  # Paystack can't charge EUR
    (_settings(enabled=("USD",)), "KES"),  # currency disabled by admin
    (_settings(paystack=False), "USD"),  # provider disabled
    (_settings(card=False, apple_pay=False), "USD"),  # only mobile_money left, not valid for USD
    (_settings(), "ZZZ"),
])
def test_no_valid_provider_combination(app, settings, currency):
    _enable_paystack(app)
    assert _resolve(app, currency, settings) is None


def test_unconfigured_provider_and_env_allowlist(app):
    app.config["PAYSTACK_ENABLED"] = False
    assert _resolve(app, "USD", _settings()) is None
    _enable_paystack(app, currencies=("KES",))  # deployment hasn't confirmed USD
    assert _resolve(app, "USD") is None and _resolve(app, "KES") is not None


def test_method_disabled_is_excluded(app):
    _enable_paystack(app)
    assert _resolve(app, "KES", _settings(apple_pay=False))["channels"] == ["card", "mobile_money"]
    assert _resolve(app, "KES", _settings(card=False, apple_pay=False))["channels"] == ["mobile_money"]


def test_paystack_initialize_validates_channels(app):
    from app.services.paystack import PaystackAPIError, initialize_transaction

    _enable_paystack(app)
    base = dict(amount_subunits=2000, email="a@example.com", reference="r1", currency="USD", callback_url="https://x.org/cb")
    with app.app_context():
        for channels in (["ussd"], ["card", "eft"], [], ["card", "card"]):
            with patch("app.services.paystack.requests.request") as request:
                with pytest.raises(PaystackAPIError):
                    initialize_transaction(**base, channels=channels)
                request.assert_not_called()
        with patch("app.services.paystack.requests.request") as request:
            with pytest.raises(PaystackAPIError):
                initialize_transaction(**{**base, "amount_subunits": 19.99})
            request.assert_not_called()
        with patch("app.services.paystack._request", return_value={"data": {"authorization_url": "u", "access_code": "c", "reference": "r1"}}) as req:
            initialize_transaction(**base, channels=["card", "apple_pay"])
            assert req.call_args.kwargs["json_body"]["channels"] == ["card", "apple_pay"]


# --- server-authoritative checkout ----------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["circle", "resource"])
def test_checkout_charges_the_stored_price_for_the_chosen_currency(client, app, buyer, protected_root, kind):
    _enable_paystack(app)
    _save_settings(app, _settings())
    slug = _plan(app)[1] if kind == "circle" else _resource(app, protected_root)[1]
    usd_minor, kes_minor = (2000, 250000) if kind == "circle" else (900, 120000)

    resp, mock_init = _checkout(client, buyer, kind, slug)  # no currency -> global default USD
    assert resp.status_code == 201, resp.get_json()
    kwargs = mock_init.call_args.kwargs
    assert (kwargs["currency"], kwargs["amount_subunits"], kwargs["channels"]) == ("USD", usd_minor, ["card", "apple_pay"])

    _, mock_init = _checkout(client, buyer, kind, slug, {"currency": "KES", "amount": 1, "price": 1, "amountMinor": 1,
                                                         "email": "evil@example.com", "userId": 1, "entitlement": True})
    kwargs = mock_init.call_args.kwargs
    assert (kwargs["currency"], kwargs["amount_subunits"]) == ("KES", kes_minor)
    assert kwargs["channels"] == ["card", "apple_pay", "mobile_money"]
    assert kwargs["email"] == USER["email"]


@pytest.mark.parametrize("kind", ["circle", "resource"])
@pytest.mark.parametrize("body, settings, code", [
    ({"currency": "EUR"}, _settings(), "currency_not_available"),  # not priced in EUR
    ({"currency": "ZZZ"}, _settings(), "currency_not_available"),
    ({"currency": "KES"}, _settings(enabled=("USD",)), "currency_not_supported"),  # disabled currency
    ({"currency": "USD"}, _settings(paystack=False), "payment_unavailable"),  # disabled provider
    ({"currency": "USD"}, _settings(card=False, apple_pay=False), "payment_unavailable"),  # no method fits USD
])
def test_checkout_rejects_tampering_without_calling_paystack(client, app, buyer, protected_root, kind, body, settings, code):
    _enable_paystack(app)
    _save_settings(app, settings)
    slug = _plan(app)[1] if kind == "circle" else _resource(app, protected_root)[1]
    resp, mock_init = _checkout(client, buyer, kind, slug, body)
    assert resp.status_code in (422, 503)
    assert resp.get_json()["error"]["code"] == code
    mock_init.assert_not_called()


def test_disabled_price_row_is_not_chargeable(client, app, buyer):
    _enable_paystack(app)
    _save_settings(app, _settings())
    slug = _plan(app, prices=(("USD", 2000, False), ("KES", 250000, True)))[1]
    resp, mock_init = _checkout(client, buyer, "circle", slug, {"currency": "USD"})
    assert resp.get_json()["error"]["code"] == "currency_not_available"
    resp, mock_init = _checkout(client, buyer, "circle", slug)  # USD default not offered -> its only enabled price
    assert mock_init.call_args.kwargs["currency"] == "KES"


def test_payment_snapshot_survives_price_edit(client, app, buyer):
    from app.models.circle import CirclePayment, CirclePlanPrice

    _enable_paystack(app)
    _save_settings(app, _settings())
    plan_id, slug = _plan(app)
    resp, _ = _checkout(client, buyer, "circle", slug, {"currency": "USD"})
    reference = resp.get_json()["data"]["reference"]
    with app.app_context():
        CirclePlanPrice.query.filter_by(plan_id=plan_id, currency="USD").one().amount_minor = 9999
        db.session.commit()
        payment = CirclePayment.query.filter_by(reference=reference).one()
        assert (payment.amount_subunits, payment.currency) == (2000, "USD")
    # A new checkout after the reprice must not reuse the stale pending one.
    resp2, mock_init = _checkout(client, buyer, "circle", slug, {"currency": "USD"})
    assert resp2.get_json()["data"]["reference"] != reference
    assert mock_init.call_args.kwargs["amount_subunits"] == 9999


# --- public + admin pricing ---------------------------------------------------------------------------------


def test_public_plan_prices_payload(client, app):
    _enable_paystack(app)
    _save_settings(app, _settings(enabled=("USD", "KES", "JPY")))
    _plan(app, prices=(("USD", 2000), ("KES", 250000), ("JPY", 2500), ("EUR", 1800, False)))
    plan = client.get("/api/v1/circle/plans").get_json()["data"][0]
    assert plan["defaultCurrency"] == "USD"
    assert [(p["currency"], p["amountMinor"], p["formatted"], p["checkoutAvailable"]) for p in plan["prices"]] == [
        ("USD", 2000, "$20.00", True), ("KES", 250000, "KES 2,500.00", True), ("JPY", 2500, "JPY 2,500", False)]
    usd, kes = plan["prices"][0], plan["prices"][1]
    assert [m["label"] for m in usd["paymentMethods"]] == ["Card", "Apple Pay"]
    assert [m["label"] for m in kes["paymentMethods"]] == ["Card", "Apple Pay", "Mobile Money / M-PESA"]
    assert "sk_test" not in json.dumps(plan)


def test_admin_plan_pricing_rules(client, app, admin):
    payload = {"name": "Yearly", "currency": "USD", "status": "active", "billingInterval": "yearly",
               "prices": [{"currency": "USD", "amount": "199.99", "enabled": True}, {"currency": "kes", "amount": "25000"}]}
    resp = client.post("/api/v1/circle/plans", json=payload, headers=auth_headers(admin))
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()["data"]
    assert [(p["currency"], p["amountMinor"], p["amount"]) for p in data["prices"]] == [("USD", 19999, "199.99"), ("KES", 2500000, "25000.00")]
    slug = data["slug"]
    for bad in ([{"currency": "USD", "amount": "1"}, {"currency": "USD", "amount": "2"}],
                [{"currency": "USD", "amount": "19.999"}], [{"currency": "ZZZ", "amount": "1"}],
                [{"currency": "USD", "amount": "0"}], [{"currency": "USD", "amount": 19.99}],
                [{"currency": "USD", "amount": "-5"}], [{"currency": "USD", "amount": "5", "enabled": False}]):
        resp = client.patch(f"/api/v1/circle/plans/{slug}", json={"prices": bad}, headers=auth_headers(admin))
        assert resp.status_code == 422, bad
    # Every rejected save above changed nothing.
    assert [p["amountMinor"] for p in client.get(f"/api/v1/circle/plans/{slug}", headers=auth_headers(admin)).get_json()["data"]["prices"]] == [19999, 2500000]
    # Omitting prices leaves them; [] removes them.
    resp = client.patch(f"/api/v1/circle/plans/{slug}", json={"name": "Yearly Plus"}, headers=auth_headers(admin))
    assert len(resp.get_json()["data"]["prices"]) == 2
    resp = client.patch(f"/api/v1/circle/plans/{slug}", json={"prices": []}, headers=auth_headers(admin))
    assert resp.get_json()["data"]["prices"] == []


def test_legacy_price_write_converts_explicitly(client, app, admin):
    resp = client.post("/api/v1/circle/plans", json={"name": "Legacy", "currency": "KES", "price": 1000},
                       headers=auth_headers(admin))
    slug = resp.get_json()["data"]["slug"]
    assert [(p["currency"], p["amountMinor"]) for p in resp.get_json()["data"]["prices"]] == [("KES", 100000)]
    resp = client.patch(f"/api/v1/circle/plans/{slug}", json={"prices": [{"currency": "USD", "amount": "10"}, {"currency": "KES", "amount": "1000"}]},
                        headers=auth_headers(admin))
    resp = client.patch(f"/api/v1/circle/plans/{slug}", json={"price": 1500, "currency": "KES"}, headers=auth_headers(admin))
    assert sorted((p["currency"], p["amountMinor"]) for p in resp.get_json()["data"]["prices"]) == [("KES", 150000), ("USD", 1000)]


def test_premium_resource_publish_requires_enabled_price(client, app, admin, protected_root):
    filename = f"{uuid.uuid4().hex}.pdf"
    (protected_root / filename).write_bytes(b"%PDF-1.4")
    base = {"name": "Toolkit", "accessType": "premium", "protectedFilePath": filename, "status": "published",
            "description": [{"type": "paragraph", "text": "A toolkit."}]}
    resp = client.post("/api/v1/resources", json={**base, "prices": [{"currency": "USD", "amount": "9", "enabled": False}]},
                       headers=auth_headers(admin))
    assert resp.status_code == 422
    resp = client.post("/api/v1/resources", json={**base, "prices": [{"currency": "USD", "amount": "9.50"}]},
                       headers=auth_headers(admin))
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["data"]["prices"][0]["amountMinor"] == 950
    public = client.get(f"/api/v1/resources/{resp.get_json()['data']['slug']}").get_json()["data"]
    assert public["prices"][0]["formatted"] == "$9.50"


# --- migration -------------------------------------------------------------------------------------------------


def _migration():
    return importlib.import_module("migrations.versions.a8d3f1c7e2b5_multi_currency_prices")


def test_migration_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    module = _migration()
    assert module.down_revision == "f2c6a8e4d1b9"
    config = Config()
    config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
    assert ScriptDirectory.from_config(config).get_heads() == ["a8d3f1c7e2b5"]


def test_migration_converts_legacy_prices_explicitly():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = _migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE circle_plans (id INTEGER PRIMARY KEY, price INTEGER, currency TEXT)"))
        conn.execute(sa.text("CREATE TABLE resources (id INTEGER PRIMARY KEY, price INTEGER, currency TEXT, access_type TEXT)"))
        conn.execute(sa.text("CREATE TABLE circle_payments (id INTEGER PRIMARY KEY, amount_subunits INTEGER)"))
        conn.execute(sa.text("INSERT INTO circle_plans VALUES (1, 1000, 'KES'), (2, 2500, 'JPY'), (3, 0, 'KES'), (4, 50, 'ZZZ'), (5, 20, 'usd')"))
        conn.execute(sa.text("INSERT INTO resources VALUES (1, 1500, 'KES', 'premium'), (2, 900, 'KES', 'direct_download'), (3, 0, 'USD', 'premium')"))
        conn.execute(sa.text("INSERT INTO circle_payments VALUES (1, 100000)"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        assert conn.execute(sa.text("SELECT plan_id, currency, amount_minor, enabled FROM circle_plan_prices ORDER BY plan_id")).fetchall() == [
            (1, "KES", 100000, 1), (2, "JPY", 2500, 1), (5, "USD", 2000, 1)]
        assert conn.execute(sa.text("SELECT resource_id, currency, amount_minor FROM resource_prices")).fetchall() == [(1, "KES", 150000)]
        # Legacy columns and historical payment snapshots are untouched.
        assert conn.execute(sa.text("SELECT price, currency FROM circle_plans WHERE id = 1")).one() == (1000, "KES")
        assert conn.execute(sa.text("SELECT amount_subunits FROM circle_payments")).scalar() == 100000
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
        tables = set(sa.inspect(conn).get_table_names())
        assert "circle_plan_prices" not in tables and "resource_prices" not in tables and "circle_plans" in tables
