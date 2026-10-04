"""WSF Circle — public plans, the owner's own membership state
(/circle/me), and staff plan/subscription administration. See
app/models/circle.py for the CirclePlan/CircleSubscription architecture
and app/services/circle.py for the one authoritative entitlement rule
this module's /circle/me route calls rather than re-deriving.

No payment gateway is wired up (see app/models/commerce.py's Order for
the same stance) and no webhook route exists here on purpose — only an
authorized circle.manage staff member may ever activate/modify a
subscription (see CircleSubscriptionListResource.post/
CircleSubscriptionDetailResource.patch below).
"""
from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required, permission_required
from app.extensions import db
from app.models.circle import CirclePlan, CIRCLE_PLAN_STATUSES, CircleSubscription
from app.models.user import User
from app.schemas.circle import (
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
from app.services.content_blocks import sanitize_content_blocks
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
    plan.currency = data.get("currency", "USD")
    plan.status = data.get("status", "draft")
    plan.featured = data.get("featured", False)
    plan.display_order = data.get("display_order", 0)
    plan.checkout_url = data.get("checkout_url")
    plan.manage_billing_url = data.get("manage_billing_url")
    plan.benefits = data.get("benefits", [])
    plan.seo = data.get("seo")


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
api.add_resource(CircleMeResource, "/me")
api.add_resource(CircleSubscriptionListResource, "/subscriptions")
api.add_resource(CircleSubscriptionDetailResource, "/subscriptions/<int:subscription_id>")
