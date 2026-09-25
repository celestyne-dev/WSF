from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.audit import AuditLog
from app.models.mentorship import (
    MATCH_ACTIVE_STATUSES,
    MentorshipApplication,
    MentorshipApplicationNote,
    MentorshipMatch,
    MentorshipMatchNote,
    MentorshipProgram,
    MentorshipSession,
)
from app.models.taxonomy import Topic
from app.schemas.mentorship import (
    MentorshipApplicationAdminUpdateSchema,
    MentorshipApplicationNoteInputSchema,
    MentorshipApplicationSchema,
    MentorshipApplicationStatusInputSchema,
    MentorshipApplicationSubmitInputSchema,
    MentorshipMatchCreateInputSchema,
    MentorshipMatchNoteInputSchema,
    MentorshipMatchSchema,
    MentorshipMatchStatusInputSchema,
    MentorshipMatchUpdateSchema,
    MentorshipProgramInputSchema,
    MentorshipProgramSchema,
    MentorshipProgramStatusInputSchema,
    MentorshipProgramUpdateSchema,
    MentorshipSessionInputSchema,
    MentorshipSessionUpdateSchema,
)
from app.schemas.media import MediaSchema
from app.services.audit import log_action
from app.services.content_blocks import sanitize_content_blocks
from app.services.newsletter import upsert_subscriber
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

mentorship_bp = Blueprint("mentorship", __name__)
api = Api(mentorship_bp)

program_schema = MentorshipProgramSchema()
application_schema = MentorshipApplicationSchema()
match_schema = MentorshipMatchSchema()

# Application statuses that already represent "a request is on file" for
# this program+role — a repeat public submission is acknowledged, never
# duplicated. declined/withdrawn/archived are closed-out states, so a
# fresh submission there is allowed (a new historical application row),
# per the "don't block someone from applying again forever" rule.
_APPLICATION_ALREADY_PRESENT = ("submitted", "reviewing", "shortlisted", "approved", "waitlisted")

_SUBMIT_WRITABLE_FIELDS = (
    "first_name", "last_name", "professional_title", "organization_name", "industry", "years_experience",
    "linkedin_url", "website_url", "background_text", "goals_text", "support_offered_text", "career_stage",
    "career_stages_supported", "country_code", "timezone", "meeting_frequency", "mentorship_format",
    "availability_note", "acquisition",
)
_ADMIN_APPLICATION_WRITABLE_FIELDS = (
    "first_name", "last_name", "email", "professional_title", "organization_name", "industry", "years_experience",
    "linkedin_url", "website_url", "background_text", "goals_text", "support_offered_text", "career_stage",
    "career_stages_supported", "country_code", "timezone", "meeting_frequency", "mentorship_format",
    "availability_note", "mentor_capacity", "mentor_active", "member_id", "person_id",
)


def _resolve_topics(slugs):
    if not slugs:
        return []
    return Topic.query.filter(Topic.slug.in_(slugs)).all()


def _get_program_or_404(program_id):
    program = db.session.get(MentorshipProgram, program_id)
    if program is None:
        raise ApiError("Program not found.", 404, code="not_found")
    return program


def _get_application_or_404(application_id):
    application = db.session.get(MentorshipApplication, application_id)
    if application is None:
        raise ApiError("Application not found.", 404, code="not_found")
    return application


def _get_match_or_404(match_id):
    match = db.session.get(MentorshipMatch, match_id)
    if match is None:
        raise ApiError("Match not found.", 404, code="not_found")
    return match


def _capacity_warning(mentor_application):
    if mentor_application.is_at_capacity():
        return (
            f"This mentor is now at or over their stated capacity "
            f"({mentor_application.active_mentee_count()}/{mentor_application.mentor_capacity})."
        )
    return None


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


def build_public_program_payload(program):
    return {
        "id": program.id,
        "slug": program.slug,
        "name": program.name,
        "shortDescription": program.short_description,
        "fullDescription": program.full_description or [],
        "status": program.status,
        "applicationOpenNow": program.applications_open_now(),
        "applicationOpensAt": program.application_opens_at.isoformat() if program.application_opens_at else None,
        "applicationClosesAt": program.application_closes_at.isoformat() if program.application_closes_at else None,
        "programStartsAt": program.program_starts_at.isoformat() if program.program_starts_at else None,
        "programEndsAt": program.program_ends_at.isoformat() if program.program_ends_at else None,
        "country": {"code": program.country.code, "name": program.country.name} if program.country else None,
        "eligibilitySummary": program.eligibility_summary,
        "topics": [t.name for t in program.topics],
        "heroMedia": MediaSchema().dump(program.hero_media) if program.hero_media else None,
        "seo": program.seo or {},
    }


class PublicProgramListResource(Resource):
    def get(self):
        programs = (
            MentorshipProgram.query.filter_by(public_visible=True)
            .filter(MentorshipProgram.status.notin_(("draft", "archived")))
            .order_by(MentorshipProgram.application_opens_at.desc().nullslast(), MentorshipProgram.created_at.desc())
            .all()
        )
        return success_response([build_public_program_payload(p) for p in programs])


class ProgramListResource(Resource):
    @permission_required("mentorship.manage")
    def get(self):
        query = MentorshipProgram.query.order_by(MentorshipProgram.created_at.desc())
        query = apply_equality_filters(query, MentorshipProgram, request.args, ["status"])
        result = paginate(query, program_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("mentorship.manage")
    def post(self):
        data = MentorshipProgramInputSchema().load(request.get_json(silent=True) or {})
        if MentorshipProgram.query.filter_by(slug=data["slug"]).first():
            raise ApiError("A program with this slug already exists.", 409, code="conflict")
        topic_slugs = data.pop("topic_slugs", [])
        data["full_description"] = sanitize_content_blocks(data.get("full_description", []))
        program = MentorshipProgram(**data)
        program.topics = _resolve_topics(topic_slugs)
        db.session.add(program)
        db.session.commit()
        log_action(current_user, "mentorship.program_create", "MentorshipProgram", program.id)
        return success_response(program_schema.dump(program), status=201)


class ProgramDetailResource(Resource):
    @permission_required("mentorship.manage")
    def get(self, program_id):
        return success_response(program_schema.dump(_get_program_or_404(program_id)))

    @permission_required("mentorship.manage")
    def patch(self, program_id):
        program = _get_program_or_404(program_id)
        data = MentorshipProgramUpdateSchema().load(request.get_json(silent=True) or {})
        if "full_description" in data:
            data["full_description"] = sanitize_content_blocks(data["full_description"])
        topic_slugs = data.pop("topic_slugs", None)
        for field, value in data.items():
            setattr(program, field, value)
        if topic_slugs is not None:
            program.topics = _resolve_topics(topic_slugs)
        db.session.commit()
        log_action(current_user, "mentorship.program_update", "MentorshipProgram", program.id)
        return success_response(program_schema.dump(program))

    @permission_required("mentorship.manage")
    def delete(self, program_id):
        program = _get_program_or_404(program_id)
        if program.status != "draft":
            raise ApiError("Only Draft programs can be deleted. Archive established programs instead.", 409, code="delete_restricted")
        if MentorshipApplication.query.filter_by(program_id=program.id).count():
            raise ApiError("This program has applications and can't be deleted. Archive it instead.", 409, code="delete_restricted")
        db.session.delete(program)
        db.session.commit()
        log_action(current_user, "mentorship.program_delete", "MentorshipProgram", program_id)
        return success_response(None, status=204)


class ProgramStatusResource(Resource):
    @permission_required("mentorship.manage")
    def patch(self, program_id):
        program = _get_program_or_404(program_id)
        data = MentorshipProgramStatusInputSchema().load(request.get_json(silent=True) or {})
        previous_status = program.status
        program.status = data["status"]
        db.session.commit()
        log_action(
            current_user, "mentorship.program_status_change", "MentorshipProgram", program.id,
            changes={"from": previous_status, "to": program.status},
        )
        return success_response(program_schema.dump(program))


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


def _apply_submitted_fields(application, data):
    for field in _SUBMIT_WRITABLE_FIELDS:
        if field in data:
            setattr(application, field, data[field])
    application.consent_given = True
    application.consent_at = db.func.now()
    application.newsletter_opt_in = bool(data.get("subscribe_newsletter"))
    application.source = "Mentorship page"


def _subscribe_to_newsletter(application, data):
    upsert_subscriber(
        email=application.email,
        first_name=application.first_name,
        last_name=application.last_name,
        country_code=application.country_code,
        placement="mentorship-application",
        acquisition=data.get("acquisition"),
    )
    db.session.commit()


def _build_application_query():
    query = MentorshipApplication.query.order_by(MentorshipApplication.submitted_at.desc())
    query = apply_equality_filters(query, MentorshipApplication, request.args, ["role", "program_id", "status", "industry", "career_stage"])
    query = apply_search(query, MentorshipApplication, request.args, ["first_name", "last_name", "email", "organization_name"])
    query = apply_country_or_region_filter(query, MentorshipApplication, request.args)

    topic = request.args.get("topic")
    if topic:
        query = query.join(MentorshipApplication.topics).filter(Topic.slug == topic)

    if request.args.get("unmatched") == "true":
        matched_ids = db.session.query(MentorshipMatch.mentee_application_id).filter(
            MentorshipMatch.status.in_(MATCH_ACTIVE_STATUSES)
        )
        query = query.filter(~MentorshipApplication.id.in_(matched_ids))

    return query


class ApplicationListResource(Resource):
    @permission_required("mentorship.manage")
    def get(self):
        result = paginate(_build_application_query(), application_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        data = MentorshipApplicationSubmitInputSchema().load(request.get_json(silent=True) or {})
        program = _get_program_or_404(data["program_id"])
        if not program.applications_open_now():
            raise ApiError("Applications for this program are not currently open.", 422, code="applications_closed")

        email = data["email"].strip().lower()
        role = data["role"]
        topic_slugs = data.pop("topic_slugs", [])

        existing = (
            MentorshipApplication.query.filter_by(program_id=program.id, role=role, email=email)
            .order_by(MentorshipApplication.submitted_at.desc())
            .first()
        )
        if existing is not None and existing.status in _APPLICATION_ALREADY_PRESENT:
            return success_response(
                {"message": f"You already have a {role} application on file for this program — our team will follow up."}
            )

        application = MentorshipApplication(program=program, role=role, email=email)
        _apply_submitted_fields(application, data)
        application.topics = _resolve_topics(topic_slugs)
        db.session.add(application)
        db.session.commit()
        if application.newsletter_opt_in:
            _subscribe_to_newsletter(application, data)
        return success_response(
            {"message": f"Thank you — your {role} application to {program.name} has been received."}, status=201
        )


class ApplicationDetailResource(Resource):
    @permission_required("mentorship.manage")
    def get(self, application_id):
        return success_response(application_schema.dump(_get_application_or_404(application_id)))

    @permission_required("mentorship.manage")
    def patch(self, application_id):
        application = _get_application_or_404(application_id)
        data = MentorshipApplicationAdminUpdateSchema().load(request.get_json(silent=True) or {})

        if "email" in data:
            data["email"] = data["email"].strip().lower()

        topic_slugs = data.pop("topic_slugs", None)
        for field in _ADMIN_APPLICATION_WRITABLE_FIELDS:
            if field in data:
                setattr(application, field, data[field])
        if topic_slugs is not None:
            application.topics = _resolve_topics(topic_slugs)

        db.session.commit()
        log_action(current_user, "mentorship.application_update", "MentorshipApplication", application.id)
        return success_response(application_schema.dump(application))

    @permission_required("mentorship.manage")
    def delete(self, application_id):
        application = _get_application_or_404(application_id)
        if application.status not in ("submitted", "reviewing", "declined", "withdrawn"):
            raise ApiError(
                "Only Submitted, Reviewing, Declined, or Withdrawn applications can be deleted. Archive established records instead.",
                409, code="delete_restricted",
            )
        if application.notes:
            raise ApiError("This application has internal notes and can't be deleted. Archive it instead.", 409, code="delete_restricted")
        referenced = MentorshipMatch.query.filter(
            db.or_(MentorshipMatch.mentor_application_id == application.id, MentorshipMatch.mentee_application_id == application.id)
        ).count()
        if referenced:
            raise ApiError("This application is referenced by a match and can't be deleted. Archive it instead.", 409, code="delete_restricted")
        db.session.delete(application)
        db.session.commit()
        log_action(current_user, "mentorship.application_delete", "MentorshipApplication", application_id)
        return success_response(None, status=204)


class ApplicationStatusResource(Resource):
    @permission_required("mentorship.manage")
    def patch(self, application_id):
        application = _get_application_or_404(application_id)
        data = MentorshipApplicationStatusInputSchema().load(request.get_json(silent=True) or {})
        previous_status = application.status
        application.status = data["status"]
        application.reviewed_by = current_user
        db.session.commit()
        log_action(
            current_user, "mentorship.application_status_change", "MentorshipApplication", application.id,
            changes={"from": previous_status, "to": application.status},
        )
        return success_response(application_schema.dump(application))


class ApplicationNoteListResource(Resource):
    @permission_required("mentorship.manage")
    def post(self, application_id):
        application = _get_application_or_404(application_id)
        data = MentorshipApplicationNoteInputSchema().load(request.get_json(silent=True) or {})
        note = MentorshipApplicationNote(application=application, user=current_user, body=data["body"])
        db.session.add(note)
        db.session.commit()
        log_action(current_user, "mentorship.application_note_add", "MentorshipApplication", application.id)
        return success_response(application_schema.dump(application), status=201)


class ApplicationHistoryResource(Resource):
    @permission_required("mentorship.manage")
    def get(self, application_id):
        _get_application_or_404(application_id)
        entries = (
            AuditLog.query.filter_by(entity_type="MentorshipApplication", entity_id=str(application_id))
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        return success_response(
            [
                {
                    "id": e.id, "action": e.action, "changes": e.changes,
                    "user": e.user.full_name if e.user else None,
                    "createdAt": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ]
        )


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------


def _build_match_query():
    query = MentorshipMatch.query.order_by(MentorshipMatch.matched_at.desc())
    query = apply_equality_filters(query, MentorshipMatch, request.args, ["program_id", "status", "mentor_application_id", "mentee_application_id"])
    return query


class MatchListResource(Resource):
    @permission_required("mentorship.manage")
    def get(self):
        result = paginate(_build_match_query(), match_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("mentorship.manage")
    def post(self):
        data = MentorshipMatchCreateInputSchema().load(request.get_json(silent=True) or {})
        mentor_application = _get_application_or_404(data["mentor_application_id"])
        mentee_application = _get_application_or_404(data["mentee_application_id"])

        if mentor_application.role != "mentor":
            raise ApiError("The selected mentor application must have role Mentor.", 422, code="validation_error")
        if mentee_application.role != "mentee":
            raise ApiError("The selected mentee application must have role Mentee.", 422, code="validation_error")
        if mentor_application.status != "approved" or mentee_application.status != "approved":
            raise ApiError("Both the mentor and mentee must be Approved before matching.", 422, code="validation_error")
        if mentor_application.program_id != mentee_application.program_id:
            raise ApiError("The mentor and mentee must belong to the same program.", 422, code="validation_error")

        match = MentorshipMatch(
            program_id=mentor_application.program_id,
            mentor_application=mentor_application,
            mentee_application=mentee_application,
            planned_start_date=data.get("planned_start_date"),
            planned_end_date=data.get("planned_end_date"),
            matching_notes=data.get("matching_notes"),
        )
        db.session.add(match)
        db.session.commit()
        log_action(
            current_user, "mentorship.match_created", "MentorshipMatch", match.id,
            changes={"mentorApplicationId": mentor_application.id, "menteeApplicationId": mentee_application.id},
        )

        payload = match_schema.dump(match)
        warning = _capacity_warning(mentor_application)
        if warning:
            payload["capacityWarning"] = warning
        return success_response(payload, status=201)


class MatchDetailResource(Resource):
    @permission_required("mentorship.manage")
    def get(self, match_id):
        return success_response(match_schema.dump(_get_match_or_404(match_id)))

    @permission_required("mentorship.manage")
    def patch(self, match_id):
        match = _get_match_or_404(match_id)
        data = MentorshipMatchUpdateSchema().load(request.get_json(silent=True) or {})
        for field, value in data.items():
            setattr(match, field, value)
        db.session.commit()
        log_action(current_user, "mentorship.match_update", "MentorshipMatch", match.id)
        return success_response(match_schema.dump(match))


class MatchStatusResource(Resource):
    @permission_required("mentorship.manage")
    def patch(self, match_id):
        match = _get_match_or_404(match_id)
        data = MentorshipMatchStatusInputSchema().load(request.get_json(silent=True) or {})
        previous_status = match.status
        match.status = data["status"]
        if "closure_reason" in data:
            match.closure_reason = data["closure_reason"]
        if match.status == "completed" and not match.actual_completion_date:
            match.actual_completion_date = date.today()
        db.session.commit()
        log_action(
            current_user, "mentorship.match_status_change", "MentorshipMatch", match.id,
            changes={"from": previous_status, "to": match.status},
        )
        payload = match_schema.dump(match)
        warning = _capacity_warning(match.mentor_application)
        if warning and match.status in MATCH_ACTIVE_STATUSES:
            payload["capacityWarning"] = warning
        return success_response(payload)


class MatchNoteListResource(Resource):
    @permission_required("mentorship.manage")
    def post(self, match_id):
        match = _get_match_or_404(match_id)
        data = MentorshipMatchNoteInputSchema().load(request.get_json(silent=True) or {})
        note = MentorshipMatchNote(match=match, user=current_user, body=data["body"])
        db.session.add(note)
        db.session.commit()
        log_action(current_user, "mentorship.match_note_add", "MentorshipMatch", match.id)
        return success_response(match_schema.dump(match), status=201)


class MatchHistoryResource(Resource):
    @permission_required("mentorship.manage")
    def get(self, match_id):
        _get_match_or_404(match_id)
        entries = (
            AuditLog.query.filter_by(entity_type="MentorshipMatch", entity_id=str(match_id))
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        return success_response(
            [
                {
                    "id": e.id, "action": e.action, "changes": e.changes,
                    "user": e.user.full_name if e.user else None,
                    "createdAt": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ]
        )


class MatchSessionListResource(Resource):
    @permission_required("mentorship.manage")
    def post(self, match_id):
        match = _get_match_or_404(match_id)
        data = MentorshipSessionInputSchema().load(request.get_json(silent=True) or {})
        session = MentorshipSession(match=match, **data)
        db.session.add(session)
        db.session.commit()
        log_action(current_user, "mentorship.session_add", "MentorshipMatch", match.id)
        return success_response(match_schema.dump(match), status=201)


class MatchSessionDetailResource(Resource):
    @permission_required("mentorship.manage")
    def patch(self, match_id, session_id):
        match = _get_match_or_404(match_id)
        session = MentorshipSession.query.filter_by(id=session_id, match_id=match.id).first()
        if session is None:
            raise ApiError("Session not found.", 404, code="not_found")
        data = MentorshipSessionUpdateSchema().load(request.get_json(silent=True) or {})
        for field, value in data.items():
            setattr(session, field, value)
        db.session.commit()
        log_action(current_user, "mentorship.session_update", "MentorshipMatch", match.id)
        return success_response(match_schema.dump(match))


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class MentorshipOverviewResource(Resource):
    @permission_required("mentorship.manage")
    def get(self):
        matched_mentee_ids = db.session.query(MentorshipMatch.mentee_application_id).filter(
            MentorshipMatch.status.in_(MATCH_ACTIVE_STATUSES)
        )
        return success_response(
            {
                "openPrograms": MentorshipProgram.query.filter_by(status="applications_open").count(),
                "mentorApplications": MentorshipApplication.query.filter_by(role="mentor").count(),
                "menteeApplications": MentorshipApplication.query.filter_by(role="mentee").count(),
                "approvedMentors": MentorshipApplication.query.filter_by(role="mentor", status="approved").count(),
                "unmatchedMentees": MentorshipApplication.query.filter(
                    MentorshipApplication.role == "mentee",
                    MentorshipApplication.status == "approved",
                    ~MentorshipApplication.id.in_(matched_mentee_ids),
                ).count(),
                "activeMatches": MentorshipMatch.query.filter(MentorshipMatch.status.in_(MATCH_ACTIVE_STATUSES)).count(),
                "completedMatches": MentorshipMatch.query.filter_by(status="completed").count(),
            }
        )


api.add_resource(PublicProgramListResource, "/programs/public")
api.add_resource(ProgramListResource, "/programs")
api.add_resource(ProgramDetailResource, "/programs/<int:program_id>")
api.add_resource(ProgramStatusResource, "/programs/<int:program_id>/status")
api.add_resource(ApplicationListResource, "/applications")
api.add_resource(ApplicationDetailResource, "/applications/<int:application_id>")
api.add_resource(ApplicationStatusResource, "/applications/<int:application_id>/status")
api.add_resource(ApplicationNoteListResource, "/applications/<int:application_id>/notes")
api.add_resource(ApplicationHistoryResource, "/applications/<int:application_id>/history")
api.add_resource(MatchListResource, "/matches")
api.add_resource(MatchDetailResource, "/matches/<int:match_id>")
api.add_resource(MatchStatusResource, "/matches/<int:match_id>/status")
api.add_resource(MatchNoteListResource, "/matches/<int:match_id>/notes")
api.add_resource(MatchHistoryResource, "/matches/<int:match_id>/history")
api.add_resource(MatchSessionListResource, "/matches/<int:match_id>/sessions")
api.add_resource(MatchSessionDetailResource, "/matches/<int:match_id>/sessions/<int:session_id>")
api.add_resource(MentorshipOverviewResource, "/overview")
