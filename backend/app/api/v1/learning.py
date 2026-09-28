"""WSF Learning: structured educational offerings — see
app/models/learning.py's module docstring for the architecture decision
and what this deliberately does not own (pricing/scheduling/editorial
body/downloads, all left to Product/Event/Article/Resource).
"""
from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

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
from app.models.opportunity import Event
from app.models.people import Author, Organization
from app.models.resource import Resource as ResourceModel
from app.models.taxonomy import Topic
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


class LearningProgramPublicDetailResource(Resource):
    def get(self, slug):
        program = LearningProgram.query.filter_by(slug=slug, status="published").first()
        if program is None:
            raise ApiError("Learning program not found.", 404, code="not_found")
        return success_response(public_learning_program_schema().dump(program))


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
    """Replaces a program's entire modules+lessons tree in one request —
    transaction-safe: every referenced Article/Resource is resolved and
    every external_url validated BEFORE any ORM object is created, so a
    validation failure never leaves half the curriculum saved (spec
    section 70). Unlinking never deletes the referenced Article/Resource
    itself (spec section 71) — only the LearningLesson row that pointed
    at it.
    """

    def put(self, program_id):
        user = _require_manage()
        program = LearningProgram.query.get(program_id)
        if program is None:
            raise ApiError("Learning program not found.", 404, code="not_found")

        data = LearningCurriculumInputSchema().load(request.get_json(silent=True) or {})

        new_modules = []
        for module_index, module_data in enumerate(data["modules"]):
            module = LearningModule(
                title=module_data["title"],
                description=module_data.get("description"),
                sort_order=module_index,
            )
            lessons = []
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

                lessons.append(
                    LearningLesson(
                        title=lesson_data["title"],
                        lesson_type=lesson_type,
                        summary=lesson_data.get("summary"),
                        content=sanitize_content_blocks(lesson_data.get("content", [])),
                        article_id=article.id if article else None,
                        resource_id=resource.id if resource else None,
                        external_url=external_url,
                        duration_minutes=lesson_data.get("duration_minutes"),
                        sort_order=lesson_index,
                    )
                )
            module.lessons = lessons
            new_modules.append(module)

        # Everything above is resolved/validated with nothing yet attached
        # to the session-tracked program — only now, with no further way to
        # fail, do we replace the tree (delete-orphan cascade removes the
        # old modules/lessons; nothing here ever touches the Article/
        # Resource rows those lessons referenced).
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


api.add_resource(LearningProgramPublicListResource, "")
api.add_resource(LearningProgramPublicDetailResource, "/<string:slug>")
api.add_resource(AdminLearningProgramListResource, "/admin/programs")
api.add_resource(AdminLearningProgramDetailResource, "/admin/programs/<int:program_id>")
api.add_resource(AdminLearningCurriculumResource, "/admin/programs/<int:program_id>/curriculum")
