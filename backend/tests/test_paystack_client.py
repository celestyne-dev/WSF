"""app/services/paystack.py — the thin Paystack API client built in
Module 1 of the Paystack Circle integration. Every test here mocks
`requests.request`; nothing in this file makes a real network call, and
nothing here creates a CircleSubscription or changes entitlement.
"""
from unittest.mock import patch

import pytest

from app.services.paystack import (
    PaystackAPIError,
    PaystackNotConfiguredError,
    generate_reference,
    initialize_transaction,
    verify_transaction,
)


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, raise_json_error=False):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json_body = json_body
        self._raise_json_error = raise_json_error

    def json(self):
        if self._raise_json_error:
            raise ValueError("not json")
        return self._json_body


def _enable_paystack(app, secret="sk_test_abc123"):
    app.config["PAYSTACK_ENABLED"] = True
    app.config["PAYSTACK_SECRET_KEY"] = secret


class TestGenerateReference:
    def test_reference_uses_only_safe_characters(self):
        reference = generate_reference()
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.=")
        assert set(reference) <= allowed

    def test_reference_is_unique_across_calls(self):
        assert generate_reference() != generate_reference()


class TestNotConfigured:
    def test_disabled_raises_before_any_network_call(self, app):
        app.config["PAYSTACK_ENABLED"] = False
        with app.app_context(), patch("app.services.paystack.requests.request") as mock_request:
            with pytest.raises(PaystackNotConfiguredError):
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )
            mock_request.assert_not_called()

    def test_enabled_without_secret_raises_before_any_network_call(self, app):
        app.config["PAYSTACK_ENABLED"] = True
        app.config["PAYSTACK_SECRET_KEY"] = None
        with app.app_context(), patch("app.services.paystack.requests.request") as mock_request:
            with pytest.raises(PaystackNotConfiguredError):
                verify_transaction("ref1")
            mock_request.assert_not_called()


class TestInitializeTransaction:
    def test_correct_endpoint_and_method(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={
            "status": True, "message": "ok",
            "data": {"authorization_url": "https://checkout.paystack.com/abc", "access_code": "abc", "reference": "ref1"},
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake) as mock_request:
            initialize_transaction(
                amount_subunits=100000, email="a@example.com", reference="ref1",
                currency="KES", callback_url="https://example.com/cb",
            )
            args, kwargs = mock_request.call_args
            assert args[0] == "POST"
            assert args[1] == "https://api.paystack.co/transaction/initialize"

    def test_bearer_auth_header_sent(self, app):
        _enable_paystack(app, secret="sk_test_the_secret")
        fake = _FakeResponse(json_body={
            "status": True, "data": {"authorization_url": "https://x", "access_code": "a", "reference": "ref1"},
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake) as mock_request:
            initialize_transaction(
                amount_subunits=100000, email="a@example.com", reference="ref1",
                currency="KES", callback_url="https://example.com/cb",
            )
            _, kwargs = mock_request.call_args
            assert kwargs["headers"]["Authorization"] == "Bearer sk_test_the_secret"

    def test_amount_sent_as_integer_subunits_unchanged(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={
            "status": True, "data": {"authorization_url": "https://x", "access_code": "a", "reference": "ref1"},
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake) as mock_request:
            initialize_transaction(
                amount_subunits=150000, email="a@example.com", reference="ref1",
                currency="KES", callback_url="https://example.com/cb",
            )
            _, kwargs = mock_request.call_args
            assert kwargs["json"]["amount"] == 150000
            assert isinstance(kwargs["json"]["amount"], int)

    def test_email_reference_currency_callback_sent_correctly(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={
            "status": True, "data": {"authorization_url": "https://x", "access_code": "a", "reference": "ref1"},
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake) as mock_request:
            initialize_transaction(
                amount_subunits=100000, email="buyer@example.com", reference="my-ref-1",
                currency="KES", callback_url="https://example.com/cb",
            )
            _, kwargs = mock_request.call_args
            body = kwargs["json"]
            assert body["email"] == "buyer@example.com"
            assert body["reference"] == "my-ref-1"
            assert body["currency"] == "KES"
            assert body["callback_url"] == "https://example.com/cb"

    def test_metadata_serialized_when_given(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={
            "status": True, "data": {"authorization_url": "https://x", "access_code": "a", "reference": "ref1"},
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake) as mock_request:
            initialize_transaction(
                amount_subunits=100000, email="a@example.com", reference="ref1",
                currency="KES", callback_url="https://example.com/cb",
                metadata={"plan_id": 7, "user_id": 42},
            )
            _, kwargs = mock_request.call_args
            assert kwargs["json"]["metadata"] == {"plan_id": 7, "user_id": 42}

    def test_metadata_omitted_when_not_given(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={
            "status": True, "data": {"authorization_url": "https://x", "access_code": "a", "reference": "ref1"},
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake) as mock_request:
            initialize_transaction(
                amount_subunits=100000, email="a@example.com", reference="ref1",
                currency="KES", callback_url="https://example.com/cb",
            )
            _, kwargs = mock_request.call_args
            assert "metadata" not in kwargs["json"]

    def test_response_parsed_into_authorization_url_access_code_reference(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={
            "status": True,
            "data": {
                "authorization_url": "https://checkout.paystack.com/3ni8kdavz62431k",
                "access_code": "3ni8kdavz62431k",
                "reference": "re4lyvq3s3",
            },
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            result = initialize_transaction(
                amount_subunits=100000, email="a@example.com", reference="re4lyvq3s3",
                currency="KES", callback_url="https://example.com/cb",
            )
            assert result == {
                "authorization_url": "https://checkout.paystack.com/3ni8kdavz62431k",
                "access_code": "3ni8kdavz62431k",
                "reference": "re4lyvq3s3",
            }

    def test_timeout_raises_paystack_api_error(self, app):
        import requests

        _enable_paystack(app)
        with app.app_context(), patch("app.services.paystack.requests.request", side_effect=requests.Timeout("boom")):
            with pytest.raises(PaystackAPIError):
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )

    def test_network_error_raises_paystack_api_error(self, app):
        import requests

        _enable_paystack(app)
        with app.app_context(), patch(
            "app.services.paystack.requests.request", side_effect=requests.ConnectionError("boom")
        ):
            with pytest.raises(PaystackAPIError):
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )

    def test_non_success_http_status_raises_paystack_api_error(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(status_code=401, json_body={"status": False, "message": "Invalid key"})
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            with pytest.raises(PaystackAPIError, match="Invalid key"):
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )

    def test_status_false_with_200_raises_paystack_api_error(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(status_code=200, json_body={"status": False, "message": "Duplicate reference"})
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            with pytest.raises(PaystackAPIError, match="Duplicate reference"):
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )

    def test_malformed_json_raises_paystack_api_error(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(raise_json_error=True)
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            with pytest.raises(PaystackAPIError):
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )

    def test_response_missing_authorization_url_raises(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={"status": True, "data": {"access_code": "a", "reference": "ref1"}})
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            with pytest.raises(PaystackAPIError):
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )

    def test_response_missing_data_object_raises(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={"status": True})
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            with pytest.raises(PaystackAPIError):
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )

    def test_secret_never_appears_in_error_message(self, app):
        _enable_paystack(app, secret="sk_test_super_secret_value")
        fake = _FakeResponse(status_code=401, json_body={"status": False, "message": "Invalid key"})
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            try:
                initialize_transaction(
                    amount_subunits=100000, email="a@example.com", reference="ref1",
                    currency="KES", callback_url="https://example.com/cb",
                )
                assert False, "expected PaystackAPIError"
            except PaystackAPIError as exc:
                assert "sk_test_super_secret_value" not in str(exc)


class TestVerifyTransaction:
    def test_correct_reference_url(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={
            "status": True,
            "data": {"status": "success", "amount": 100000, "currency": "KES", "customer": {"email": "a@example.com"}},
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake) as mock_request:
            verify_transaction("my-ref-99")
            args, _ = mock_request.call_args
            assert args[0] == "GET"
            assert args[1] == "https://api.paystack.co/transaction/verify/my-ref-99"

    def test_successful_response_normalized(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={
            "status": True,
            "data": {
                "status": "success",
                "amount": 100000,
                "currency": "KES",
                "customer": {"email": "buyer@example.com"},
                "id": 4099819076,
                "channel": "card",
                "paid_at": "2026-10-05T12:00:00.000Z",
                "gateway_response": "Successful",
            },
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            result = verify_transaction("my-ref-99")
            assert result["status"] == "success"
            assert result["amount"] == 100000
            assert result["currency"] == "KES"
            assert result["customer_email"] == "buyer@example.com"
            assert result["channel"] == "card"
            assert result["paid_at"] == "2026-10-05T12:00:00.000Z"
            assert result["gateway_response"] == "Successful"

    def test_provider_transaction_id_returned_as_string(self, app):
        _enable_paystack(app)
        # A large id, well within Paystack's documented unsigned-64-bit
        # range but beyond what a naive 32-bit integer column could hold —
        # confirming this module never tries to store it as a Python int
        # in a way that could get truncated downstream.
        fake = _FakeResponse(json_body={
            "status": True,
            "data": {"status": "success", "amount": 100000, "currency": "KES", "customer": {}, "id": 18446744073709551615},
        })
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            result = verify_transaction("my-ref-99")
            assert result["provider_transaction_id"] == "18446744073709551615"
            assert isinstance(result["provider_transaction_id"], str)

    def test_failed_abandoned_pending_statuses_kept_distinguishable(self, app):
        _enable_paystack(app)
        for raw_status in ("failed", "abandoned", "pending"):
            fake = _FakeResponse(json_body={
                "status": True,
                "data": {"status": raw_status, "amount": 100000, "currency": "KES", "customer": {}},
            })
            with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
                result = verify_transaction("my-ref-99")
                assert result["status"] == raw_status

    def test_timeout_raises_paystack_api_error(self, app):
        import requests

        _enable_paystack(app)
        with app.app_context(), patch("app.services.paystack.requests.request", side_effect=requests.Timeout("boom")):
            with pytest.raises(PaystackAPIError):
                verify_transaction("my-ref-99")

    def test_malformed_response_raises_paystack_api_error(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(raise_json_error=True)
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            with pytest.raises(PaystackAPIError):
                verify_transaction("my-ref-99")

    def test_response_missing_required_fields_raises(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body={"status": True, "data": {"currency": "KES"}})
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            with pytest.raises(PaystackAPIError):
                verify_transaction("my-ref-99")

    def test_non_dict_json_body_raises(self, app):
        _enable_paystack(app)
        fake = _FakeResponse(json_body=["not", "a", "dict"])
        with app.app_context(), patch("app.services.paystack.requests.request", return_value=fake):
            with pytest.raises(PaystackAPIError):
                verify_transaction("my-ref-99")
