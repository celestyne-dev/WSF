"""Payment provider capability registry (WSF Checkout Phase 1).

Four separate concepts, never conflated:
  PROVIDER  — who processes the charge (Paystack today; PayPal later)
  METHOD    — how the customer pays on the provider's hosted page
  CURRENCY  — what the charge is denominated in
  PRICE     — the admin-set amount (CirclePlanPrice / ResourcePrice)

Each provider declares what it can actually do. A method or currency is
only ever offered when the provider definition here says it is
supported — an admin toggle can narrow this, never widen it. Adding a
provider later (e.g. "paypal") means adding one definition plus its
verified gateway integration; Circle/Resource entitlement code is not
touched, because checkout only asks this registry "which provider +
channels can take this currency for this transaction type?".

Secrets never live here or in payment settings — credentials stay in
environment config (PAYSTACK_SECRET_KEY); `is_configured` only reports
yes/no.
"""
from flask import current_app

TRANSACTION_CIRCLE_MEMBERSHIP = "circle_membership"
TRANSACTION_RESOURCE_PURCHASE = "resource_purchase"


class ProviderDefinition:
    def __init__(self, key, label, currencies, methods, transaction_types, is_configured):
        self.key = key
        self.label = label
        # Currencies this provider/account can charge — never a guess.
        self.currencies = tuple(currencies)
        # method key -> {"label", "description", "currencies": tuple|None (None = all provider currencies)}
        self.methods = methods
        self.transaction_types = frozenset(transaction_types)
        self._is_configured = is_configured

    def is_configured(self):
        return bool(self._is_configured())

    def methods_for_currency(self, currency):
        return [
            key for key, spec in self.methods.items()
            if currency in self.currencies and (spec.get("currencies") is None or currency in spec["currencies"])
        ]


def _paystack_configured():
    config = current_app.config
    return bool(config.get("PAYSTACK_ENABLED")) and bool(config.get("PAYSTACK_SECRET_KEY"))


def _paystack_account_currencies():
    """Paystack's Kenya merchant capability (KES, USD) narrowed further by
    the deployment's own PAYSTACK_ALLOWED_CURRENCIES env allowlist (see
    config.py) — so a currency the WSF account hasn't been confirmed for
    can never be charged just because an admin enabled it."""
    allowed = {c.strip().upper() for c in (current_app.config.get("PAYSTACK_ALLOWED_CURRENCIES") or [])}
    return tuple(c for c in PAYSTACK_CURRENCIES if c in allowed)


# WSF's Kenya Paystack account: the only currencies Paystack can collect
# for a Kenyan merchant. Nothing else is ever sent to Paystack.
PAYSTACK_CURRENCIES = ("KES", "USD")

# The only Paystack hosted-checkout `channels` WSF supports, in admin
# display order. Card covers Visa/Mastercard (and supported American
# Express) in ONE channel; google_pay and apple_pay are wallet channels on
# top of card (Google Pay additionally REQUIRES card to be enabled — see
# payment_settings.validate_payment_settings); mobile_money is one channel
# (M-PESA and other Kenyan mobile money on Paystack's own page) and is
# KES-only. Unsupported channels (ussd, eft, bank_transfer, qr,
# capitec_pay, ...) are deliberately absent.
PAYSTACK_METHODS = {
    "card": {
        "label": "Card",
        "description": "Visa, Mastercard and supported American Express cards.",
        "currencies": None,
    },
    "google_pay": {
        "label": "Google Pay",
        "description": "Google Pay on supported devices, browsers and eligible cards.",
        "currencies": None,
    },
    "apple_pay": {
        "label": "Apple Pay",
        "description": "Apple Pay on supported devices and browsers.",
        "currencies": None,
    },
    "mobile_money": {
        "label": "Mobile Money / M-PESA",
        "description": "M-PESA and other supported Kenyan mobile money (KES only).",
        "currencies": ("KES",),
    },
}


def _paystack_definition():
    return ProviderDefinition(
        key="paystack",
        label="Paystack",
        currencies=_paystack_account_currencies(),
        methods=PAYSTACK_METHODS,
        transaction_types=(TRANSACTION_CIRCLE_MEMBERSHIP, TRANSACTION_RESOURCE_PURCHASE),
        is_configured=_paystack_configured,
    )


# Provider registry, in preference order. Phase 2 adds "paypal" here.
PROVIDER_KEYS = ("paystack",)
_FACTORIES = {"paystack": _paystack_definition}


def get_provider(key):
    factory = _FACTORIES.get(key)
    return factory() if factory else None


def provider_method_keys(key):
    """Static method keys a provider supports (for settings validation)."""
    return tuple({"paystack": PAYSTACK_METHODS}.get(key, {}))
