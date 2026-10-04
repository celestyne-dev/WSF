"""WSF Learning: structured educational offerings — see
app/models/learning.py's module docstring for the architecture decision
and what this deliberately does not own (pricing/scheduling/editorial
body/downloads, all left to Product/Event/Article/Resource).
"""
from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.commerce import Product
from app.models.learning import (
    ACCESS_TYPES,
    LearningLesson,
    LearningModule,
    LearningProgram,
    LearningProgramEvent,
    LearningProgramRelatedArticle,
)
from app.models.article import Article
from app.models.learning_enrollment import LearningEnrollment
from app.models.opportunity import Event
from app.models.people import Author, Organization
from app.models.resource import Resource as ResourceModel
from app.models.taxonomy import Topic
from app.models.user import User
from app.schemas.learning import (
    LearningCurriculumInputSchema,
    LearningProgramInputSchema,
    LearningProgramSchema,
    admin_learning_program_summary_schema,
    learning_program_summary_schema,
    public_learning_program_schema,
)
from app.services.content_blocks import sanitize_content_blocks
from app.services.homepage import validate_cta_url
from app.services.audit import log_action
from app.services.learning_access import can_access_program_content
from app.services.learning_enrollments import progress_summary
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

learning_bp = Blueprint("learning", __name__)
api = Api(learning_bp)

program_schema = LearningProgramSchema()


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _current_user_or_none():
    """Optional-auth viewer resolution for the public endpoints below —
    anonymous access is always preserved (a missing/invalid token never
    raises); only used to compute the safe `viewerCanAccess` hint, never
    as authorization itself (see app/services/learning_access.py).
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    return current_user


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("learning.manage"):
        raise ApiError("You do not have permission to manage Learning programs.", 403, code="forbidden")
    return user


def _lookup_all(model, slugs, label):
    if not slugs:
        return []
    found = model.query.filter(model.slug.in_(slugs)).all()
    found_slugs = {item.slug for item in found}
    missing = [s for s in slugs if s not in found_slugs]
    if missing:
        raise ApiError(f'{label.capitalize()} "{missing[0]}" not found.', 404, code="not_found")
    return found


def _resolve_program_relations(data):
    resolved = {}

    resolved["primary_instructor"] = None
    if data.get("primary_instructor_slug"):
        author = Author.query.filter_by(slug=data["primary_instructor_slug"]).first()
        if author is None:
            raise ApiError(f'Instructor "{data["primary_instructor_slug"]}" not found.', 404, code="not_found")
        resolved["primary_instructor"] = author

    resolved["co_instructors"] = _lookup_all(Author, data.get("co_instructor_slugs", []), "instructor")

    resolved["provider_organization"] = None
    if data.get("provider_organization_slug"):
        org = Organization.query.filter_by(slug=data["provider_organization_slug"]).first()
        if org is None:
            raise ApiError(f'Organization "{data["provider_organization_slug"]}" not found.', 404, code="not_found")
        resolved["provider_organization"] = org

    resolved["product"] = None
    if data.get("product_slug"):
        product = Product.query.filter_by(slug=data["product_slug"]).first()
        if product is None:
            raise ApiError(f'Product "{data["product_slug"]}" not found.', 404, code="not_found")
        resolved["product"] = product

    resolved["events"] = _lookup_all(Event, data.get("event_slugs", []), "event")
    resolved["topics"] = _lookup_all(Topic, data.get("topic_slugs", []), "topic")
    resolved["related_articles"] = _lookup_all(Article, data.get("related_article_slugs", []), "article")
    resolved["related_resources"] = _lookup_all(ResourceModel, data.get("related_resource_slugs", []), "resource")

    return resolved


def _apply_program_fields(program, data, relations):
    program.title = data["title"]
    program.subtitle = data.get("subtitle")
    program.short_description = data.get("short_description")
    program.program_type = data.get("program_type", "course")
    program.difficulty_level = data.get("difficulty_level")
    program.audience = data.get("audience", [])
    program.overview = sanitize_content_blocks(data.get("overview", []))
    program.learning_outcomes = data.get("learning_outcomes", [])
    program.prerequisites = data.get("prerequisites", [])
    program.duration_value = data.get("duration_value")
    program.duration_unit = data.get("duration_unit")
    program.hero_media_id = data.get("hero_media_id")
    program.primary_instructor = relations["primary_instructor"]
    program.co_instructors = relations["co_instructors"]
    program.provider_organization = relations["provider_organization"]
    program.delivery_mode = data.get("delivery_mode", "self_paced")
    program.access_type = data.get("access_type", "free")
    program.product = relations["product"]
    program.external_url = data.get("external_url")
    program.topics = relations["topics"]
    program.related_resources = relations["related_resources"]
    program.featured = data.get("featured", False)
    program.seo = data.get("seo")

    program.related_article_links = [
        LearningProgramRelatedArticle(article_id=article.id, position=i)
        for i, article in enumerate(relations["related_articles"])
    ]
    program.event_links = [
        LearningProgramEvent(event_id=event.id, position=i) for i, event in enumerate(relations["events"])
    ]


def _validate_for_publish(program):
    """Enforced only when a program's effective status is "published" — a
    draft may stay incomplete indefinitely, but the public CTA a published
    program promises must actually work (spec: "no fake course gating",
    "public CTA uses Product relationship").
    """
    errors = []
    if program.access_type == "product" and program.product_id is None:
        errors.append('A "product" access program must be linked to a Product before publishing.')
    if program.access_type == "external":
        if not program.external_url:
            errors.append('An "external" access program needs an external URL before publishing.')
        else:
            try:
                validate_cta_url(program.external_url, field_name="external_url")
            except Exception:
                errors.append("The external URL is not a safe http(s) link.")
    if program.primary_instructor_id is None:
        errors.append("An instructor is required before publishing.")
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


def _dump_from_id(program_id, schema):
    program = LearningProgram.query.get(program_id)
    return schema.dump(program)


class LearningProgramPublicListResource(Resource):
    def get(self):
        query = LearningProgram.query.filter_by(status="published")

        if request.args.get("program_type"):
            query = query.filter(LearningProgram.program_type == request.args["program_type"])
        if request.args.get("difficulty_level"):
            query = query.filter(LearningProgram.difficulty_level == request.args["difficulty_level"])
        if request.args.get("delivery_mode"):
            query = query.filter(LearningProgram.delivery_mode == request.args["delivery_mode"])
        if request.args.get("access_type"):
            query = query.filter(LearningProgram.access_type == request.args["access_type"])
        if request.args.get("topic"):
            query = query.filter(LearningProgram.topics.any(slug=request.args["topic"]))
        if request.args.get("audience"):
            # audience is a small JSON list column (a handful of controlled
            # values from AUDIENCE_TYPES, never large or user-authored) —
            # a plain text-cast ILIKE on the serialized JSON is simplest and
            # correct here (a real `@>` containment operator needs a JSONB
            # column, which nothing else in this app uses either).
            query = query.filter(db.cast(LearningProgram.audience, db.Text).ilike(f'%"{request.args["audience"]}"%'))
        if request.args.get("featured") == "true":
            query = query.filter(LearningProgram.featured.is_(True))
        if request.args.get("q"):
            like = f"%{request.args['q']}%"
            from sqlalchemy import or_

            query = query.filter(
                or_(
                    LearningProgram.title.ilike(like),
                    LearningProgram.subtitle.ilike(like),
                    LearningProgram.short_description.ilike(like),
                )
            )

        query = query.order_by(LearningProgram.featured.desc(), LearningProgram.created_at.desc())
        result = paginate(query, learning_program_summary_schema())
        return success_response(result["items"], meta=result["meta"])


def build_public_program_payload(program, viewer):
    """The public detail payload — full curriculum for `free`, a SAFE
    OUTLINE for circle_only/external/product (see
    public_learning_program_schema). `requiresCircle`/`viewerCanAccess`
    are UI guidance only (spec section K) — the real rule is
    app/services/learning_access.py's can_access_program_content, never
    re-derived here; backend endpoints remain the actual authority.
    """
    payload = public_learning_program_schema(program).dump(program)
    payload["requiresCircle"] = program.access_type == "circle_only"
    payload["viewerCanAccess"] = can_access_program_content(program, viewer)
    return payload


class LearningProgramPublicDetailResource(Resource):
    def get(self, slug):
        program = LearningProgram.query.filter_by(slug=slug, status="published").first()
        if program is None:
            raise ApiError("Learning program not found.", 404, code="not_found")
        return success_response(build_public_program_payload(program, _current_user_or_none()))


class AdminLearningProgramListResource(Resource):
    def get(self):
        _require_manage()
        query = LearningProgram.query

        if request.args.get("status"):
            query = query.filter(LearningProgram.status == request.args["status"])
        if request.args.get("program_type"):
            query = query.filter(LearningProgram.program_type == request.args["program_type"])
        if request.args.get("delivery_mode"):
            query = query.filter(LearningProgram.delivery_mode == request.args["delivery_mode"])
        if request.args.get("access_type"):
            query = query.filter(LearningProgram.access_type == request.args["access_type"])
        if request.args.get("instructor"):
            query = query.join(Author, LearningProgram.primary_instructor_id == Author.id).filter(
                Author.slug == request.args["instructor"]
            )
        if request.args.get("featured") == "true":
            query = query.filter(LearningProgram.featured.is_(True))
        if request.args.get("q"):
            like = f"%{request.args['q']}%"
            from sqlalchemy import or_

            query = query.filter(or_(LearningProgram.title.ilike(like), LearningProgram.subtitle.ilike(like)))

        query = query.order_by(LearningProgram.updated_at.desc())
        result = paginate(query, admin_learning_program_summary_schema())
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        user = _require_manage()
        data = LearningProgramInputSchema().load(request.get_json(silent=True) or {})
        relations = _resolve_program_relations(data)

        program = LearningProgram()
        if data.get("slug"):
            program.slug = validate_explicit_slug(LearningProgram, data["slug"])
        else:
            program.slug = generate_unique_slug(LearningProgram, data["title"])

        _apply_program_fields(program, data, relations)
        program.status = data.get("status", "draft")
        db.session.add(program)
        if program.status == "published":
            program.published_at = db.func.now()
            # Flush so the primary_instructor relationship assigned above is
            # synchronized to primary_instructor_id before validation reads
            # it — on a brand-new object nothing has flushed yet, so the FK
            # column would otherwise still read None even with a valid
            # instructor attached.
            db.session.flush()
            _validate_for_publish(program)
        db.session.commit()

        log_action(user, "learning.create", "LearningProgram", program.id, {"status": program.status})
        return success_response(program_schema.dump(program), status=201)


class AdminLearningProgramDetailResource(Resource):
    def get(self, program_id):
        _require_manage()
        program = LearningProgram.query.get(program_id)
        if program is None:
            raise ApiError("Learning program not found.", 404, code="not_found")
        return success_response(program_schema.dump(program))

    def patch(self, program_id):
        user = _require_manage()
        program = LearningProgram.query.get(program_id)
        if program is None:
            raise ApiError("Learning program not found.", 404, code="not_found")

        data = LearningProgramInputSchema().load(request.get_json(silent=True) or {})
        relations = _resolve_program_relations(data)

        old_slug = program.slug
        if data.get("slug") and data["slug"] != old_slug:
            program.slug = validate_explicit_slug(LearningProgram, data["slug"], current_id=program.id)

        old_status = program.status
        old_access_type = program.access_type
        _apply_program_fields(program, data, relations)
        new_status = data.get("status", old_status)

        if new_status == "published" and old_status != "published":
            program.published_at = db.func.now()
        if new_status == "archived" and old_status != "archived":
            program.archived_at = db.func.now()
        program.status = new_status
        if program.status == "published":
            _validate_for_publish(program)

        db.session.commit()

        changes = {}
        if old_status != new_status:
            changes["from_status"] = old_status
            changes["to_status"] = new_status
        if old_access_type != program.access_type:
            changes["access_type_changed"] = {"from": old_access_type, "to": program.access_type}
        log_action(user, "learning.update", "LearningProgram", program.id, changes or None)

        return success_response(program_schema.dump(program))


class AdminLearningCurriculumResource(Resource):
    """Replaces a program's modules+lessons tree IN PLACE rather than
    discarding and recreating every row — an existing module/lesson `id`
    (which LearningModuleInputSchema/LearningLessonInputSchema already
    accept) is matched against this program's OWN current curriculum and
    updated on the SAME row, so its id survives a normal edit. This is
    load-bearing: app/services/learning_enrollments.py's
    LearningLessonProgress rows FK to learning_lessons.id, so an id that
    silently changed on every save would otherwise sever a learner's
    progress from lessons that, from an editor's point of view, never
    moved (see that module's own docstring for how a learner's earned
    completion is preserved across curriculum edits — it depends on this).

    Still transaction-safe: every referenced Article/Resource is
    resolved and every external_url/id validated BEFORE the tree is
    swapped, and nothing here ever touches the Article/Resource rows a
    lesson referenced, or the LearningEnrollment/progress rows
    themselves — this resource updates curriculum shape only.

    SECURITY: a submitted module/lesson id is only ever matched against
    THIS program's own current modules/lessons (never a global lookup),
    so an id belonging to a different LearningProgram — or a lesson id
    belonging to a different module within this SAME program — is
    rejected as not-found rather than silently reattached or edited
    cross-program/cross-module.
    """

    def put(self, program_id):
        user = _require_manage()
        program = LearningProgram.query.get(program_id)
        if program is None:
            raise ApiError("Learning program not found.", 404, code="not_found")

        data = LearningCurriculumInputSchema().load(request.get_json(silent=True) or {})

        existing_modules_by_id = {m.id: m for m in program.modules}

        new_modules = []
        seen_module_ids = set()
        for module_index, module_data in enumerate(data["modules"]):
            module_id = module_data.get("id")
            existing_lessons_by_id = {}
            if module_id is not None:
                module = existing_modules_by_id.get(module_id)
                if module is None:
                    raise ApiError(f"Module {module_id} not found in this program.", 404, code="not_found")
                if module_id in seen_module_ids:
                    raise ApiError(f"Module {module_id} was submitted more than once.", 422, code="validation_error")
                seen_module_ids.add(module_id)
                existing_lessons_by_id = {lesson.id: lesson for lesson in module.lessons}
            else:
                module = LearningModule()

            module.title = module_data["title"]
            module.description = module_data.get("description")
            module.sort_order = module_index

            lessons = []
            seen_lesson_ids = set()
            for lesson_index, lesson_data in enumerate(module_data.get("lessons", [])):
                lesson_type = lesson_data.get("lesson_type", "text")
                article = None
                if lesson_data.get("article_slug"):
                    article = Article.query.filter_by(slug=lesson_data["article_slug"]).first()
                    if article is None:
                        raise ApiError(f'Article "{lesson_data["article_slug"]}" not found.', 404, code="not_found")
                resource = None
                if lesson_data.get("resource_slug"):
                    resource = ResourceModel.query.filter_by(slug=lesson_data["resource_slug"]).first()
                    if resource is None:
                        raise ApiError(f'Resource "{lesson_data["resource_slug"]}" not found.', 404, code="not_found")
                external_url = lesson_data.get("external_url")
                if external_url:
                    try:
                        validate_cta_url(external_url, field_name="external_url")
                    except Exception:
                        raise ApiError(
                            f'Lesson "{lesson_data["title"]}" has an unsafe external URL.', 422, code="invalid_url"
                        )
                if lesson_type in ("video", "external_link") and not external_url:
                    raise ApiError(
                        f'Lesson "{lesson_data["title"]}" needs an external URL for lesson type "{lesson_type}".',
                        422,
                        code="validation_error",
                    )

                lesson_id = lesson_data.get("id")
                if lesson_id is not None:
                    lesson = existing_lessons_by_id.get(lesson_id)
                    if lesson is None:
                        raise ApiError(f"Lesson {lesson_id} not found in this module.", 404, code="not_found")
                    if lesson_id in seen_lesson_ids:
                        raise ApiError(f"Lesson {lesson_id} was submitted more than once.", 422, code="validation_error")
                    seen_lesson_ids.add(lesson_id)
                else:
                    lesson = LearningLesson()

                lesson.title = lesson_data["title"]
                lesson.lesson_type = lesson_type
                lesson.summary = lesson_data.get("summary")
                lesson.content = sanitize_content_blocks(lesson_data.get("content", []))
                lesson.article_id = article.id if article else None
                lesson.resource_id = resource.id if resource else None
                lesson.external_url = external_url
                lesson.duration_minutes = lesson_data.get("duration_minutes")
                lesson.sort_order = lesson_index
                lessons.append(lesson)

            module.lessons = lessons
            new_modules.append(module)

        # Everything above is resolved/validated against this program's
        # own existing rows only — now, with no further way to fail, the
        # tree is replaced: delete-orphan cascade removes any omitted
        # module/lesson (and, via LearningLesson's own cascade, that
        # lesson's LearningLessonProgress rows — spec: "removed lesson
        # progress is safely removed"), while every reused object above
        # keeps its existing id and is updated, not recreated.
        program.modules = new_modules
        db.session.commit()

        log_action(
            user,
            "learning.curriculum_update",
            "LearningProgram",
            program.id,
            {"module_count": len(new_modules), "lesson_count": sum(len(m.lessons) for m in new_modules)},
        )
        return success_response(program_schema.dump(program))


def _dump_admin_enrollment(enrollment):
    user = enrollment.user
    summary = progress_summary(enrollment, enrollment.learning_program)
    return {
        "id": enrollment.id,
        "status": enrollment.status,
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        "withdrawn_at": enrollment.withdrawn_at.isoformat() if enrollment.withdrawn_at else None,
        "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
        "completed_lessons": summary["completed_lessons"],
        "total_lessons": summary["total_lessons"],
        "progress_percent": summary["progress_percent"],
        "learner_name": user.full_name if user else None,
        "learner_email": user.email if user else None,
        "learner_country": user.country.name if user and user.country else None,
    }


class LearningEnrollmentAdminListResource(Resource):
    """Read-only operational view for learning.manage staff — spec:
    "primarily operational/read-only"; "do not let staff casually mark
    lessons complete" / "fabricate completion". No mutation endpoint is
    exposed here at all, so learner lifecycle/progress stays entirely
    self-service (the spec explicitly allows leaving it that way rather
    than adding a staff withdraw/reactivate action).
    """

    def get(self, program_id):
        _require_manage()
        program = LearningProgram.query.get(program_id)
        if program is None:
            raise ApiError("Learning program not found.", 404, code="not_found")

        query = LearningEnrollment.query.filter_by(learning_program_id=program.id).join(LearningEnrollment.user)

        state = request.args.get("state")
        if state == "current":
            query = query.filter(LearningEnrollment.status == "active", LearningEnrollment.completed_at.is_(None))
        elif state == "completed":
            query = query.filter(LearningEnrollment.status == "active", LearningEnrollment.completed_at.isnot(None))
        elif state == "withdrawn":
            query = query.filter(LearningEnrollment.status == "withdrawn")

        search_term = request.args.get("q")
        if search_term:
            like = f"%{search_term}%"
            query = query.filter(or_(User.first_name.ilike(like), User.last_name.ilike(like), User.email.ilike(like)))

        query = query.order_by(LearningEnrollment.enrolled_at.desc())
        result = paginate(query, schema=None)

        counts = {
            "current": LearningEnrollment.query.filter_by(
                learning_program_id=program.id, status="active"
            ).filter(LearningEnrollment.completed_at.is_(None)).count(),
            "completed": LearningEnrollment.query.filter_by(
                learning_program_id=program.id, status="active"
            ).filter(LearningEnrollment.completed_at.isnot(None)).count(),
            "withdrawn": LearningEnrollment.query.filter_by(learning_program_id=program.id, status="withdrawn").count(),
        }
        items = [_dump_admin_enrollment(e) for e in result["items"]]
        # Pagination nested inside `data` (not the `meta=` kwarg) so the
        # frontend apiClient's response interceptor — which only reshapes
        # a bare-array `data` into {items, pagination} — leaves `counts`
        # intact alongside `items` (same convention as the Event
        # Registration admin list; see frontend/src/api/client.js).
        return success_response({"items": items, "counts": counts, "pagination": result["meta"]})


api.add_resource(LearningProgramPublicListResource, "")
api.add_resource(LearningProgramPublicDetailResource, "/<string:slug>")
api.add_resource(AdminLearningProgramListResource, "/admin/programs")
api.add_resource(AdminLearningProgramDetailResource, "/admin/programs/<int:program_id>")
api.add_resource(AdminLearningCurriculumResource, "/admin/programs/<int:program_id>/curriculum")
api.add_resource(LearningEnrollmentAdminListResource, "/admin/programs/<int:program_id>/enrollments")
