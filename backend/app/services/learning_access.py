"""The ONE place WSF Learning program-CONTENT eligibility is decided —
reused by circle_only enrollment creation, the protected curriculum
endpoint, and lesson-progress mutation, so Circle logic is never
scattered across routes. WSF Circle entitlement itself always comes
from app/services/circle.py's has_circle_access() — never re-derived
here, and nothing here ever reads Member/Member.membership_type,
Community status, User role, Product, or Order.

free: content is open to everyone (no login needed to read it — the
public detail endpoint doesn't even call this for a free program).
circle_only: content requires has_circle_access(user). external/product:
no first-party protected content ever exists — always False, even if a
historical/stray enrollment row somehow exists.
"""
from app.services.circle import has_circle_access, has_lifetime_circle_access

CURRICULUM_ACCESS_REASONS = ("circle_required", "program_unavailable", "enrollment_withdrawn", "access_denied")


# Product types that are a pure digital wrapper for selling a WSF Learning
# program. "service"/"physical"/"other" (coaching, cohorts with delivery
# costs, merchandise, anything unclear) are never Lifetime-included.
LIFETIME_DIGITAL_PRODUCT_TYPES = ("digital", "downloadable")


def is_lifetime_eligible_program(program):
    """Whether a Learning program is WSF-owned digital Learning that WSF
    Circle Lifetime includes — decided from the program's own fields and
    its linked Product, never from Product titles or a blanket Product
    rule:
      * WSF-owned: no partner provider Organization (WSF-as-provider is
        represented by leaving provider_organization_id empty);
      * free / circle_only: included;
      * product: included only when the program has a linked Product AND
        that Product is a digital/downloadable wrapper for it;
      * external: never (third-party/external enrollment).
    Evaluated live on every request, so future eligible programs are
    included automatically with no per-member rows."""
    if program.provider_organization_id is not None:
        return False
    if program.access_type in ("free", "circle_only"):
        return True
    if program.access_type == "product":
        product = program.product
        return product is not None and product.type in LIFETIME_DIGITAL_PRODUCT_TYPES
    return False


def lifetime_unlocks_program(program, user):
    """True when an active Lifetime member may access this program's
    content without a purchase. Grants Learning access only — it never
    creates an Order or implies ownership of the linked Product."""
    return is_lifetime_eligible_program(program) and has_lifetime_circle_access(user)


def can_access_program_content(program, user):
    """True iff `user` (may be None) is currently eligible for this
    program's protected curriculum/progress. The single rule reused by
    every call site listed in the module docstring.

    circle_only additionally requires the user to be active and NOT in a
    forced-password-change state — a temporary/reset-password account
    must never be reported (even as the public viewerCanAccess hint) as
    currently able to access Circle Learning content, matching the same
    guard app/auth/decorators.py's active_user_required enforces for the
    protected endpoints themselves.
    """
    if program.access_type == "free":
        return True
    if program.access_type == "circle_only":
        return (
            bool(user)
            and user.is_active
            and not user.must_change_password
            and has_circle_access(user)
        )
    if program.access_type == "product":
        # Monthly/Yearly Circle never unlocks a product program; an active
        # Lifetime member does, for an eligible WSF-owned digital program
        # (see is_lifetime_eligible_program) — same account guards as
        # circle_only above.
        return (
            bool(user)
            and user.is_active
            and not user.must_change_password
            and lifetime_unlocks_program(program, user)
        )
    # external: never internally accessible — no first-party protected
    # content exists for it.
    return False


def curriculum_access_state(enrollment, user):
    """Combines enrollment lifecycle + program availability + program-
    content eligibility into the one learner-facing state (spec section
    J/H) — returns (can_access_curriculum: bool, access_reason: str|None).
    Used by the owner enrollment payload and the protected curriculum/
    progress endpoints alike, so "why can't I see this" is always
    computed the same way. Content eligibility itself is always delegated
    to can_access_program_content() — never independently re-derived here
    — so the two can never disagree.
    """
    program = enrollment.learning_program
    if enrollment.status != "active":
        return False, "enrollment_withdrawn"
    if program.status != "published":
        return False, "program_unavailable"
    if can_access_program_content(program, user):
        return True, None
    if program.access_type == "circle_only":
        return False, "circle_required"
    # free can never reach here (can_access_program_content is always
    # True for it); external/product — including a stray/historical
    # enrollment row, which should normally never exist (see enroll()'s
    # own rejection of both) — must never grant protected content.
    return False, "access_denied"


def program_circle_inclusion(program):
    """Display-only mirror of can_access_program_content(): circle_only
    content is granted by any active WSF Circle membership; an eligible
    product program by Lifetime only; free needs no membership; external
    is never unlocked by Circle.
    Returns {"included": bool, "scope": "all"|"lifetime"|None}."""
    if program.access_type == "circle_only":
        return {"included": True, "scope": "all"}
    if program.access_type == "product" and is_lifetime_eligible_program(program):
        return {"included": True, "scope": "lifetime"}
    return {"included": False, "scope": None}
