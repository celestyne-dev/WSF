"""Multi-currency price options shared by Circle plans and premium
Resources (WSF Checkout Phase 1). One validation schema, one apply
function, one public/admin serializer — used by both parents so their
pricing rules can never drift.

Admin input never carries floats: each option is
    {"currency": "USD", "amount": "19.99", "enabled": true}
where `amount` is a decimal STRING in major units, converted server-side
to integer minor units by app/services/money.py (no rounding — too many
decimals is an error). An integer `amountMinor` is accepted instead of
`amount` for API clients that already work in minor units.
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load, validates_schema

from app.services.currencies import UnknownCurrencyError, normalize_currency
from app.services.money import MoneyError, format_money, from_minor_units, legacy_whole_units_to_minor, to_minor_units
from app.services.payment_settings import available_checkout_currencies, get_payment_settings
from app.services.payment_providers import PAYSTACK_METHODS

MAX_PRICE_OPTIONS = 20


class PriceOptionSchema(Schema):
    currency = fields.String(required=True)
    amount = fields.Raw(required=False, allow_none=True)
    amount_minor = fields.Integer(required=False, allow_none=True, data_key="amountMinor", strict=True)
    enabled = fields.Boolean(required=False, load_default=True)

    class Meta:
        unknown = EXCLUDE

    @validates_schema
    def _check(self, data, **kwargs):
        try:
            normalize_currency(data.get("currency"))
        except UnknownCurrencyError:
            raise ValidationError({"currency": ["Choose a valid ISO 4217 currency."]})
        if data.get("amount") is None and data.get("amount_minor") is None:
            raise ValidationError({"amount": ["Enter an amount."]})

    @post_load
    def _to_minor(self, data, **kwargs):
        currency = normalize_currency(data["currency"])
        if data.get("amount") is not None:
            if not isinstance(data["amount"], (str, int)) or isinstance(data["amount"], bool):
                raise ValidationError({"amount": ["Enter the amount as a decimal string, e.g. \"19.99\"."]})
            try:
                amount_minor = to_minor_units(data["amount"], currency)
            except MoneyError as exc:
                raise ValidationError({"amount": [str(exc)]})
        else:
            amount_minor = data["amount_minor"]
        if amount_minor <= 0:
            raise ValidationError({"amount": ["The amount must be greater than zero."]})
        return {"currency": currency, "amount_minor": amount_minor, "enabled": data.get("enabled", True)}


def _validate_price_list(options):
    if len(options) > MAX_PRICE_OPTIONS:
        raise ValidationError(f"At most {MAX_PRICE_OPTIONS} prices.")
    seen = set()
    for option in options:
        if option["currency"] in seen:
            raise ValidationError(f"{option['currency']} is listed more than once — one price per currency.")
        seen.add(option["currency"])


def prices_field():
    """No load_default: omitted on update -> price rows untouched."""
    return fields.List(fields.Nested(PriceOptionSchema), required=False, validate=_validate_price_list)


def apply_prices(parent, options, price_model):
    """Replace `parent.prices` with exactly `options` (upsert by currency,
    remove currencies no longer listed). Payments already initialized keep
    their own snapshots, so this never affects an in-flight checkout."""
    existing = {p.currency: p for p in parent.prices}
    wanted = {o["currency"]: o for o in options}
    for currency, row in existing.items():
        if currency not in wanted:
            parent.prices.remove(row)
    for currency, option in wanted.items():
        row = existing.get(currency)
        if row is None:
            parent.prices.append(price_model(currency=currency, amount_minor=option["amount_minor"], enabled=option["enabled"]))
        else:
            row.amount_minor = option["amount_minor"]
            row.enabled = option["enabled"]


def apply_legacy_price(parent, price, currency, price_model):
    """Legacy `price`(whole units)+`currency` write from an older API client:
    explicitly converted (same rule as the Phase 1 migration) and upserted
    as THAT currency's row only — other currencies are left alone. A zero
    price changes nothing (legacy 0 meant "not priced")."""
    if not price or price <= 0:
        return
    try:
        code = normalize_currency(currency)
    except UnknownCurrencyError:
        return
    amount_minor = legacy_whole_units_to_minor(price, code)
    for row in parent.prices:
        if row.currency == code:
            row.amount_minor = amount_minor
            row.enabled = True
            return
    parent.prices.append(price_model(currency=code, amount_minor=amount_minor, enabled=True))


def enabled_prices(parent):
    return [p for p in parent.prices if p.enabled and p.amount_minor > 0]


def find_enabled_price(parent, currency):
    try:
        code = normalize_currency(currency)
    except UnknownCurrencyError:
        return None
    return next((p for p in enabled_prices(parent) if p.currency == code), None)


def admin_prices_payload(parent):
    return [
        {
            "currency": p.currency,
            "amountMinor": p.amount_minor,
            "amount": str(from_minor_units(p.amount_minor, p.currency)),
            "formatted": format_money(p.amount_minor, p.currency),
            "enabled": p.enabled,
        }
        for p in parent.prices
    ]


def _method_labels(channels):
    return [{"key": c, "label": PAYSTACK_METHODS[c]["label"]} for c in channels if c in PAYSTACK_METHODS]


def public_pricing_payload(parent, transaction_type):
    """Public: enabled prices only, each with server-formatted text and
    whether it can be checked out right now (and with which payment
    options), plus the default currency to preselect. No secrets, no
    provider internals beyond the method labels a buyer needs."""
    settings = get_payment_settings()
    options = enabled_prices(parent)
    checkout = available_checkout_currencies([p.currency for p in options], transaction_type, settings)
    prices = []
    for p in options:
        decision = checkout.get(p.currency)
        prices.append({
            "currency": p.currency,
            "amountMinor": p.amount_minor,
            "amount": str(from_minor_units(p.amount_minor, p.currency)),
            "formatted": format_money(p.amount_minor, p.currency),
            "checkoutAvailable": decision is not None,
            "paymentMethods": _method_labels(decision["channels"]) if decision else [],
        })
    currencies = [p["currency"] for p in prices]
    default = settings["defaultCurrency"]
    if default not in currencies:
        payable = [p["currency"] for p in prices if p["checkoutAvailable"]]
        default = payable[0] if payable else (currencies[0] if currencies else None)
    return {"prices": prices, "defaultCurrency": default}


def checkout_currency_for(parent, requested):
    """The currency a checkout will use: the requested one if given, else
    the global default if this item is priced in it, else the item's only
    enabled price. Never an amount — only which stored row to load."""
    if requested:
        return requested
    options = enabled_prices(parent)
    default = get_payment_settings()["defaultCurrency"]
    if any(p.currency == default for p in options):
        return default
    return options[0].currency if options else None
