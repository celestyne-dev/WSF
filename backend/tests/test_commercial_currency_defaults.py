"""Focused tests for the KES-default commercial currency change.

Scope: ResourceInputSchema/ProductInputSchema now default a missing
currency to KES instead of USD (schemas/resource.py, schemas/commerce.py).
Circle's "currency is required, no implicit default" rule is intentionally
NOT re-tested here — it's already covered in depth by test_circle.py's
TestPlans currency.1-currency.5 tests, which this change does not touch.
"""

import pytest
from marshmallow import ValidationError

from app.schemas.commerce import ProductInputSchema
from app.schemas.resource import ResourceInputSchema


def test_resource_input_schema_defaults_missing_currency_to_kes():
    data = ResourceInputSchema().load({"name": "A Resource"})
    assert data["currency"] == "KES"


def test_resource_input_schema_preserves_explicit_usd():
    data = ResourceInputSchema().load({"name": "A Resource", "currency": "USD"})
    assert data["currency"] == "USD"


def test_product_input_schema_defaults_missing_currency_to_kes():
    data = ProductInputSchema().load({"name": "A Product", "price": 1000})
    assert data["currency"] == "KES"


def test_product_input_schema_preserves_explicit_usd():
    data = ProductInputSchema().load({"name": "A Product", "price": 1000, "currency": "USD"})
    assert data["currency"] == "USD"


def test_circle_plan_input_schema_still_requires_explicit_currency():
    """Unchanged by this task — reconfirmed here as a guard against a future
    regression, since it's the one schema this change deliberately does
    NOT touch (see spec section 4 and app/schemas/circle.py's own comment).
    """
    from app.schemas.circle import CirclePlanInputSchema

    with pytest.raises(ValidationError):
        CirclePlanInputSchema().load({"name": "A Plan", "price": 1000})
