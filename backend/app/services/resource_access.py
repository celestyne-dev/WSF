"""The ONE place Resource access-type rules are evaluated — both for the
real grant (POST /resources/{slug}/access) and for the public payload's
safe `viewerCanAccess` hint (see app/schemas/resource.py). WSF Circle
entitlement is NEVER re-derived here — see app/services/circle.py's
has_circle_access(), the one authoritative check for that.

member_only means any valid authenticated WSF User account — never a
Community Member record, never WSF Circle, never Member.membership_type
(see app/models/community.py's own docstring for why those stay separate
concepts). circle_only means exactly has_circle_access(user); nothing
about Community membership feeds into it either way.
"""
from app.services.circle import has_circle_access
from app.utils.responses import ApiError


def _require_account(user):
    """Same checks app/auth/decorators.py's _require_active_user applies
    (active account, no forced password change) but raising THIS
    endpoint's own account_required code for the anonymous case, per
    spec, rather than flask-jwt-extended's generic 401
    authorization_required a bare verify_jwt_in_request() would produce.
    """
    if user is None:
        raise ApiError("An account is required to access this resource.", 401, code="account_required")
    if not user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    if user.must_change_password:
        raise ApiError(
            "You must change your password before continuing.", 403, code="password_change_required"
        )


def check_resource_access(resource, user):
    """Raises ApiError if `user` (None for an anonymous visitor) may not
    access `resource` right now. Returns None (silently) when access is
    granted. Never resolves or returns the target URL itself — that
    stays the access endpoint's own job, only after this check passes.
    """
    access_type = resource.access_type

    if access_type == "premium":
        # Unconditional — a WSF Circle membership never unlocks a
        # premium one-off resource; Circle and Resource purchase are
        # deliberately separate commercial concepts (spec section E/R).
        raise ApiError(
            "This is a premium resource. Purchasing isn't available yet.", 403, code="premium_unavailable"
        )

    if access_type == "member_only":
        _require_account(user)
        return

    if access_type == "circle_only":
        _require_account(user)
        if not has_circle_access(user):
            raise ApiError(
                "This resource is included with WSF Circle membership.", 403, code="circle_required"
            )
        return

    # direct_download / email_gate / external_link: open to any visitor.
    # email_gate's own lead-capture requirement is enforced by the caller
    # (POST /access) directly — it is a data requirement, not an
    # entitlement check, so it doesn't belong in this function.
    return


def viewer_can_access(resource, user):
    """A safe, side-effect-free hint for serialization only (spec
    section C's `viewerCanAccess`) — never itself a grant of access;
    POST /access remains the one authoritative place that actually
    grants it. email_gate is always False here, regardless of `user`,
    since access only becomes true once the gate is actually submitted.
    """
    if resource.access_type == "email_gate":
        return False
    try:
        check_resource_access(resource, user)
        return True
    except ApiError:
        return False
