"""WSF Circle — public plans, the owner's own membership state
(/circle/me), and staff plan/subscription administration. See
app/models/circle.py for the CirclePlan/CircleSubscription architecture
and app/services/circle.py for the one authoritative entitlement rule
this module's /circle/me route calls rather than re-deriving.

Module 2 of the Paystack integration added CircleCheckoutResource/
CirclePaymentStatusResource below — a signed-in member may now initialize
and poll their own Paystack checkout. That is still the only self-service
path to membership: there is still no webhook route here, and only an
authorized circle.manage staff member may directly activate/modify a
subscription (see CircleSubscriptionListResource.post/
CircleSubscriptionDetailResource.patch below). All payment-triggered
entitlement changes instead run through
app/services/circle_payments.py's consume_verified_circle_payment() —
never through those staff-only routes, and never duplicated here.
"""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required, permission_required
from app.extensions import db, limiter
from app.models.circle import CirclePlan, CIRCLE_PLAN_STATUSES, CircleSubscription
from app.models.contact import ContactInquiry
from app.models.user import User
from app.schemas.circle import (
    CircleMembershipRequestInputSchema,
    CirclePlanInputSchema,
    CirclePlanSchema,
    CirclePlanUpdateSchema,
    CircleSubscriptionAdminCreateSchema,
    CircleSubscriptionAdminUpdateSchema,
    CircleSubscriptionSchema,
)
from app.services.audit import log_action
from app.services.circle import (
    create_subscription_for_user,
    get_circle_entitlement,
    validate_subscription_status_transition,
)
from app.services.circle_payments import get_payment_status, start_circle_checkout
from app.services.contact import generate_contact_reference
from app.services.content_blocks import sanitize_content_blocks
from app.services.notifications import notify_contact_received
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

circle_bp = Blueprint("circle", __name__)
api = Api(circle_bp)

plan_schema = CirclePlanSchema()
subscription_schema = CircleSubscriptionSchema()

# Fields an admin update is allowed to touch directly (no schema-level
# load_default, so a PATCH only ever changes what it actually sends —
# house partial-update convention). `status` is handled on its own, via
# validate_subscription_status_transition, never a free field write.
_SUBSCRIPTION_METADATA_FIELDS = (
    "provider", "provider_customer_id", "provider_subscription_id", "payment_reference",
    "starts_at", "current_period_start", "current_period_end",
)


def _current_user_or_none():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    return current_user if current_user else None


def _can_manage_or_none():
    user = _current_user_or_none()
    if user and user.has_permission("circle.manage"):
        return user
    return None


def _get_plan_or_404(slug):
    plan = CirclePlan.query.filter_by(slug=slug).first()
    if plan is None:
        raise ApiError("Plan not found.", 404, code="not_found")
    return plan


def _get_plan_by_id_or_404(plan_id):
    plan = db.session.get(CirclePlan, plan_id)
    if plan is None:
        raise ApiError("Plan not found.", 404, code="not_found")
    return plan


def _get_subscription_or_404(subscription_id):
    subscription = db.session.get(CircleSubscription, subscription_id)
    if subscription is None:
        raise ApiError("Subscription not found.", 404, code="not_found")
    return subscription


def _plan_is_referenced(plan):
    return CircleSubscription.query.filter_by(plan_id=plan.id).first() is not None


def build_public_plan_payload(plan):
    """Never exposes admin-only fields (display_order is an internal
    ordering hint, not shown — the public list is already pre-sorted by
    it). `checkoutAvailable` tells the client whether to render "Continue
    to secure checkout" vs. the safe "coming soon" state, without leaking
    the raw URL construction logic.
    """
    return {
        "slug": plan.slug,
        "name": plan.name,
        "shortDescription": plan.short_description,
        "description": plan.description or [],
        "billingInterval": plan.billing_interval,
        "price": plan.price,
        "currency": plan.currency,
        "featured": plan.featured,
        "benefits": plan.benefits or [],
        "checkoutAvailable": bool(plan.checkout_url),
        "checkoutUrl": plan.checkout_url,
        "seo": plan.seo or {},
    }


def _apply_plan_fields(plan, data):
    plan.name = data["name"]
    plan.short_description = data.get("short_description")
    plan.description = sanitize_content_blocks(data.get("description", []))
    plan.billing_interval = data.get("billing_interval", "monthly")
    plan.price = data.get("price", 0)
    plan.currency = data["currency"]  # required by CirclePlanInputSchema — no implicit default
    plan.status = data.get("status", "draft")
    plan.featured = data.get("featured", False)
    plan.display_order = data.get("display_order", 0)
    plan.checkout_url = data.get("checkout_url")
    plan.manage_billing_url = data.get("manage_billing_url")
    plan.benefits = data.get("benefits", [])
    plan.seo = data.get("seo")


def _validate_effective_period(subscription, data):
    """PATCH must validate the RESULTING period, not just the fields it
    happens to touch: a field absent from `data` keeps the subscription's
    existing value (house partial-update convention), so "effective"
    start/end are whichever of (submitted, existing) applies to each side
    independently. Must run before any field is mutated so a rejected
    PATCH leaves the subscription completely unchanged. The DB CHECK
    constraint (ck_circle_subscriptions_period_order) stays in place as
    defense in depth — this is the pre-commit, user-facing 422 version of
    the same rule.
    """
    start = data["current_period_start"] if "current_period_start" in data else subscription.current_period_start
    end = data["current_period_end"] if "current_period_end" in data else subscription.current_period_end
    if start is not None and end is not None and end < start:
        raise ApiError("Current period end cannot be before its start.", 422, code="invalid_period")


def build_owner_subscription_payload(subscription):
    if subscription is None:
        return None
    return {
        "id": subscription.id,
        "status": subscription.status,
        "source": subscription.source,
        "startsAt": subscription.starts_at.isoformat() if subscription.starts_at else None,
        "currentPeriodStart": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
        "currentPeriodEnd": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        "cancelAtPeriodEnd": subscription.cancel_at_period_end,
        "cancelledAt": subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
        "endedAt": subscription.ended_at.isoformat() if subscription.ended_at else None,
        "plan": build_public_plan_payload(subscription.plan) if subscription.plan else None,
    }


class CirclePlanListResource(Resource):
    def get(self):
        manager = _can_manage_or_none()
        query = CirclePlan.query.order_by(CirclePlan.featured.desc(), CirclePlan.display_order, CirclePlan.id)
        if manager and request.args.get("status"):
            query = query.filter(CirclePlan.status == request.args["status"])
        elif not manager:
            query = query.filter(CirclePlan.status == "active")
        plans = query.all()
        if manager:
            return success_response(plan_schema.dump(plans, many=True))
        return success_response([build_public_plan_payload(p) for p in plans])

    @permission_required("circle.manage")
    def post(self):
        data = CirclePlanInputSchema().load(request.get_json(silent=True) or {})
        plan = CirclePlan()
        if data.get("slug"):
            plan.slug = validate_explicit_slug(CirclePlan, data["slug"])
        else:
            plan.slug = generate_unique_slug(CirclePlan, data["name"])
        _apply_plan_fields(plan, data)
        db.session.add(plan)
        db.session.commit()
        log_action(current_user, "circle_plan.create", "CirclePlan", plan.id)
        return success_response(plan_schema.dump(plan), status=201)


class CirclePlanDetailResource(Resource):
    def get(self, slug):
        plan = _get_plan_or_404(slug)
        manager = _can_manage_or_none()
        if not plan.is_publicly_visible() and not manager:
            raise ApiError("Plan not found.", 404, code="not_found")
        if manager:
            return success_response(plan_schema.dump(plan))
        return success_response(build_public_plan_payload(plan))

    @permission_required("circle.manage")
    def patch(self, slug):
        plan = _get_plan_or_404(slug)
        data = CirclePlanUpdateSchema().load(request.get_json(silent=True) or {}, partial=True)
        if "slug" in data and data["slug"] and data["slug"] != plan.slug:
            plan.slug = validate_explicit_slug(CirclePlan, data["slug"], current_id=plan.id)

        for field in (
            "name", "short_description", "description", "billing_interval", "price", "currency",
            "status", "featured", "display_order", "checkout_url", "manage_billing_url", "benefits", "seo",
        ):
            if field in data:
                if field == "description":
                    plan.description = sanitize_content_blocks(data[field])
                else:
                    setattr(plan, field, data[field])

        db.session.commit()
        log_action(current_user, "circle_plan.update", "CirclePlan", plan.id)
        return success_response(plan_schema.dump(plan))

    @permission_required("circle.manage")
    def delete(self, slug):
        plan = _get_plan_or_404(slug)
        if _plan_is_referenced(plan):
            raise ApiError(
                "This plan is referenced by one or more subscriptions and can't be deleted. "
                "Archive it instead to keep historical membership data intact.",
                409,
                code="reference_conflict",
            )
        db.session.delete(plan)
        db.session.commit()
        log_action(current_user, "circle_plan.delete", "CirclePlan", plan.id)
        return success_response(None, status=204)


class CircleMeResource(Resource):
    """GET-only (spec: "GET only is sufficient for self-service
    subscription state in this phase" — no POST subscribe/activate for
    ordinary users; payment activation is admin/provider-side only).
    Strictly current_user-scoped — never accepts any kind of id.
    """

    @active_user_required
    def get(self):
        entitlement = get_circle_entitlement(current_user)
        subscription = entitlement["subscription"]
        return success_response(
            {
                "hasAccess": entitlement["has_access"],
                "subscription": build_owner_subscription_payload(subscription),
            }
        )


def _find_recent_circle_membership_request(email, subject):
    """Same accidental-double-submission guard as the public Contact form
    (app/api/v1/contact.py's _find_recent_duplicate) — an identical-subject
    request from the same email within a short window is treated as the
    same click, not a second lead.
    """
    window_start = datetime.now(timezone.utc) - timedelta(minutes=5)
    return ContactInquiry.query.filter(
        ContactInquiry.email == email,
        ContactInquiry.subject == subject,
        ContactInquiry.source == "circle_membership_request",
        ContactInquiry.created_at >= window_start,
    ).first()


class CircleMembershipRequestResource(Resource):
    """Phase 1 staff-assisted enrollment lead. No payment gateway exists
    yet (see this module's own docstring), so this is deliberately NOT a
    subscribe/activate endpoint — it only ever creates a staff-reviewable
    lead, reusing the existing ContactInquiry model/admin-review workflow
    (app/models/contact.py, app/api/v1/contact.py) rather than a new
    persistence model: ContactInquiry.source already exists precisely so a
    second entry point like this one doesn't need a schema change, and its
    own docstring's "deliberately excludes" list is about categories with
    a DEDICATED workflow — a WSF Circle lead has no dedicated workflow of
    its own yet, so the general inbox is the right fit for this phase.

    Never touches CircleSubscription in any way — name/email come from the
    authenticated account (never trusted from the request body), and the
    optional plan reference is only ever used to look up a real, currently
    active CirclePlan to quote back in the message staff will read.
    """

    @active_user_required
    def post(self):
        data = CircleMembershipRequestInputSchema().load(request.get_json(silent=True) or {})

        plan = None
        if data["plan_slug"]:
            plan = _get_plan_or_404(data["plan_slug"])
            if plan.status != "active":
                raise ApiError("That plan is not currently available.", 422, code="plan_not_active")

        subject = f"WSF Circle membership request — {plan.name}" if plan else "WSF Circle membership request"
        email = current_user.email.strip().lower()

        duplicate = _find_recent_circle_membership_request(email, subject)
        if duplicate is not None:
            return success_response({"reference": duplicate.reference, "status": "received"}, status=201)

        message_lines = ["A WSF Circle membership request was submitted from a signed-in WSF account."]
        if plan:
            message_lines.append(f"Plan of interest: {plan.name} ({plan.price} {plan.currency} / {plan.billing_interval}).")
        else:
            message_lines.append("No specific plan was selected.")
        note = (data.get("note") or "").strip()
        message_lines.append(f"Member note: {note}" if note else "Member note: (none provided)")

        inquiry = ContactInquiry(
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            email=email,
            inquiry_type="other",
            subject=subject,
            message="\n".join(message_lines),
            source="circle_membership_request",
            privacy_acknowledged=True,
        )
        db.session.add(inquiry)
        db.session.flush()
        inquiry.reference = generate_contact_reference(inquiry)
        db.session.commit()
        notify_contact_received(inquiry)

        log_action(
            current_user, "circle_membership_request.created", "ContactInquiry", inquiry.id,
            changes={"reference": inquiry.reference, "planSlug": plan.slug if plan else None},
        )
        return success_response({"reference": inquiry.reference, "status": "received"}, status=201)


class CircleCheckoutResource(Resource):
    """Module 2: start a Paystack hosted checkout for an active plan. The
    request body is never read — amount/currency/billing interval/
    customer email all come from the database and the authenticated
    session (see app/services/circle_payments.py's start_circle_checkout
    docstring) — so there is nothing in the body that could influence
    checkout terms even if a client sent one.
    """

    @limiter.limit("10 per minute")
    @active_user_required
    def post(self, slug):
        plan = _get_plan_or_404(slug)
        result = start_circle_checkout(current_user, plan)
        return success_response(
            {"reference": result["reference"], "authorizationUrl": result["authorization_url"]}, status=201
        )


class CirclePaymentStatusResource(Resource):
    """Module 2: owner-only payment status/verification — the function a
    future /circle/checkout/callback page will poll. Never accepts or
    trusts anything from the query string; verification against Paystack
    happens server-side only (see app/services/circle_payments.py).
    """

    @limiter.limit("30 per minute")
    @active_user_required
    def get(self, reference):
        status = get_payment_status(current_user, reference)
        return success_response(
            {
                "reference": status["reference"],
                "status": status["status"],
                "membershipActivated": status["membership_activated"],
                "reconciliationRequired": status["reconciliation_required"],
                "reason": status["reason"],
            }
        )


def _build_subscription_query():
    query = CircleSubscription.query.order_by(CircleSubscription.created_at.desc())
    query = apply_equality_filters(query, CircleSubscription, request.args, ["status", "plan_id", "source"])
    q = request.args.get("q")
    if q:
        query = query.join(User, CircleSubscription.user_id == User.id).filter(
            db.or_(User.email.ilike(f"%{q}%"), User.first_name.ilike(f"%{q}%"), User.last_name.ilike(f"%{q}%"))
        )
    return query


class CircleSubscriptionListResource(Resource):
    @permission_required("circle.manage")
    def get(self):
        result = paginate(_build_subscription_query(), subscription_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("circle.manage")
    def post(self):
        data = CircleSubscriptionAdminCreateSchema().load(request.get_json(silent=True) or {})
        email = data.pop("email").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user is None:
            raise ApiError("No WSF account currently uses this email.", 404, code="no_matching_account")

        plan = _get_plan_by_id_or_404(data.pop("plan_id"))
        status = data.pop("status", "pending")
        source = data.pop("source")

        subscription = create_subscription_for_user(user, plan, status, source, **data)
        log_action(
            current_user, "circle_subscription.create", "CircleSubscription", subscription.id,
            changes={"userId": user.id, "planId": plan.id, "status": status, "source": source},
        )
        return success_response(subscription_schema.dump(subscription), status=201)


class CircleSubscriptionDetailResource(Resource):
    @permission_required("circle.manage")
    def get(self, subscription_id):
        return success_response(subscription_schema.dump(_get_subscription_or_404(subscription_id)))

    @permission_required("circle.manage")
    def patch(self, subscription_id):
        subscription = _get_subscription_or_404(subscription_id)
        data = CircleSubscriptionAdminUpdateSchema().load(request.get_json(silent=True) or {}, partial=True)
        _validate_effective_period(subscription, data)

        if "status" in data:
            new_status = data.pop("status")
            old_status = subscription.status
            validate_subscription_status_transition(old_status, new_status)
            if new_status != old_status:
                subscription.status = new_status
                if new_status == "cancelled" and subscription.cancelled_at is None:
                    subscription.cancelled_at = db.func.now()
                if new_status in ("cancelled", "expired", "revoked") and subscription.ended_at is None:
                    subscription.ended_at = db.func.now()
                log_action(
                    current_user, "circle_subscription.status_change", "CircleSubscription", subscription.id,
                    changes={"from": old_status, "to": new_status},
                )

        if "cancel_at_period_end" in data:
            new_value = data.pop("cancel_at_period_end")
            if new_value != subscription.cancel_at_period_end:
                subscription.cancel_at_period_end = new_value
                log_action(
                    current_user, "circle_subscription.cancel_at_period_end_change", "CircleSubscription",
                    subscription.id, changes={"cancelAtPeriodEnd": new_value},
                )

        metadata_changed = {}
        for field in _SUBSCRIPTION_METADATA_FIELDS:
            if field in data:
                new_value = data[field]
                if getattr(subscription, field) != new_value:
                    metadata_changed[field] = True
                    setattr(subscription, field, new_value)
        if metadata_changed:
            log_action(
                current_user, "circle_subscription.metadata_update", "CircleSubscription", subscription.id,
                changes={"fields": sorted(metadata_changed.keys())},
            )

        db.session.commit()
        return success_response(subscription_schema.dump(subscription))


api.add_resource(CirclePlanListResource, "/plans")
api.add_resource(CirclePlanDetailResource, "/plans/<string:slug>")
api.add_resource(CircleCheckoutResource, "/plans/<string:slug>/checkout")
api.add_resource(CircleMeResource, "/me")
api.add_resource(CircleMembershipRequestResource, "/membership-requests")
api.add_resource(CirclePaymentStatusResource, "/payments/<string:reference>")
api.add_resource(CircleSubscriptionListResource, "/subscriptions")
api.add_resource(CircleSubscriptionDetailResource, "/subscriptions/<int:subscription_id>")
