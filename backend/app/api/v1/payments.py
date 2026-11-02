"""GET /api/v1/payments/config (WSF Checkout Phase 1) — the minimum
non-secret checkout configuration a client needs: the ISO 4217 currency
catalogue (for the admin pricing editors' currency dropdown), the global
default currency and the enabled currencies. Never any provider
credential, configuration error, or which provider is configured — per-
item checkout availability already ships with each plan/resource's own
`prices`. Read-only; changing it is Admin Settings -> Payments.
"""
from flask import Blueprint
from flask_restful import Api, Resource

from app.services.currencies import currency_catalogue
from app.services.payment_settings import get_payment_settings
from app.utils.responses import success_response

payments_bp = Blueprint("payments", __name__)
api = Api(payments_bp)


class PaymentConfigResource(Resource):
    def get(self):
        settings = get_payment_settings()
        return success_response(
            {
                "defaultCurrency": settings["defaultCurrency"],
                "enabledCurrencies": settings["enabledCurrencies"],
                "currencies": currency_catalogue(),
            }
        )


api.add_resource(PaymentConfigResource, "/config")
