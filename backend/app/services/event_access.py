"""The ONE place WSF Event access-TIER entitlement is decided — reused by
circle_only registration (app/services/event_registrations.py),
the private virtual-link authorization, and the public viewerCanAccess
hint, so Circle logic is never scattered across routes. WSF Circle
entitlement itself always comes from app/services/circle.py's
has_circle_access() — never re-derived here, and nothing here ever reads
Member/Member.membership_type, Community status, User role, Product, or
Order.

Access tier is orthogonal to registration_mode (HOW registration is
collected: external/wsf) and to ticket_price (event PRICING) — see
app/models/opportunity.py's EVENT_ACCESS_TYPES docstring. Registration-
window/capacity/status logic stays in event_registrations.py; this
module decides entitlement ONLY.

public: content is open to everyone. circle_only: requires an active,
non-forced-password-change user with has_circle_access(user) == True.
"""
from app.services.circle import has_circle_access

EVENT_ACCESS_REASONS = ("circle_required",)


def can_access_event(event, user):
    """True iff `user` (may be None) is currently eligible for this
    event's circle_only registration/private virtual link. The single
    rule reused by every call site listed in the module docstring.
    """
    if event.access_type != "circle_only":
        return True
    return bool(user) and user.is_active and not user.must_change_password and has_circle_access(user)


def event_access_state(event, user):
    """(can_access: bool, reason: str|None) — the owner-facing "why can't
    I access this" state (spec section M), always derived from
    can_access_event() so the two can never disagree. The only stable
    reason is "circle_required" (public events never fail this check).
    """
    if can_access_event(event, user):
        return True, None
    return False, "circle_required"
