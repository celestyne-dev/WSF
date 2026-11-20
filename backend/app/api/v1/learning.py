"""WSF Learning: structured educational offerings — see
app/models/learning.py's module docstring for the architecture decision
and what this deliberately does not own (pricing/scheduling/editorial
body/downloads, all left to Product/Event/Article/Resource).
"""
from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import and_, or_

from app.extensions import db
from app.models.commerce import Product
from app.models.learning import (
    ACCESS_TYPES,
    LearningLesson,
    LearningModule,
    LearningProgram,
    LearningProgramEvent,
    LearningProgramRelatedArticle,
    VIDEO_LESSON_TYPES,
)
from app.models.article import Article
from app.models.learning_enrollment import LearningEnrollment
from app.models.media import Media
from app.models.opportunity import Event
from app.models.people import Author, Organization
from app.models.resource import Resource as ResourceModel
from app.models.taxonomy import CAREER_GOALS, Topic
from app.models.user import User
from app.schemas.learning import (
    LearningCurriculumInputSchema,
    LearningProgramInputSchema,
    LearningProgramSchema,
    admin_learning_program_summary_schema,
    learning_program_summary_schema,
    public_learning_program_schema,
)
from app.services.learning_catalog import FORMAT_LABELS, catalog_stats, program_ids_with_format
from app.services.content_blocks import MAX_ASSESSMENT_QUESTIONS, sanitize_questions, sanitize_content_blocks
from app.services.homepage import validate_cta_url
from app.services.video_embed import is_safe_video_url, resolve_video_provider
from app.services.audit import log_action
from app.services.indexnow import capture_public_urls, notify_public_change
from app.services.career_hub import viewer_membership_label
from app.services.circle import circle_tier
from app.services.learning_access import can_access_program_content, program_circle_inclusion
from app.services.learning_certificates import program_issues_certificates
from app.services.learning_enrollments import progress_summary
from app.services.learning_assessments import check_knowledge_answers
from app.services.learning_paths import paths_containing_program
from app.services.public_visibility import public_learning_dump
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

learning_bp = Blueprint("learning", __name__)
api = Api(learning_bp)

program_schema = LearningProgramSchema(context={"include_answers": True})


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


# /learning/paths is the Learning Paths index, so no Program may take it.
RESERVED_LEARNING_SLUGS = ("paths",)


def _learning_slug(slug):
    if slug in RESERVED_LEARNING_SLUGS:
        raise ApiError(f'"{slug}" is reserved in WSF Learning. Choose another slug.', 400, code="reserved_slug")
    return slug


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
    program.learning_outcomes = [o.strip() for o in data.get("learning_outcomes", []) if o and o.strip()]
    program.skills = [k.strip() for k in data.get("skills", []) if k and k.strip()]
    program.lifetime_access = data.get("lifetime_access") or "default"
    program.final_assessment = sanitize_questions(data.get("final_assessment") or [], MAX_ASSESSMENT_QUESTIONS)
    program.final_assessment_required = bool(data.get("final_assessment_required")) and bool(program.final_assessment)
    program.final_assessment_passing_score = data.get("final_assessment_passing_score") or 70
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
    for field in ("certificate_enabled", "certificate_title", "certificate_signatory_name", "certificate_signatory_title"):
        if field in data:
            value = data[field]
            setattr(program, field, value.strip() or None if isinstance(value, str) else value)

    program.related_article_links = [
        LearningProgramRelatedArticle(article_id=article.id, position=i)
        for i, article in enumerate(relations["related_articles"])
    ]
    program.event_links = [
        LearningProgramEvent(event_id=event.id, position=i) for i, event in enumerate(relations["events"])
    ]


def _is_meaningful_lesson(lesson):
    """True iff `lesson` actually carries the content its own lesson_type
    promises — never requires video/audio (Module 10, part B: "do not
    force video"), and a pure-text program satisfies this through
    text/activity lessons alone. Same "real content, not an empty shell"
    check Resource/Job/Event already apply to their own body fields.
    """
    if lesson.lesson_type in ("text", "activity"):
        return bool(
            lesson.content
            and any(
                (block.get("text") or block.get("items")) for block in lesson.content if isinstance(block, dict)
            )
        )
    if lesson.lesson_type == "article":
        return lesson.article_id is not None
    if lesson.lesson_type == "resource":
        return lesson.resource_id is not None
    # external_link and video both resolve through external_url (see
    # app/models/learning.py's LearningLesson docstring) — video is never
    # required, but a video lesson an editor did add is just as
    # "meaningful" as an external_link one once its URL is set.
    return bool(lesson.external_url)


def _resolve_lesson_video(lesson_data, lesson_type, external_url):
    """Video/recording metadata for one submitted lesson. Non-video
    lessons always store none (so switching a lesson's type never leaves
    stale video facts behind). Provider is detected from the URL; a
    contradicting explicit provider, an unsafe captions URL or an unknown
    thumbnail media id is rejected (422/404)."""
    empty = {"video_provider": None, "transcript": None, "captions_url": None, "thumbnail_media_id": None}
    if lesson_type not in VIDEO_LESSON_TYPES:
        return empty
    title = lesson_data["title"]
    try:
        provider = resolve_video_provider(external_url, lesson_data.get("video_provider"))
    except ValueError as exc:
        raise ApiError(f'Lesson "{title}": {exc}', 422, code="invalid_url")
    captions_url = (lesson_data.get("captions_url") or "").strip() or None
    if captions_url and not is_safe_video_url(captions_url):
        raise ApiError(f'Lesson "{title}" has an unsafe captions URL.', 422, code="invalid_url")
    thumbnail_id = lesson_data.get("thumbnail_media_id")
    if thumbnail_id is not None and db.session.get(Media, thumbnail_id) is None:
        raise ApiError(f'Lesson "{title}": thumbnail image not found.', 404, code="not_found")
    transcript = (lesson_data.get("transcript") or "").strip() or None
    return {"video_provider": provider, "transcript": transcript, "captions_url": captions_url,
            "thumbnail_media_id": thumbnail_id}


def _validate_for_publish(program):
    """Enforced only when a program's effective status is "published" — a
    draft may stay incomplete indefinitely, but the public CTA a published
    program promises must actually work (spec: "no fake course gating",
    "public CTA uses Product relationship").

    circle_only additionally requires a real curriculum (Module 10, part
    B) — at least one module containing at least one meaningful lesson —
    so a paid-member program can never be published as an empty shell.
    Entirely satisfied by plain text/activity lessons; video/audio is
    never required. Normal workflow is unaffected: a draft may still
    carry zero modules indefinitely (this only runs when status is
    actually "published").
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
    if program.access_type == "circle_only":
        if not program.modules:
            errors.append("A WSF Circle program needs at least one curriculum module before publishing.")
        elif not any(_is_meaningful_lesson(lesson) for module in program.modules for lesson in module.lessons):
            errors.append("A WSF Circle program needs at least one lesson with real content before publishing.")
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


def _dump_from_id(program_id, schema):
    program = LearningProgram.query.get(program_id)
    return schema.dump(program)


def _programs_with_lesson_type(lesson_type):
    return (
        db.session.query(LearningModule.learning_program_id)
        .join(LearningLesson, LearningLesson.module_id == LearningModule.id)
        .filter(LearningLesson.lesson_type == lesson_type)
    )


class LearningFacetsResource(Resource):
    """Which optional public filters have real content behind them, so the
    Learning page never shows a filter that would return nothing (e.g.
    "Video lessons" before any published program has one). Two EXISTS
    checks over published programs; no per-program work."""

    def get(self):
        published = LearningProgram.query.filter_by(status="published")
        formats = {
            t: db.session.query(published.filter(LearningProgram.id.in_(_programs_with_lesson_type(t))).exists()).scalar()
            for t in VIDEO_LESSON_TYPES
        }
        # Career goals with at least one published course (via its published
        # Topics), and the derived formats that actually exist — so the
        # Learning page never offers a goal or format filter that is empty.
        goal_rows = (
            db.session.query(Topic.career_goal)
            .join(LearningProgram.topics)
            .filter(LearningProgram.status == "published", Topic.status == "published", Topic.career_goal.isnot(None))
            .distinct()
            .all()
        )
        goals = sorted({row[0] for row in goal_rows if row[0] in CAREER_GOALS}, key=CAREER_GOALS.index)
        published_ids = [row[0] for row in published.with_entities(LearningProgram.id).all()]
        derived = {stats["format"] for stats in catalog_stats(published_ids).values() if stats["format"]}
        return success_response({
            "lessonFormats": [t for t in VIDEO_LESSON_TYPES if formats[t]],
            "careerGoals": goals,
            "formats": [f for f in FORMAT_LABELS if f in derived],
        })


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
        if request.args.get("format") in FORMAT_LABELS:
            query = query.filter(LearningProgram.id.in_(program_ids_with_format(request.args["format"])))
        goal = (request.args.get("goal") or "").strip().lower().replace("-", "_")
        if goal in CAREER_GOALS:
            query = query.filter(LearningProgram.topics.any(and_(Topic.career_goal == goal, Topic.status == "published")))
        if request.args.get("lesson_format") in VIDEO_LESSON_TYPES:
            query = query.filter(LearningProgram.id.in_(_programs_with_lesson_type(request.args["lesson_format"])))
        if request.args.get("q"):
            like = f"%{request.args['q']}%"
            query = query.filter(
                or_(
                    LearningProgram.title.ilike(like),
                    LearningProgram.subtitle.ilike(like),
                    LearningProgram.short_description.ilike(like),
                )
            )

        query = query.order_by(LearningProgram.featured.desc(), LearningProgram.created_at.desc())
        result = paginate(query, schema=None)
        summary_schema = learning_program_summary_schema()
        summary_schema.context = {"catalog_stats": catalog_stats([p.id for p in result["items"]])}
        # Linked instructors/provider/topics only when each is itself public.
        items = [public_learning_dump(summary_schema.dump(p), p) for p in result["items"]]
        return success_response(items, meta=result["meta"])


def build_public_program_payload(program, viewer):
    """The public detail payload — full curriculum for `free`, a SAFE
    OUTLINE for circle_only/external/product (see
    public_learning_program_schema). `requiresCircle`/`viewerCanAccess`
    are UI guidance only (spec section K) — the real rule is
    app/services/learning_access.py's can_access_program_content, never
    re-derived here; backend endpoints remain the actual authority.
    """
    payload = public_learning_dump(public_learning_program_schema(program).dump(program), program)
    payload["requiresCircle"] = program.access_type == "circle_only"
    # Only advertised when this program actually issues WSF certificates.
    payload["certificateAvailable"] = program_issues_certificates(program)
    payload["viewerCanAccess"] = can_access_program_content(program, viewer)
    # Published Learning Paths that include this course (title/slug only).
    payload["learningPaths"] = [{"slug": p.slug, "title": p.title} for p in paths_containing_program(program.id)]
    # Viewer-specific (null for anonymous / not covered): e.g. "Included
    # with your Lifetime membership" for an eligible product program —
    # UI guidance only; enrollment/curriculum endpoints stay authoritative.
    payload["viewerMembershipLabel"] = viewer_membership_label(
        program_circle_inclusion(program)["scope"], circle_tier(viewer) if viewer else None,
        free=program.access_type == "free",
    )
    return payload


class LearningKnowledgeCheckResource(Resource):
    """Immediate feedback for a lesson's knowledge-check questions. The
    lesson's Program must be published and its content open to this viewer
    (free: anyone; otherwise the same can_access_program_content rule as
    the protected curriculum). Never blocks or records progress."""

    def post(self, lesson_id):
        lesson = db.session.get(LearningLesson, lesson_id)
        program = lesson.module.program if lesson is not None and lesson.module is not None else None
        if program is None or program.status != "published":
            raise ApiError("Lesson not found.", 404, code="not_found")
        if not can_access_program_content(program, _current_user_or_none()):
            raise ApiError("You do not have access to this lesson.", 403, code="access_denied")
        data = request.get_json(silent=True) or {}
        return success_response({"results": check_knowledge_answers(lesson, data.get("answers"))})


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
        result = paginate(query, schema=None)
        schema = admin_learning_program_summary_schema()
        schema.context = {"catalog_stats": catalog_stats([p.id for p in result["items"]])}
        return success_response(schema.dump(result["items"], many=True), meta=result["meta"])

    def post(self):
        user = _require_manage()
        data = LearningProgramInputSchema().load(request.get_json(silent=True) or {})
        relations = _resolve_program_relations(data)

        program = LearningProgram()
        if data.get("slug"):
            program.slug = _learning_slug(validate_explicit_slug(LearningProgram, data["slug"]))
        else:
            program.slug = generate_unique_slug(LearningProgram, data["title"])
            if program.slug in RESERVED_LEARNING_SLUGS:
                program.slug = generate_unique_slug(LearningProgram, f"{data['title']} course")

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
        notify_public_change({}, program)
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
        public_before = capture_public_urls(program)

        data = LearningProgramInputSchema().load(request.get_json(silent=True) or {})
        relations = _resolve_program_relations(data)

        old_slug = program.slug
        if data.get("slug") and data["slug"] != old_slug:
            program.slug = _learning_slug(validate_explicit_slug(LearningProgram, data["slug"], current_id=program.id))

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

        notify_public_change(public_before, program)
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
        public_before = capture_public_urls(program)

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
                if lesson_type in ("video", "recording", "external_link") and not external_url:
                    raise ApiError(
                        f'Lesson "{lesson_data["title"]}" needs an external URL for lesson type "{lesson_type}".',
                        422,
                        code="validation_error",
                    )

                video = _resolve_lesson_video(lesson_data, lesson_type, external_url)

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
                for key, value in video.items():
                    setattr(lesson, key, value)
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
        # Closes the obvious loophole in "a circle_only program needs real
        # curriculum before it can be published" (Module 10, part B): this
        # is the one other place a published program's modules/lessons
        # can change, so an already-published program must satisfy the
        # same check here, not only at the moment status first flips to
        # "published" (_apply_program_fields's/the detail PATCH's own
        # call site above).
        if program.status == "published":
            _validate_for_publish(program)
        db.session.commit()

        log_action(
            user,
            "learning.curriculum_update",
            "LearningProgram",
            program.id,
            {"module_count": len(new_modules), "lesson_count": sum(len(m.lessons) for m in new_modules)},
        )
        notify_public_change(public_before, program)
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
api.add_resource(LearningFacetsResource, "/meta/facets")
api.add_resource(LearningKnowledgeCheckResource, "/lessons/<int:lesson_id>/knowledge-check")
api.add_resource(LearningProgramPublicDetailResource, "/<string:slug>")
api.add_resource(AdminLearningProgramListResource, "/admin/programs")
api.add_resource(AdminLearningProgramDetailResource, "/admin/programs/<int:program_id>")
api.add_resource(AdminLearningCurriculumResource, "/admin/programs/<int:program_id>/curriculum")
api.add_resource(LearningEnrollmentAdminListResource, "/admin/programs/<int:program_id>/enrollments")
