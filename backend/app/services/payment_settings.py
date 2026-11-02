"""Global payment settings (WSF Checkout Phase 1) — the admin-controlled,
NON-SECRET checkout configuration, stored as one validated SiteSetting
row (key "payment_settings"), same pattern as site_identity:

    {
      "defaultCurrency": "USD",
      "enabledCurrencies": ["USD", "KES"],
      "providers": {"paystack": {"enabled": true,
                                 "methods": {"card": true, "apple_pay": false, "mobile_money": true}}}
    }

Secrets (Paystack secret key, webhook secret, any future PayPal client
secret) never live here — they stay in environment config.

resolve_checkout() is the single server-side decision every checkout
makes: given a currency and transaction type, which provider and which
hosted-checkout channels are allowed — only when the provider is
enabled AND configured AND supports the currency AND the transaction
type AND at least one enabled method fits that currency.
"""
import copy

from app.extensions import db
from app.models.cms import SiteSetting
from app.services.currencies import UnknownCurrencyError, normalize_currency
from app.services.payment_providers import PROVIDER_KEYS, get_provider, provider_method_keys
from app.utils.responses import ApiError

PAYMENT_SETTINGS_KEY = "payment_settings"

# Production defaults when no row has ever been saved: keep today's
# working Paystack checkout (card + mobile money for KES) alive after
# deploy, add USD, and keep Apple Pay OFF until an admin turns it on —
# Paystack Apple Pay needs account/domain setup WSF can't verify here.
DEFAULT_PAYMENT_SETTINGS = {
    "defaultCurrency": "USD",
    "enabledCurrencies": ["USD", "KES"],
    "providers": {
        "paystack": {"enabled": True, "methods": {"card": True, "apple_pay": False, "mobile_money": True}},
    },
}


class PaymentSettingsError(ValueError):
    pass


def validate_payment_settings(raw):
    """Strict validation; returns the normalized dict or raises
    PaymentSettingsError with a field-specific message."""
    if not isinstance(raw, dict):
        raise PaymentSettingsError("Payment settings must be an object.")
    unknown = set(raw) - {"defaultCurrency", "enabledCurrencies", "providers"}
    if unknown:
        raise PaymentSettingsError(f"Unknown payment setting(s): {', '.join(sorted(unknown))}.")

    currencies = raw.get("enabledCurrencies")
    if not isinstance(currencies, list) or not currencies:
        raise PaymentSettingsError("Enable at least one currency.")
    normalized = []
    for code in currencies:
        try:
            value = normalize_currency(code)
        except UnknownCurrencyError:
            raise PaymentSettingsError(f"{code!r} is not a valid ISO 4217 currency code.")
        if value in normalized:
            raise PaymentSettingsError(f"{value} is listed more than once.")
        normalized.append(value)

    try:
        default = normalize_currency(raw.get("defaultCurrency"))
    except UnknownCurrencyError:
        raise PaymentSettingsError("The default currency must be a valid ISO 4217 code.")
    if default not in normalized:
        raise PaymentSettingsError("The default currency must be one of the enabled currencies.")

    providers_raw = raw.get("providers") or {}
    if not isinstance(providers_raw, dict):
        raise PaymentSettingsError("providers must be an object.")
    unknown_providers = set(providers_raw) - set(PROVIDER_KEYS)
    if unknown_providers:
        raise PaymentSettingsError(f"Unsupported payment provider(s): {', '.join(sorted(unknown_providers))}.")
    providers = {}
    for key in PROVIDER_KEYS:
        entry = providers_raw.get(key) or copy.deepcopy(
            DEFAULT_PAYMENT_SETTINGS["providers"].get(key, {"enabled": False, "methods": {}})
        )
        if not isinstance(entry, dict) or not isinstance(entry.get("enabled"), bool):
            raise PaymentSettingsError(f"{key}.enabled must be true or false.")
        methods_raw = entry.get("methods") or {}
        if not isinstance(methods_raw, dict):
            raise PaymentSettingsError(f"{key}.methods must be an object.")
        allowed_methods = provider_method_keys(key)
        unsupported = set(methods_raw) - set(allowed_methods)
        if unsupported:
            raise PaymentSettingsError(f"Unsupported {key} payment method(s): {', '.join(sorted(unsupported))}.")
        methods = {}
        for method in allowed_methods:
            value = methods_raw.get(method, False)
            if not isinstance(value, bool):
                raise PaymentSettingsError(f"{key}.methods.{method} must be true or false.")
            methods[method] = value
        providers[key] = {"enabled": entry["enabled"], "methods": methods}

    return {"defaultCurrency": default, "enabledCurrencies": normalized, "providers": providers}


def get_payment_settings():
    """The stored settings (validated), or the production defaults when
    nothing has been saved yet. A corrupt stored blob never crashes
    checkout — it falls back to the defaults."""
    setting = db.session.get(SiteSetting, PAYMENT_SETTINGS_KEY)
    if setting is not None and isinstance(setting.value, dict):
        try:
            return validate_payment_settings(setting.value)
        except PaymentSettingsError:
            pass
    return validate_payment_settings(copy.deepcopy(DEFAULT_PAYMENT_SETTINGS))


def save_payment_settings(raw):
    settings = validate_payment_settings(raw)
    setting = db.session.get(SiteSetting, PAYMENT_SETTINGS_KEY)
    if setting is None:
        setting = SiteSetting(key=PAYMENT_SETTINGS_KEY)
        db.session.add(setting)
    setting.value = settings
    return settings


def resolve_checkout(currency, transaction_type, settings=None):
    """Returns {"provider": key, "currency": code, "channels": [...]} for
    the first provider that can take this charge, or None. Pure decision —
    no I/O beyond reading settings/config."""
    settings = settings or get_payment_settings()
    try:
        currency = normalize_currency(currency)
    except UnknownCurrencyError:
        return None
    if currency not in settings["enabledCurrencies"]:
        return None
    for key in PROVIDER_KEYS:
        provider_settings = settings["providers"].get(key) or {}
        if not provider_settings.get("enabled"):
            continue
        provider = get_provider(key)
        if provider is None or not provider.is_configured():
            continue
        if transaction_type not in provider.transaction_types:
            continue
        channels = [m for m in provider.methods_for_currency(currency) if provider_settings["methods"].get(m)]
        if channels:
            return {"provider": key, "currency": currency, "channels": channels}
    return None


def available_checkout_currencies(currencies, transaction_type, settings=None):
    """Of `currencies` (an item's enabled price currencies), those that can
    actually be checked out right now, with their channels."""
    settings = settings or get_payment_settings()
    result = {}
    for currency in currencies:
        decision = resolve_checkout(currency, transaction_type, settings)
        if decision:
            result[decision["currency"]] = decision
    return result


def admin_payment_settings_payload():
    """Admin view: settings + read-only provider capability/configured
    status. Never any secret value."""
    from app.services.currencies import currency_catalogue
    from app.services.payment_providers import PAYSTACK_METHODS

    settings = get_payment_settings()
    providers = {}
    for key in PROVIDER_KEYS:
        provider = get_provider(key)
        providers[key] = {
            "label": provider.label,
            "configured": provider.is_configured(),
            "currencies": list(provider.currencies),
            "methods": [
                {"key": m, "label": spec["label"], "description": spec["description"],
                 "currencies": list(spec["currencies"]) if spec["currencies"] else list(provider.currencies)}
                for m, spec in PAYSTACK_METHODS.items()
            ] if key == "paystack" else [],
        }
    return {"settings": settings, "providers": providers, "currencies": currency_catalogue()}


def ensure_checkout_or_error(currency, transaction_type):
    """The decision, or a safe user-facing error — never a checkout with no
    valid provider/method. `currency_not_supported`: no enabled provider
    capability covers this currency at all. `payment_unavailable`: the
    currency is fine but every provider/method that could take it is
    disabled or unconfigured right now."""
    settings = get_payment_settings()
    decision = resolve_checkout(currency, transaction_type, settings)
    if decision is not None:
        return decision
    capable = False
    try:
        code = normalize_currency(currency)
        if code in settings["enabledCurrencies"]:
            capable = any(code in (get_provider(k).currencies if get_provider(k) else ()) for k in PROVIDER_KEYS)
    except UnknownCurrencyError:
        pass
    if capable:
        raise ApiError("Online payment is temporarily unavailable. Please try again later.", 503, code="payment_unavailable")
    raise ApiError("Online payment isn't available in this currency right now.", 422, code="currency_not_supported")
