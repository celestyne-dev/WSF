"""The ONE place Opportunity access-tier entitlement and application-open
state are decided — mirrors app/services/event_access.py and
app/services/resource_access.py exactly. WSF Circle entitlement is NEVER
re-derived here; every check traces back to app/services/circle.py's
has_circle_access(). Status/date "is this still accepting applications"
logic lives here too (spec section E) so the schema's is_closed flag and
the access endpoint can never drift apart.

Opportunity.access_type is orthogonal to the application mechanism
itself — applying always happens on the provider's own external site;
WSF never runs an application workflow, with or without Circle.
"""
from datetime import date

from app.services.circle import has_circle_access
from app.utils.responses import ApiError
from app.utils.urls import is_safe_http_url

OPPORTUNITY_ACCESS_REASONS = ("circle_required",)


def is_application_open(opportunity):
    """True only for a published Opportunity whose deadline/expiry have
    not passed. draft/closed/archived are never open — a draft is never
    even publicly visible, and closed/archived are explicit end states.
    """
    if opportunity.status != "published":
        return False
    today = date.today()
    if opportunity.expiry_date and opportunity.expiry_date < today:
        return False
    if opportunity.deadline and opportunity.deadline < today:
        return False
    return True


def has_safe_application_target(opportunity):
    """Revalidated at read/access time, never trusted from storage alone
    — a legacy/manually-edited row with an unsafe scheme must never be
    handed back to a visitor (spec section F), even though publish-time
    validation already rejects an unsafe URL on ordinary API writes.
    """
    return is_safe_http_url(opportunity.application_url)


def can_access_opportunity_application(opportunity, user):
    """True when `user` (None for anonymous) may receive this
    Opportunity's application destination/instructions right now.
    Application-open/URL-safety are NOT checked here — those are
    orthogonal preconditions the caller (the /access endpoint,
    viewer_can_access below) checks on its own, so this function answers
    only "is the Circle-gate satisfied", exactly like
    app/services/event_access.py's can_access_event().
    """
    if opportunity.access_type != "circle_only":
        return True
    if user is None or not user.is_active or user.must_change_password:
        return False
    return has_circle_access(user)


def opportunity_access_state(opportunity, user):
    """Richer (bool, reason) form for API payloads that need to explain
    *why* access is denied. reason is None when access is granted, or
    the one stable code "circle_required" otherwise.
    """
    if can_access_opportunity_application(opportunity, user):
        return True, None
    return False, "circle_required"


def viewer_can_access(opportunity, user):
    """The safe `viewerCanAccess` serialization hint (spec section H) —
    UI guidance only. POST /opportunities/{slug}/access remains the one
    authoritative grant and re-checks everything (entitlement,
    application-open state, URL safety) itself.
    """
    return can_access_opportunity_application(opportunity, user)


def _require_entitled_account(user):
    """Account-standing checks shared by the access endpoint, raising
    this endpoint's own stable codes rather than a generic 401/403 (spec
    section G, steps 5-8).
    """
    if user is None:
        raise ApiError("An account is required to access this application.", 401, code="account_required")
    if not user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    if user.must_change_password:
        raise ApiError(
            "You must change your password before continuing.", 403, code="password_change_required"
        )


def check_opportunity_application_access(opportunity, user):
    """Raises ApiError if `user` may not receive the application target
    right now; returns None (silently) when access is granted. Never
    resolves or returns the target itself — the /access endpoint does
    that only after this check passes (spec section G).
    """
    if not is_application_open(opportunity):
        raise ApiError(
            "This opportunity is no longer accepting applications.", 409, code="application_closed"
        )
    if not has_safe_application_target(opportunity):
        raise ApiError(
            "No application destination is configured for this opportunity.", 422, code="application_unavailable"
        )
    if opportunity.access_type == "circle_only":
        _require_entitled_account(user)
        if not has_circle_access(user):
            raise ApiError(
                "This opportunity's application details are included with WSF Circle membership.",
                403,
                code="circle_required",
            )
