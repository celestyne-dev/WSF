"""Money arithmetic for WSF checkout (Checkout Phase 1) — the ONE place an
amount is converted between a human/decimal value and integer minor units.

Replaces every `price * 100`: the exponent comes from the currency's real
ISO 4217 minor unit (app/services/currencies.py) — USD 19.99 -> 1999,
KES 2500 -> 250000, JPY 2500 -> 2500, KWD 1.250 -> 1250.

Never floating point: decimal input is parsed with Decimal from its string
form (a float argument is rejected outright, since 19.99 as a float is
already 19.989999…), and integer minor units are the only stored/charged
representation. Money is never silently rounded — an amount with more
decimal places than the currency allows is an error, not a rounding.
"""
from decimal import Decimal, InvalidOperation

from app.services.currencies import minor_unit, normalize_currency


class MoneyError(ValueError):
    pass


def to_minor_units(amount, currency):
    """Decimal/str/int `amount` in major units -> exact int minor units.
    Raises MoneyError for floats, non-numeric input, negative amounts, or
    more decimal places than `currency` has (no rounding, ever)."""
    if isinstance(amount, bool) or isinstance(amount, float):
        raise MoneyError("Money amounts must be given as a decimal string or integer, never a float.")
    exponent = minor_unit(currency)
    try:
        value = Decimal(str(amount).strip()) if not isinstance(amount, Decimal) else amount
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError("Amount is not a valid number.") from exc
    if not value.is_finite():
        raise MoneyError("Amount is not a valid number.")
    if value < 0:
        raise MoneyError("Amount cannot be negative.")
    scaled = value.scaleb(exponent)
    if scaled != scaled.to_integral_value():
        places = f"{exponent} decimal place{'s' if exponent != 1 else ''}" if exponent else "no decimal places"
        raise MoneyError(f"{normalize_currency(currency)} amounts allow {places}.")
    return int(scaled)


def from_minor_units(amount_minor, currency):
    """Exact int minor units -> Decimal major units with the currency's
    own number of decimal places (e.g. 1999 USD -> Decimal('19.99'))."""
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise MoneyError("Minor-unit amounts must be integers.")
    exponent = minor_unit(currency)
    return (Decimal(amount_minor).scaleb(-exponent)).quantize(Decimal(1).scaleb(-exponent))


def legacy_whole_units_to_minor(whole_units, currency):
    """The explicit legacy conversion: CirclePlan.price / Resource.price
    were integer WHOLE currency units (see their model docstrings), so
    1000 KES -> 100000, 2500 JPY -> 2500. Used by the Checkout Phase 1
    migration and by legacy `price`-only API writes — never inferred."""
    if isinstance(whole_units, bool) or not isinstance(whole_units, int) or whole_units < 0:
        raise MoneyError("Legacy prices are non-negative whole-unit integers.")
    return whole_units * (10 ** minor_unit(currency))


def format_money(amount_minor, currency):
    """Server-side display string, so no client ever does float math:
    "$19.99", "€9.00", "£5.00", otherwise "KES 2,500.00" / "JPY 2,500"."""
    from app.services.currencies import currency_info

    info = currency_info(currency)
    value = from_minor_units(amount_minor, info["code"])
    number = f"{value:,.{info['minorUnit']}f}"
    return f"{info['symbol']}{number}" if info["symbol"] else f"{info['code']} {number}"
