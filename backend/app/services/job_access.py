"""The ONE place Job access-tier entitlement and application-open state
are decided — mirrors app/services/opportunity_access.py exactly, with
one addition: a Job's application channel is two independent fields
(application_url, application_email), each revalidated at read/access
time rather than trusted from storage, with the other surviving alone
if just one of them turns out unsafe/invalid. WSF Circle entitlement is
NEVER re-derived here; every check traces back to app/services/circle.py's
has_circle_access().

Job.access_type is orthogonal to the application mechanism itself —
applying always happens via the employer's own URL/email/instructions,
with or without Circle.
"""
from datetime import date

from marshmallow import validate as ma_validate

from app.services.circle import has_circle_access
from app.utils.responses import ApiError
from app.utils.urls import is_safe_http_url

JOB_ACCESS_REASONS = ("circle_required",)

_email_validator = ma_validate.Email()


def is_job_publicly_visible(job):
    """True only for a job a non-privileged viewer may see at all.
    draft/review/future-scheduled/expired/archived are never visible —
    expired/archived are explicit end states kept only for record, distinct
    from "published but past its deadline" (still visible, just closed to
    new applications — see is_job_application_open below).
    """
    if job.status == "published":
        return True
    if job.status == "scheduled" and job.published_date and job.published_date <= date.today():
        return True
    return False


def is_job_application_open(job):
    """True only for a publicly visible Job whose deadline/expiry have not
    passed. Not publicly visible => never open either.
    """
    if not is_job_publicly_visible(job):
        return False
    today = date.today()
    if job.deadline and job.deadline < today:
        return False
    if job.expiry_date and job.expiry_date < today:
        return False
    return True


def is_safe_application_email(email):
    """Revalidated at read/access time, never trusted from storage alone
    — reuses marshmallow's own trusted Email validator (the same
    mechanism JobInputSchema's application_email field already enforces
    on write), never a permissive hand-rolled regex.
    """
    if not email:
        return False
    try:
        _email_validator(email)
        return True
    except Exception:
        return False


def safe_application_channel(job):
    """Each destination is checked independently so one unsafe/invalid
    field never hides the other — a job with a bad URL but a valid email
    still returns the email, and vice versa.
    """
    url = job.application_url if is_safe_http_url(job.application_url) else None
    email = job.application_email if is_safe_application_email(job.application_email) else None
    return {"url": url, "email": email}


def has_valid_application_channel(job):
    channel = safe_application_channel(job)
    return bool(channel["url"] or channel["email"])


def can_access_job_application(job, user):
    """True when `user` (None for anonymous) may receive this Job's
    application channel/instructions right now. Application-open/channel
    safety are NOT checked here — those are orthogonal preconditions the
    caller (the /access endpoint, viewer_can_access below) checks on its
    own, so this function answers only "is the Circle-gate satisfied".
    """
    if job.access_type != "circle_only":
        return True
    if user is None or not user.is_active or user.must_change_password:
        return False
    return has_circle_access(user)


def job_access_state(job, user):
    """Richer (bool, reason) form for API payloads that need to explain
    *why* access is denied. reason is None when access is granted, or
    the one stable code "circle_required" otherwise.
    """
    if can_access_job_application(job, user):
        return True, None
    return False, "circle_required"


def viewer_can_access(job, user):
    """The safe `viewerCanAccess` serialization hint — UI guidance only.
    POST /jobs/{slug}/access remains the one authoritative grant and
    re-checks everything (entitlement, application-open state, channel
    safety) itself.
    """
    return can_access_job_application(job, user)


def _require_entitled_account(user):
    """Account-standing checks shared by the access endpoint, raising
    this endpoint's own stable codes rather than a generic 401/403.
    """
    if user is None:
        raise ApiError("An account is required to access this application.", 401, code="account_required")
    if not user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    if user.must_change_password:
        raise ApiError(
            "You must change your password before continuing.", 403, code="password_change_required"
        )


def check_job_application_access(job, user):
    """Raises ApiError if `user` may not receive the application channel
    right now; returns None (silently) when access is granted. Never
    resolves or returns the channel itself — the /access endpoint does
    that only after this check passes.
    """
    if not is_job_application_open(job):
        raise ApiError("This job is no longer accepting applications.", 409, code="application_closed")
    if not has_valid_application_channel(job):
        raise ApiError(
            "No application destination is configured for this job.", 422, code="application_unavailable"
        )
    if job.access_type == "circle_only":
        _require_entitled_account(user)
        if not has_circle_access(user):
            raise ApiError(
                "This job's application details are included with WSF Circle membership.",
                403,
                code="circle_required",
            )
