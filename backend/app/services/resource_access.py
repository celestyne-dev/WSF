"""The ONE place Resource access-type rules are evaluated — both for the
real grant (POST /resources/{slug}/access) and for the public payload's
safe `viewerCanAccess` hint (see app/schemas/resource.py). WSF Circle
entitlement is NEVER re-derived here — see app/services/circle.py's
has_circle_access(), the one authoritative check for that. Premium
Resource purchase entitlement is likewise never re-derived here — see
app/models/resource.py's ResourcePurchase, the one authoritative record
for that.

member_only means any valid authenticated WSF User account — never a
Community Member record, never WSF Circle, never Member.membership_type
(see app/models/community.py's own docstring for why those stay separate
concepts). circle_only means has_circle_access(user) — further narrowed
to has_yearly_circle_access(user) when the Resource's own
circle_access_level == "yearly_members" (see app/models/resource.py's
CIRCLE_ACCESS_LEVELS; meaningless for every other access_type). Monthly
and yearly Circle members alike pass the ordinary circle_only gate — the
yearly-only narrowing is a strictly smaller, second tier reserved for
annual-member bonus content, never a replacement for the base rule.
Nothing about Community membership feeds into either tier. premium means
"this user holds a ResourcePurchase for this Resource, OR currently has
active WSF Circle entitlement via has_circle_access(user)" — the two are
deliberately separate paths to the SAME access, not merged concepts:
a ResourcePurchase is a durable, one-time entitlement that survives a
later Circle lapse; Circle access is temporary, membership-based, and
disappears the moment has_circle_access(user) stops being true, exactly
like circle_only's own gate. Circle access is never itself converted
into (or recorded as) a ResourcePurchase row — see
get_viewer_access_source below for how a caller tells the two apart for
display purposes. Buying a premium Resource still never grants Circle
either way (see ResourcePurchase's own docstring in
app/models/resource.py) — Community membership, Product/Order records,
and frontend flags are likewise never consulted for either path.
"""
from app.models.resource import ResourcePurchase
from app.services.circle import has_circle_access, has_yearly_circle_access
from app.utils.responses import ApiError


def has_resource_purchase(user, resource):
    """The one authoritative check for premium Resource entitlement —
    never re-derived from Circle, Community, Product/Order, or any
    frontend flag. False for an anonymous viewer (no account to hold a
    purchase at all).
    """
    if user is None:
        return False
    return (
        ResourcePurchase.query.filter_by(user_id=user.id, resource_id=resource.id, status="active").first()
        is not None
    )


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
        # Requires a real WSF account first (same account_required 401 as
        # member_only/circle_only) — ownership/entitlement must attach to
        # a known account, so an anonymous visitor can never hold/redeem
        # either path below. has_circle_access(user) is checked as a
        # second, independent path to the SAME access (see
        # get_viewer_access_source for the display precedence this gives
        # purchase over it) — never as a substitute that creates or
        # implies a ResourcePurchase.
        _require_account(user)
        if has_resource_purchase(user, resource) or has_circle_access(user):
            return
        raise ApiError(
            "This premium resource requires purchase.", 403, code="purchase_required"
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
        # A second, narrower tier reserved for annual-member bonus
        # content (see app/models/resource.py's CIRCLE_ACCESS_LEVELS) —
        # meaningless for the "all_members" default, which stops right
        # above at the ordinary Circle check every monthly or yearly
        # member already passes.
        if resource.circle_access_level == "yearly_members" and not has_yearly_circle_access(user):
            raise ApiError(
                "This resource is included with WSF Circle Yearly.", 403, code="yearly_circle_required"
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


def get_viewer_access_source(resource, user):
    """Which of the two independent premium-access paths `user` actually
    holds right now — serialization-only, same safety posture as
    viewer_can_access (never itself a grant; never consulted by POST
    /access, which re-derives everything from check_resource_access
    directly). Returns "purchase", "circle", or None; always None for
    any access_type other than premium, since those have no second path
    to distinguish. Purchase takes precedence when a viewer holds both —
    it's the durable entitlement, so it's the one worth surfacing to the
    UI even while Circle also happens to be active. Exposes only which
    PATH grants access, never any subscription id, plan id, payment id,
    date, or other membership/payment detail.
    """
    if resource.access_type != "premium":
        return None
    if has_resource_purchase(user, resource):
        return "purchase"
    if has_circle_access(user):
        return "circle"
    return None
