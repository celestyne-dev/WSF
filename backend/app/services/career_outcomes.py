"""WSF Career Outcomes, built on Story Submissions (no separate intake).

A submitter may add one controlled career outcome to her story, with
explicit publish consent and a chosen attribution. Editors review it and
write the one-line public summary. An outcome is public only when
outcome_status == "approved" AND the submitter consented. The public
payload never carries email, surname, employer, location or any id, and
its copy never claims WSF caused the outcome.
"""
from datetime import datetime, timezone

from app.models.submissions import CAREER_OUTCOME_TYPES, StorySubmission
from app.utils.responses import ApiError

OUTCOME_LABELS = {
    "new_job": "Landed a new job",
    "promotion": "Got promoted",
    "pay_increase": "Negotiated a pay increase",
    "career_change": "Changed careers",
    "returned_to_work": "Returned to work",
    "started_business": "Started a business",
    "leadership_role": "Stepped into leadership",
    "new_qualification": "Earned a new qualification",
}
assert set(OUTCOME_LABELS) == set(CAREER_OUTCOME_TYPES)

PUBLIC_OUTCOME_LIMIT = 12


def apply_outcome_review(submission, data):
    """Validate staff outcome edits in `data` (a SubmissionUpdateSchema
    load) before they are applied. Attribution can only be made more
    private; approval requires consent, a type and a summary."""
    attribution = data.get("outcome_attribution")
    if attribution == "first_name" and submission.outcome_attribution != "first_name":
        raise ApiError("Only the submitter can choose to be named.", 422, code="validation_error")
    status = data.get("outcome_status")
    if status == "approved":
        outcome_type = data.get("outcome_type", submission.outcome_type)
        summary = (data.get("outcome_summary", submission.outcome_summary) or "").strip()
        if not submission.outcome_publish_consent:
            raise ApiError("This outcome can't be published: the submitter didn't give permission.", 422, code="validation_error")
        if not outcome_type or not summary:
            raise ApiError("Add an outcome type and a public summary before approving.", 422, code="validation_error")
        submission.outcome_approved_at = datetime.now(timezone.utc)
    elif status is not None:
        submission.outcome_approved_at = None
    if "outcome_summary" in data:
        data["outcome_summary"] = (data["outcome_summary"] or "").strip() or None


def _attribution(submission):
    if submission.outcome_attribution == "first_name":
        first = (submission.first_name or "").strip()
        initial = (submission.last_name or "").strip()[:1]
        if first:
            return f"{first} {initial}." if initial else first
    return "A WSF community member"


def public_outcomes(limit=PUBLIC_OUTCOME_LIMIT):
    rows = (
        StorySubmission.query.filter(
            StorySubmission.outcome_status == "approved",
            StorySubmission.outcome_publish_consent.is_(True),
            StorySubmission.outcome_type.isnot(None),
            StorySubmission.outcome_summary.isnot(None),
        )
        .order_by(StorySubmission.outcome_approved_at.desc(), StorySubmission.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {"type": r.outcome_type, "label": OUTCOME_LABELS[r.outcome_type], "summary": r.outcome_summary,
         "attribution": _attribution(r)}
        for r in rows
    ]
