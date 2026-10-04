"""Self-service Learning enrollment and lesson-progress tracking for any
active authenticated WSF account — free published LearningPrograms only
(see app/services/learning_enrollments.py for the eligibility rules and
why external/product programs are rejected here rather than silently
ignored). No Community-membership requirement, no new CMS permission.
"""
from flask import Blueprint, current_app, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required
from app.extensions import db
from app.models.learning import LearningLesson
from app.models.learning_enrollment import LearningEnrollment
from app.schemas.learning import LearningModuleSchema, learning_program_summary_schema
from app.services.email import send_email
from app.services.learning_enrollments import (
    enroll,
    fetch_program_or_404,
    fetch_protected_curriculum,
    mark_lesson_complete,
    mark_lesson_incomplete,
    serialize_enrollment_for_owner,
    withdraw,
)
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

learning_enrollments_bp = Blueprint("learning_enrollments", __name__)
api = Api(learning_enrollments_bp)

_program_summary_schema = learning_program_summary_schema()


def _dump_enrollment(enrollment):
    return serialize_enrollment_for_owner(enrollment, _program_summary_schema)


def _fetch_owned_enrollment_or_404(enrollment_id, user):
    enrollment = db.session.get(LearningEnrollment, enrollment_id)
    if enrollment is None or enrollment.user_id != user.id:
        raise ApiError("Enrollment not found.", 404, code="not_found")
    return enrollment


def _fetch_lesson_or_404(lesson_id):
    lesson = db.session.get(LearningLesson, lesson_id)
    if lesson is None:
        raise ApiError("Lesson not found.", 404, code="not_found")
    return lesson


def _send_enrollment_confirmation_email(user, program):
    frontend_url = current_app.config["FRONTEND_URL"].rstrip("/")
    my_learning_url = f"{frontend_url}/account/learning"
    text_body = (
        f"You're enrolled in {program.title} with Women Shaping Futures.\n\n"
        f"Track your progress and pick up where you left off any time:\n{my_learning_url}\n"
    )
    html_body = (
        f"<p>You're enrolled in <strong>{program.title}</strong> with Women Shaping Futures.</p>"
        f'<p><a href="{my_learning_url}">View it in My Learning</a></p>'
    )
    if not send_email(to=user.email, subject=f"You're enrolled: {program.title}", text_body=text_body, html_body=html_body):
        current_app.logger.error(
            "Learning enrollment confirmation email delivery failed for user_id=%s program_id=%s.",
            user.id,
            program.id,
        )


class LearningEnrollmentListResource(Resource):
    @active_user_required
    def post(self):
        data = request.get_json(silent=True) or {}
        program_id = data.get("program_id")
        if not isinstance(program_id, int) or isinstance(program_id, bool) or program_id <= 0:
            raise ApiError("program_id must be a positive integer.", 422, code="validation_error")

        program = fetch_program_or_404(program_id)
        enrollment, created = enroll(program, current_user)
        if created:
            _send_enrollment_confirmation_email(current_user, program)
        return success_response({"enrollment": _dump_enrollment(enrollment), "enrolled": True})


class LearningEnrollmentCheckResource(Resource):
    @active_user_required
    def get(self):
        program_id = request.args.get("program_id", type=int)
        if not program_id or program_id <= 0:
            return success_response({"enrolled": False, "enrollment": None})
        enrollment = LearningEnrollment.query.filter_by(
            learning_program_id=program_id, user_id=current_user.id
        ).first()
        if enrollment is None:
            return success_response({"enrolled": False, "enrollment": None})
        return success_response({"enrolled": enrollment.status == "active", "enrollment": _dump_enrollment(enrollment)})


class LearningEnrollmentMeResource(Resource):
    @active_user_required
    def get(self):
        query = LearningEnrollment.query.filter_by(user_id=current_user.id)

        state = request.args.get("state")
        if state == "current":
            query = query.filter(LearningEnrollment.status == "active", LearningEnrollment.completed_at.is_(None))
        elif state == "completed":
            query = query.filter(LearningEnrollment.status == "active", LearningEnrollment.completed_at.isnot(None))
        elif state == "withdrawn":
            query = query.filter(LearningEnrollment.status == "withdrawn")

        query = query.order_by(LearningEnrollment.enrolled_at.desc())
        result = paginate(query, schema=None)
        items = [_dump_enrollment(e) for e in result["items"]]
        return success_response(items, meta=result["meta"])


class LearningEnrollmentWithdrawResource(Resource):
    @active_user_required
    def post(self, enrollment_id):
        enrollment = _fetch_owned_enrollment_or_404(enrollment_id, current_user)
        enrollment = withdraw(enrollment, current_user)
        return success_response({"enrollment": _dump_enrollment(enrollment)})


class LearningEnrollmentCurriculumResource(Resource):
    """The protected curriculum endpoint (spec section H) — the ONE place
    an enrolled learner's full curriculum (lesson content, external
    URLs, safe Article/Resource refs) is ever returned, and only after
    app/services/learning_enrollments.py's fetch_protected_curriculum
    confirms ownership + enrollment/program availability + program-
    content eligibility (free, or circle_only with current Circle
    access) via the one central app/services/learning_access.py rule.
    """

    @active_user_required
    def get(self, enrollment_id):
        enrollment = _fetch_owned_enrollment_or_404(enrollment_id, current_user)
        program = fetch_protected_curriculum(enrollment)
        return success_response(LearningModuleSchema(many=True).dump(program.modules))


class LearningLessonCompletionResource(Resource):
    @active_user_required
    def post(self, enrollment_id, lesson_id):
        enrollment = _fetch_owned_enrollment_or_404(enrollment_id, current_user)
        lesson = _fetch_lesson_or_404(lesson_id)
        mark_lesson_complete(enrollment, lesson)
        return success_response({"enrollment": _dump_enrollment(enrollment)})

    @active_user_required
    def delete(self, enrollment_id, lesson_id):
        enrollment = _fetch_owned_enrollment_or_404(enrollment_id, current_user)
        lesson = _fetch_lesson_or_404(lesson_id)
        mark_lesson_incomplete(enrollment, lesson)
        return success_response({"enrollment": _dump_enrollment(enrollment)})


api.add_resource(LearningEnrollmentListResource, "")
api.add_resource(LearningEnrollmentCheckResource, "/check")
api.add_resource(LearningEnrollmentMeResource, "/me")
api.add_resource(LearningEnrollmentWithdrawResource, "/<int:enrollment_id>/withdraw")
api.add_resource(LearningEnrollmentCurriculumResource, "/<int:enrollment_id>/curriculum")
api.add_resource(LearningLessonCompletionResource, "/<int:enrollment_id>/lessons/<int:lesson_id>/complete")
