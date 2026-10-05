from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.circle import (
    CIRCLE_PLAN_BILLING_INTERVALS,
    CIRCLE_PLAN_STATUSES,
    CIRCLE_SUBSCRIPTION_SOURCES,
    CIRCLE_SUBSCRIPTION_STATUSES,
    CirclePlan,
    CircleSubscription,
)
from app.schemas.user import UserSchema

# ISO 4217 is exactly three uppercase letters — Length(equal=3) alone (the
# convention elsewhere in app/schemas/commerce.py) would silently accept
# "usd" or "U$D"; Circle is a brand-new premium commercial surface, so
# this enforces the stricter rule the task spec calls for explicitly.
_CURRENCY_VALIDATE = validate.Regexp(r"^[A-Z]{3}$", error="Currency must be exactly 3 uppercase letters (ISO 4217).")
# http(s)-only — rejects javascript:/data:/file: and any other scheme
# (same validator already used for Member.website_url/linkedin_url in
# app/schemas/community.py).
_SAFE_URL_VALIDATE = validate.URL(require_tld=True, schemes={"http", "https"})


class CirclePlanSchema(ma.SQLAlchemyAutoSchema):
    """Admin-only full dump — see api/v1/circle.py's
    build_public_plan_payload() for the separate public-safe subset.
    """

    class Meta:
        model = CirclePlan
        load_instance = False


class CirclePlanInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription", validate=validate.Length(max=500))
    description = fields.List(fields.Dict(), required=False, load_default=list)
    billing_interval = fields.String(required=False, load_default="monthly", data_key="billingInterval", validate=validate.OneOf(CIRCLE_PLAN_BILLING_INTERVALS))
    price = fields.Integer(required=False, load_default=0, validate=validate.Range(min=0))
    # Required, no default: WSF is global and must not silently assume
    # USD for a plan the admin never gave a currency for.
    currency = fields.String(required=True, validate=_CURRENCY_VALIDATE)
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(CIRCLE_PLAN_STATUSES))
    featured = fields.Boolean(required=False, load_default=False)
    display_order = fields.Integer(required=False, load_default=0, data_key="displayOrder")
    checkout_url = fields.String(required=False, allow_none=True, data_key="checkoutUrl", validate=_SAFE_URL_VALIDATE)
    manage_billing_url = fields.String(required=False, allow_none=True, data_key="manageBillingUrl", validate=_SAFE_URL_VALIDATE)
    benefits = fields.List(fields.String(validate=validate.Length(max=300)), required=False, load_default=list)
    seo = fields.Dict(required=False, allow_none=True)


class CirclePlanUpdateSchema(ma.Schema):
    """PATCH /circle/plans/<slug> — no load_default anywhere (unlike
    CirclePlanInputSchema above, which is POST/create-only), so a key
    absent from a PATCH leaves that field untouched rather than being
    silently reset to its create-time default (house partial-update
    convention — see MemberAdminUpdateSchema in app/schemas/community.py).
    """

    name = fields.String(required=False, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription", validate=validate.Length(max=500))
    description = fields.List(fields.Dict(), required=False)
    billing_interval = fields.String(required=False, data_key="billingInterval", validate=validate.OneOf(CIRCLE_PLAN_BILLING_INTERVALS))
    price = fields.Integer(required=False, validate=validate.Range(min=0))
    currency = fields.String(required=False, validate=_CURRENCY_VALIDATE)
    status = fields.String(required=False, validate=validate.OneOf(CIRCLE_PLAN_STATUSES))
    featured = fields.Boolean(required=False)
    display_order = fields.Integer(required=False, data_key="displayOrder")
    checkout_url = fields.String(required=False, allow_none=True, data_key="checkoutUrl", validate=_SAFE_URL_VALIDATE)
    manage_billing_url = fields.String(required=False, allow_none=True, data_key="manageBillingUrl", validate=_SAFE_URL_VALIDATE)
    benefits = fields.List(fields.String(validate=validate.Length(max=300)), required=False)
    seo = fields.Dict(required=False, allow_none=True)


class CircleSubscriptionSchema(ma.SQLAlchemyAutoSchema):
    """Admin-only full dump (community.manage-gated call sites only) —
    includes provider/payment-reference metadata that must never reach a
    public or owner response (see api/v1/circle.py's owner payload
    builder, which is a separate, deliberately narrower function).
    """

    plan = fields.Nested(CirclePlanSchema, dump_only=True)
    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = CircleSubscription
        load_instance = False


class CircleSubscriptionAdminCreateSchema(ma.Schema):
    """POST /admin/circle/memberships — staff records a subscription for
    an EXISTING User, found by exact normalized email (see
    api/v1/circle.py). Never accepts a userId directly — email lookup
    only, matching the same exact-match pattern already used for Member
    account linking (app/services/community_accounts.py).
    """

    email = fields.Email(required=True)
    plan_id = fields.Integer(required=True, data_key="planId")
    status = fields.String(required=False, load_default="pending", validate=validate.OneOf(CIRCLE_SUBSCRIPTION_STATUSES))
    source = fields.String(required=True, validate=validate.OneOf(CIRCLE_SUBSCRIPTION_SOURCES))
    provider = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    provider_customer_id = fields.String(required=False, allow_none=True, data_key="providerCustomerId", validate=validate.Length(max=200))
    provider_subscription_id = fields.String(required=False, allow_none=True, data_key="providerSubscriptionId", validate=validate.Length(max=200))
    payment_reference = fields.String(required=False, allow_none=True, data_key="paymentReference", validate=validate.Length(max=200))
    starts_at = fields.DateTime(required=False, allow_none=True, data_key="startsAt")
    current_period_start = fields.DateTime(required=False, allow_none=True, data_key="currentPeriodStart")
    current_period_end = fields.DateTime(required=False, allow_none=True, data_key="currentPeriodEnd")
    cancel_at_period_end = fields.Boolean(required=False, load_default=False, data_key="cancelAtPeriodEnd")

    @validates_schema
    def validate_period_order(self, data, **kwargs):
        start = data.get("current_period_start")
        end = data.get("current_period_end")
        if start and end and end < start:
            raise ValidationError("Current period end cannot be before its start.", field_name="current_period_end")


class CircleMembershipRequestInputSchema(ma.Schema):
    """POST /circle/membership-requests — a Phase 1, staff-assisted
    enrollment lead (see CircleMembershipRequestResource, api/v1/circle.py).
    Deliberately tiny: name/email come from the authenticated account, not
    this payload, and there is no status/date/provider field here at all —
    this can never activate, create, or modify a CircleSubscription.
    """

    plan_slug = fields.String(required=False, allow_none=True, load_default=None, data_key="planSlug")
    note = fields.String(required=False, allow_none=True, load_default=None, validate=validate.Length(max=1000))


class CircleSubscriptionAdminUpdateSchema(ma.Schema):
    """PATCH /admin/circle/memberships/<id> — no load_default anywhere, so
    a key absent from the request leaves that field untouched (house
    partial-update convention). `status` transitions are validated
    separately against the explicit allowed-transition map (see
    app/services/circle.py) rather than accepted as a free OneOf here.
    """

    status = fields.String(required=False, validate=validate.OneOf(CIRCLE_SUBSCRIPTION_STATUSES))
    provider = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    provider_customer_id = fields.String(required=False, allow_none=True, data_key="providerCustomerId", validate=validate.Length(max=200))
    provider_subscription_id = fields.String(required=False, allow_none=True, data_key="providerSubscriptionId", validate=validate.Length(max=200))
    payment_reference = fields.String(required=False, allow_none=True, data_key="paymentReference", validate=validate.Length(max=200))
    starts_at = fields.DateTime(required=False, allow_none=True, data_key="startsAt")
    current_period_start = fields.DateTime(required=False, allow_none=True, data_key="currentPeriodStart")
    current_period_end = fields.DateTime(required=False, allow_none=True, data_key="currentPeriodEnd")
    cancel_at_period_end = fields.Boolean(required=False, data_key="cancelAtPeriodEnd")
