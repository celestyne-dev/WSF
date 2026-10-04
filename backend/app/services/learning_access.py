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
from app.services.circle import has_circle_access

CURRICULUM_ACCESS_REASONS = ("circle_required", "program_unavailable", "enrollment_withdrawn", "access_denied")


def can_access_program_content(program, user):
    """True iff `user` (may be None) is currently eligible for this
    program's protected curriculum/progress. The single rule reused by
    every call site listed in the module docstring.
    """
    if program.access_type == "free":
        return True
    if program.access_type == "circle_only":
        return bool(user) and has_circle_access(user)
    # external/product: never internally accessible — no first-party
    # protected content exists for either, and Circle never unlocks a
    # product program (spec section N: "Circle must NOT unlock product
    # access").
    return False


def curriculum_access_state(enrollment, user):
    """Combines enrollment lifecycle + program availability + program-
    content eligibility into the one learner-facing state (spec section
    J/H) — returns (can_access_curriculum: bool, access_reason: str|None).
    Used by the owner enrollment payload and the protected curriculum/
    progress endpoints alike, so "why can't I see this" is always
    computed the same way.
    """
    program = enrollment.learning_program
    if enrollment.status != "active":
        return False, "enrollment_withdrawn"
    if program.status != "published":
        return False, "program_unavailable"
    if program.access_type == "free":
        return True, None
    if program.access_type == "circle_only":
        if has_circle_access(user):
            return True, None
        return False, "circle_required"
    # external/product: a stray/historical enrollment row (should
    # normally never exist — see enroll()'s own rejection of both) must
    # never grant protected content.
    return False, "access_denied"
