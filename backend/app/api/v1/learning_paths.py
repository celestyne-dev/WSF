"""WSF Learning Paths — public catalog/detail and Studio management.

Public endpoints only ever return PUBLISHED paths and, inside them, only
PUBLISHED programs (as catalog summaries — never lesson bodies). Viewer
progress is the signed-in learner's own and is derived from her
enrollments (app/services/learning_paths.py). Studio endpoints require
the existing `learning.manage` permission.
"""
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from marshmallow import Schema, fields, validate

from app.extensions import db
from app.models.learning import DIFFICULTY_LEVELS, LEARNING_STATUSES, LearningPath
from app.models.media import Media
from app.models.taxonomy import CAREER_GOALS
from app.schemas.learning import summary_schema_for
from app.schemas.media import MediaSchema
from app.services.audit import log_action
from app.services.circle import has_lifetime_circle_access
from app.services.career_hub import GOAL_LABELS, url_value
from app.services.content_blocks import sanitize_content_blocks
from app.services.learning_catalog import catalog_stats
from app.services.learning_paths import (
    path_facts,
    public_paths_query,
    published_programs,
    recommended_paths_for_goals,
    set_path_programs,
    viewer_path_progress,
)
from app.services.public_visibility import public_learning_dump
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.responses import ApiError, success_response

learning_paths_bp = Blueprint("learning_paths", __name__)
api = Api(learning_paths_bp)

MAX_PATH_PROGRAMS = 12
_media_schema = MediaSchema()


def _viewer():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    return current_user


def _require_manage():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    if not current_user.has_permission("learning.manage"):
        raise ApiError("You do not have permission to manage Learning paths.", 403, code="forbidden")
    return current_user


def _goal(path):
    if path.career_goal in GOAL_LABELS:
        return {"key": path.career_goal, "slug": url_value(path.career_goal), "label": GOAL_LABELS[path.career_goal]}
    return None


def _summary(path, stats):
    programs = published_programs(path)
    return {
        "id": path.id,
        "slug": path.slug,
        "title": path.title,
        "subtitle": path.subtitle,
        "shortDescription": path.short_description,
        "heroMedia": _media_schema.dump(path.hero_media) if path.hero_media else None,
        "careerGoal": _goal(path),
        "difficultyLevel": path.difficulty_level,
        "featured": path.featured,
        "courseTitles": [p.title for p in programs][:6],
        **path_facts(path, stats),
    }


def _stats_for(paths):
    ids = [p.id for path in paths for p in published_programs(path)]
    return catalog_stats(ids)


class LearningPathListResource(Resource):
    def get(self):
        query = public_paths_query()
        goal = (request.args.get("goal") or "").strip().lower().replace("-", "_")
        if goal in CAREER_GOALS:
            query = query.filter(LearningPath.career_goal == goal)
        if request.args.get("featured") == "true":
            query = query.filter(LearningPath.featured.is_(True))
        paths = query.order_by(LearningPath.featured.desc(), LearningPath.published_at.desc().nullslast(), LearningPath.id.desc()).limit(48).all()
        stats = _stats_for(paths)
        # A path with no published course is not shown publicly.
        items = [_summary(p, stats) for p in paths]
        return success_response([i for i in items if i["courseCount"] > 0])


class LearningPathRecommendedResource(Resource):
    """Deterministic "Recommended for your goals" (never AI): published
    paths matching the signed-in learner's saved Career Hub goals."""

    def get(self):
        user = _viewer()
        goals = [g for g in ((user.career_goals or []) if user else []) if g in GOAL_LABELS]
        paths = recommended_paths_for_goals(goals)
        stats = _stats_for(paths)
        items = [i for i in (_summary(p, stats) for p in paths) if i["courseCount"] > 0]
        return success_response({"goals": [{"key": g, "label": GOAL_LABELS[g]} for g in goals], "items": items})


def build_public_path_payload(path, viewer):
    programs = published_programs(path)
    stats = catalog_stats([p.id for p in programs])
    schema = summary_schema_for([])
    schema.context = {"catalog_stats": stats}
    courses = [public_learning_dump(schema.dump(p), p) for p in programs]
    return {
        **_summary(path, stats),
        "description": path.description or [],
        "courses": courses,
        "seo": {k: v for k, v in (path.seo or {}).items() if k in ("title", "description", "canonical", "robots")},
        "viewerProgress": viewer_path_progress(path, viewer),
        # Display only: a Lifetime member sees "Included in your Lifetime
        # membership" instead of the sales note (access stays per course).
        "viewerIsLifetime": bool(viewer) and has_lifetime_circle_access(viewer),
    }


class LearningPathDetailResource(Resource):
    def get(self, slug):
        path = public_paths_query().filter(LearningPath.slug == slug).first()
        if path is None or not published_programs(path):
            raise ApiError("Learning path not found.", 404, code="not_found")
        return success_response(build_public_path_payload(path, _viewer()))


# --- Studio -----------------------------------------------------------------

class LearningPathInputSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    subtitle = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription", validate=validate.Length(max=600))
    description = fields.List(fields.Dict(), required=False, load_default=list)
    career_goal = fields.String(required=False, allow_none=True, data_key="careerGoal", validate=validate.OneOf(CAREER_GOALS))
    difficulty_level = fields.String(required=False, allow_none=True, data_key="difficultyLevel", validate=validate.OneOf(DIFFICULTY_LEVELS))
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(LEARNING_STATUSES))
    featured = fields.Boolean(required=False, load_default=False)
    seo = fields.Dict(required=False, allow_none=True)
    program_ids = fields.List(fields.Integer(), required=False, load_default=list, data_key="programIds",
                              validate=validate.Length(max=MAX_PATH_PROGRAMS))


def _admin_dump(path):
    return {
        "id": path.id,
        "slug": path.slug,
        "title": path.title,
        "subtitle": path.subtitle,
        "shortDescription": path.short_description,
        "description": path.description or [],
        "careerGoal": path.career_goal,
        "difficultyLevel": path.difficulty_level,
        "heroMedia": _media_schema.dump(path.hero_media) if path.hero_media else None,
        "status": path.status,
        "featured": path.featured,
        "publishedAt": path.published_at.isoformat() if path.published_at else None,
        "updatedAt": path.updated_at.isoformat() if path.updated_at else None,
        "seo": path.seo or {},
        "programs": [
            {"id": link.program.id, "title": link.program.title, "slug": link.program.slug, "status": link.program.status}
            for link in path.program_links if link.program is not None
        ],
    }


# Path slugs share /learning-paths/<slug> with these fixed endpoints.
_RESERVED_PATH_SLUGS = ("admin", "recommended")


def _apply(path, data, is_new):
    if data.get("slug") and data["slug"].strip().lower() in _RESERVED_PATH_SLUGS:
        raise ApiError("That slug is reserved. Choose another.", 400, code="reserved_slug")
    if data.get("slug"):
        slug = validate_explicit_slug(LearningPath, data["slug"], current_id=None if is_new else path.id)
    elif is_new:
        slug = generate_unique_slug(LearningPath, data["title"])
        if slug in _RESERVED_PATH_SLUGS:
            slug = generate_unique_slug(LearningPath, f"{data['title']} path")
    else:
        slug = path.slug
    path.slug = slug
    if is_new:
        # Only now (slug set) may the new row join the session — later
        # queries autoflush it.
        db.session.add(path)
    path.title = data["title"].strip()
    path.subtitle = (data.get("subtitle") or "").strip() or None
    path.short_description = (data.get("short_description") or "").strip() or None
    path.description = sanitize_content_blocks(data.get("description") or [])
    path.career_goal = data.get("career_goal") or None
    path.difficulty_level = data.get("difficulty_level") or None
    media_id = data.get("hero_media_id")
    if media_id is not None and db.session.get(Media, media_id) is None:
        raise ApiError("Hero image not found.", 404, code="not_found")
    path.hero_media_id = media_id
    path.featured = bool(data.get("featured"))
    seo = data.get("seo") or {}
    path.seo = {k: (seo.get(k) or "").strip()[:300] for k in ("title", "description") if isinstance(seo.get(k), str)}
    set_path_programs(path, data.get("program_ids") or [])
    previous = path.status
    path.status = data.get("status") or "draft"
    if path.status == "published":
        if not published_programs(path):
            raise ApiError("A published learning path needs at least one published course.", 422, code="publish_validation_failed")
        if previous != "published" or path.published_at is None:
            path.published_at = datetime.now(timezone.utc)


class AdminLearningPathListResource(Resource):
    def get(self):
        _require_manage()
        paths = LearningPath.query.order_by(LearningPath.updated_at.desc()).all()
        return success_response([
            {"id": p.id, "slug": p.slug, "title": p.title, "status": p.status, "featured": p.featured,
             "careerGoal": p.career_goal, "courseCount": len(p.program_links),
             "updatedAt": p.updated_at.isoformat() if p.updated_at else None}
            for p in paths
        ])

    def post(self):
        user = _require_manage()
        data = LearningPathInputSchema().load(request.get_json(silent=True) or {})
        path = LearningPath()
        _apply(path, data, is_new=True)
        db.session.commit()
        log_action(user, "learning_path.create", "LearningPath", path.id, {"status": path.status})
        return success_response(_admin_dump(path), status=201)


class AdminLearningPathDetailResource(Resource):
    def _get(self, path_id):
        path = db.session.get(LearningPath, path_id)
        if path is None:
            raise ApiError("Learning path not found.", 404, code="not_found")
        return path

    def get(self, path_id):
        _require_manage()
        return success_response(_admin_dump(self._get(path_id)))

    def put(self, path_id):
        user = _require_manage()
        path = self._get(path_id)
        data = LearningPathInputSchema().load(request.get_json(silent=True) or {})
        _apply(path, data, is_new=False)
        db.session.commit()
        log_action(user, "learning_path.update", "LearningPath", path.id, {"status": path.status})
        return success_response(_admin_dump(path))

    def delete(self, path_id):
        user = _require_manage()
        path = self._get(path_id)
        db.session.delete(path)
        db.session.commit()
        log_action(user, "learning_path.delete", "LearningPath", path_id, None)
        return success_response({"deleted": True})


api.add_resource(LearningPathListResource, "")
api.add_resource(LearningPathRecommendedResource, "/recommended")
api.add_resource(AdminLearningPathListResource, "/admin")
api.add_resource(AdminLearningPathDetailResource, "/admin/<int:path_id>")
api.add_resource(LearningPathDetailResource, "/<string:slug>")
