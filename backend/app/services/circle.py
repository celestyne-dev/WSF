"""The ONE authoritative WSF Circle premium-entitlement service. Every
place that needs to know "does this User have active Circle access right
now" — the owner API, the account pages, and any future gated
Resources/Learning/Events module — must call has_circle_access()/
get_circle_entitlement() here rather than re-deriving the rule locally
(see app/models/circle.py's module docstring for the full architecture
this sits on top of).

No payment gateway exists yet (see app/models/commerce.py's Order for
the same stance) — there is no background scheduler either (deliberately
out of scope for this phase), so has_circle_access() must correctly deny
access the instant current_period_end has passed even if a status row
still reads "active" because nothing has batch-updated it yet.
"""
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.circle import (
    CIRCLE_SUBSCRIPTION_CURRENT_STATUSES,
    CircleSubscription,
)
from app.utils.responses import ApiError

# Explicit allowed transitions (spec section M). A status not listed as a
# key here (every terminal status: cancelled/expired/revoked) allows NO
# outgoing transition — a terminal subscription never casually returns to
# active; a new membership cycle is always a brand-new CircleSubscription
# row, never a resurrected one.
_ALLOWED_TRANSITIONS = {
    "pending": {"active", "cancelled", "revoked"},
    "active": {"past_due", "cancelled", "expired", "revoked"},
    "past_due": {"active", "cancelled", "expired", "revoked"},
}


def validate_subscription_status_transition(old_status, new_status):
    if old_status == new_status:
        return
    allowed = _ALLOWED_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        raise ApiError(
            f'This subscription cannot move from "{old_status}" to "{new_status}".',
            422,
            code="invalid_status_transition",
        )


def get_current_subscription(user):
    """The at-most-one nonterminal (pending/active/past_due) row for this
    user — the same set the database's partial unique index enforces (see
    app/models/circle.py's uq_circle_subscriptions_one_current_per_user).
    """
    return CircleSubscription.query.filter(
        CircleSubscription.user_id == user.id,
        CircleSubscription.status.in_(CIRCLE_SUBSCRIPTION_CURRENT_STATUSES),
    ).first()


def get_latest_subscription_for_user(user):
    """The single most relevant subscription to show this user: her
    current one if she has one, otherwise her most recent historical
    (terminal) one — so /account/membership can explain "you were a
    member, here's what happened" rather than treating every non-current
    state identically to "never subscribed". Returns None only if she has
    never had a subscription at all.
    """
    current = get_current_subscription(user)
    if current is not None:
        return current
    return (
        CircleSubscription.query.filter_by(user_id=user.id)
        .order_by(CircleSubscription.created_at.desc())
        .first()
    )


def has_circle_access(user):
    """The single rule (spec section D): TRUE only when status == active,
    starts_at (if set) has arrived, current_period_end (if set) hasn't
    passed, and the account itself is active. pending/past_due/cancelled/
    expired/revoked never grant access — cancel_at_period_end never
    changes this calculation on its own; an active subscription with
    cancel_at_period_end=true keeps access until current_period_end.
    """
    if not user or not user.is_active:
        return False
    subscription = get_current_subscription(user)
    if subscription is None or subscription.status != "active":
        return False

    now = datetime.now(timezone.utc)
    if subscription.starts_at and subscription.starts_at > now:
        return False
    if subscription.current_period_end and subscription.current_period_end <= now:
        return False
    return True


def get_circle_entitlement(user):
    """Returns {"has_access": bool, "subscription": CircleSubscription|None}
    — the one shape both the owner API and account pages build their
    response from.
    """
    return {
        "has_access": has_circle_access(user),
        "subscription": get_latest_subscription_for_user(user),
    }


def create_subscription_for_user(user, plan, status, source, **fields):
    """Staff-only (enforced by the caller — see api/v1/circle.py's admin
    resources). Never creates a User, never creates/touches a Community
    Member, never creates an Order, never alters User.role. The database's
    partial unique index is the final authority on "one current
    subscription per user"; a race that slips past any earlier check still
    gets turned into a clean 409 here rather than a raw 500.
    """
    subscription = CircleSubscription(
        user_id=user.id,
        plan_id=plan.id,
        status=status,
        source=source,
        **fields,
    )
    db.session.add(subscription)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "This account already has a current WSF Circle subscription. "
            "Resolve or cancel it before recording a new one.",
            409,
            code="current_subscription_exists",
        )
    return subscription
