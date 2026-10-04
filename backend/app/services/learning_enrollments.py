"""First-party WSF learner enrollment & lesson-progress tracking — the
actual eligibility/completion logic behind
app/api/v1/learning_enrollments.py (self-service) and the read-only
enrollment-listing endpoint added to app/api/v1/learning.py (staff).

Only ever relevant for a LearningProgram whose access_type == "free": an
"external" or "product" program is never internally enrollable — see
enroll()'s explicit rejection of those two access types (spec: never
infer entitlement from a Product relationship, never create an
enrollment merely because someone clicked an external link).

Completion is derived from the program's CURRENT lesson set and is never
persisted as a percentage — only `completed_at` is a stored fact, and it
is only ever set/cleared as the direct result of the LEARNER's own
mark-complete/mark-incomplete action (see mark_lesson_complete/
mark_lesson_incomplete below) — never as a side effect of an editor's
curriculum update (app/api/v1/learning.py's AdminLearningCurriculumResource
never calls into this module at all), so a learner who already earned
completion keeps it even after new lessons are added later.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models.learning import LearningProgram
from app.models.learning_enrollment import LearningEnrollment, LearningLessonProgress
from app.utils.responses import ApiError


def fetch_program_or_404(program_id):
    program = db.session.get(LearningProgram, program_id)
    if program is None:
        raise ApiError("Learning program not found.", 404, code="not_found")
    return program


def _current_lesson_ids(program):
    return [lesson.id for module in program.modules for lesson in module.lessons]


def progress_summary(enrollment, program=None):
    program = program or enrollment.learning_program
    lesson_ids = set(_current_lesson_ids(program))
    total = len(lesson_ids)
    completed = sum(1 for p in enrollment.lesson_progress if p.lesson_id in lesson_ids)
    percent = round((completed / total) * 100) if total else 0
    return {"completed_lessons": completed, "total_lessons": total, "progress_percent": percent}


def enroll(program, user):
    """Never silently enrolls an external/product program — each gets its
    own distinct, clearly-coded rejection so the caller can show the
    right message rather than a generic failure.
    """
    if program.status != "published":
        raise ApiError("Learning program not found.", 404, code="not_found")
    if program.access_type == "external":
        raise ApiError(
            "This program uses external enrollment — WSF does not manage enrollment for it here.",
            422,
            code="external_enrollment",
        )
    if program.access_type == "product":
        raise ApiError(
            "This program's access is handled through the Shop — purchase or access is managed separately.",
            422,
            code="product_enrollment",
        )

    existing = LearningEnrollment.query.filter_by(learning_program_id=program.id, user_id=user.id).first()
    if existing and existing.status == "active":
        return existing, False

    if existing:
        existing.status = "active"
        existing.withdrawn_at = None
        enrollment = existing
    else:
        enrollment = LearningEnrollment(
            learning_program_id=program.id, user_id=user.id, status="active", enrolled_at=datetime.now(timezone.utc)
        )
        db.session.add(enrollment)

    db.session.commit()
    return enrollment, True


def withdraw(enrollment, user):
    if enrollment.user_id != user.id:
        raise ApiError("You do not have permission to withdraw this enrollment.", 403, code="forbidden")
    if enrollment.status == "withdrawn":
        return enrollment

    enrollment.status = "withdrawn"
    enrollment.withdrawn_at = datetime.now(timezone.utc)
    db.session.commit()
    return enrollment


def _check_progress_allowed(enrollment, lesson):
    program = enrollment.learning_program
    if enrollment.status != "active":
        raise ApiError(
            "This enrollment has been withdrawn — reactivate it to update lesson progress.",
            409,
            code="enrollment_withdrawn",
        )
    if program.status != "published":
        raise ApiError("This learning program is no longer available.", 409, code="program_unavailable")
    # The critical cross-program guard (spec: "a learner must never mark a
    # lesson complete through an enrollment belonging to another program").
    if lesson.module is None or lesson.module.learning_program_id != enrollment.learning_program_id:
        raise ApiError("This lesson does not belong to this enrollment's program.", 403, code="forbidden")


def mark_lesson_complete(enrollment, lesson):
    _check_progress_allowed(enrollment, lesson)
    program = enrollment.learning_program

    if not any(p.lesson_id == lesson.id for p in enrollment.lesson_progress):
        enrollment.lesson_progress.append(LearningLessonProgress(lesson_id=lesson.id))

    summary = progress_summary(enrollment, program)
    if summary["total_lessons"] > 0 and summary["completed_lessons"] >= summary["total_lessons"]:
        if enrollment.completed_at is None:
            enrollment.completed_at = datetime.now(timezone.utc)

    db.session.commit()
    return summary


def mark_lesson_incomplete(enrollment, lesson):
    _check_progress_allowed(enrollment, lesson)
    program = enrollment.learning_program

    existing = next((p for p in enrollment.lesson_progress if p.lesson_id == lesson.id), None)
    if existing is not None:
        enrollment.lesson_progress.remove(existing)

    summary = progress_summary(enrollment, program)
    still_complete = summary["total_lessons"] > 0 and summary["completed_lessons"] >= summary["total_lessons"]
    if not still_complete and enrollment.completed_at is not None:
        enrollment.completed_at = None

    db.session.commit()
    return summary


def serialize_enrollment_for_owner(enrollment, program_summary_schema):
    """Dump shared by /check, /me, and the enroll/withdraw/progress
    responses — always the learner's own data, and the linked Program is
    dumped with the PUBLIC SUMMARY shape (no modules/curriculum) so an
    archived program's hidden curriculum is never leaked through this
    endpoint regardless of its current status (spec: "the enrollment
    should not leak hidden curriculum" through the account endpoint).
    """
    program = enrollment.learning_program
    summary = progress_summary(enrollment, program)
    current_lesson_ids = set(_current_lesson_ids(program))
    return {
        "id": enrollment.id,
        "status": enrollment.status,
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        "withdrawn_at": enrollment.withdrawn_at.isoformat() if enrollment.withdrawn_at else None,
        "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
        "completed_lessons": summary["completed_lessons"],
        "total_lessons": summary["total_lessons"],
        "progress_percent": summary["progress_percent"],
        # Which of the program's CURRENT lessons this learner has marked
        # complete — small and the learner's own data, so safe to include
        # unconditionally; the curriculum UI needs this to render each
        # lesson's own Mark complete/Completed toggle correctly (the
        # aggregate count/percent above isn't enough for that).
        "completed_lesson_ids": sorted(p.lesson_id for p in enrollment.lesson_progress if p.lesson_id in current_lesson_ids),
        "program_available": program.status == "published",
        "program": program_summary_schema.dump(program),
    }
