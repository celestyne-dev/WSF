import datetime

from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.page import PAGE_STATUSES, SYSTEM_PAGE_KEYS, Page, PageRevision
from app.schemas.page import (
    PageInputSchema,
    PagePublicSchema,
    PageReviewInputSchema,
    PageRevisionSchema,
    PageSchema,
    PageStatusUpdateSchema,
    PageUpdateSchema,
)
from app.services.audit import log_action
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

# Public read (`/public/<key>`, published-only) and admin CRUD/status/
# review/revisions (`taxonomy`-CMS-style, gated by pages.manage/
# pages.publish) live together in this one blueprint — there is no
# pre-existing public Pages contract to preserve separately, unlike
# Taxonomy's split public/admin files.
pages_bp = Blueprint("pages", __name__)
api = Api(pages_bp)

page_schema = PageSchema()
page_public_schema = PagePublicSchema()
page_revision_schema = PageRevisionSchema()


def _get_page_or_404(page_id):
    page = db.session.get(Page, page_id)
    if page is None:
        raise ApiError("Page not found.", 404, code="not_found")
    return page


def _unique_general_page_slug(base_value, current_id=None):
    """Delegates to the same reserved-slug + uniqueness logic Article uses
    (app/services/slugs.py), then additionally steps past any slug already
    claimed by a published-or-not Article — Articles use flat top-level
    URLs, so a Page and an Article can otherwise collide at the same path.
    """
    candidate = generate_unique_slug(Page, base_value, current_id=current_id)
    suffix = 2
    base = candidate
    while Article.query.filter_by(slug=candidate).first() is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _validate_general_page_slug(raw_slug, current_id=None):
    candidate = validate_explicit_slug(Page, raw_slug, current_id=current_id)
    if Article.query.filter_by(slug=candidate).first() is not None:
        raise ApiError(
            f'"{candidate}" is already used by a published article URL and cannot be used as a page slug.',
            409,
            code="slug_taken",
        )
    return candidate


def _json_safe_changes(data):
    """AuditLog.changes is a JSON column — a raw date/datetime from a
    loaded schema (effective_date, say) would otherwise blow up the
    INSERT. Everything else in Page's input schemas is already
    JSON-native.
    """
    return {
        k: (v.isoformat() if isinstance(v, (datetime.date, datetime.datetime)) else v)
        for k, v in data.items()
        if k != "content"
    }


def _snapshot(page, user, note=None):
    db.session.add(PageRevision(page_id=page.id, data=page_schema.dump(page), note=note, created_by_id=user.id if user else None))


class PublicPageResource(Resource):
    def get(self, key):
        page = Page.query.filter_by(key=key, status="published").first()
        if page is None:
            raise ApiError("Page not found.", 404, code="not_found")
        return success_response(page_public_schema.dump(page))


class PageListResource(Resource):
    @permission_required("pages.manage")
    def get(self):
        query = Page.query
        if request.args.get("status"):
            query = query.filter(Page.status == request.args["status"])
        query = apply_equality_filters(query, Page, request.args, ["page_type"])
        query = apply_search(query, Page, request.args, ["title", "key", "slug"], param="q")
        query = query.order_by(Page.page_type, Page.title)
        result = paginate(query, page_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("pages.manage")
    def post(self):
        data = PageInputSchema().load(request.get_json(silent=True) or {})
        if data.get("page_type") == "system":
            raise ApiError(
                "System pages are fixed to this app's existing routes and can't be created here.",
                400,
                code="invalid_page_type",
            )

        page = Page(
            page_type="general",
            title=data["title"],
            internal_name=data.get("internal_name"),
            subtitle=data.get("subtitle"),
            content=sanitize_content_blocks(data.get("content") or []),
            hero_media_id=data.get("hero_media_id"),
            seo=data.get("seo"),
            status=data.get("status", "draft"),
            effective_date=data.get("effective_date"),
        )
        if page.status == "published" and not (current_user and current_user.has_permission("pages.publish", "pages.manage")):
            raise ApiError("You do not have permission to publish pages.", 403, code="forbidden")

        page.slug = _validate_general_page_slug(data["slug"], None) if data.get("slug") else _unique_general_page_slug(data["title"])
        page.key = page.slug

        if page.status == "published":
            page.published_at = db.func.now()
        page.updated_by_id = current_user.id if current_user else None

        db.session.add(page)
        db.session.commit()
        _snapshot(page, current_user, note="Created")
        db.session.commit()
        log_action(current_user, "page.create", "Page", page.id, {"key": page.key, "title": page.title})
        return success_response(page_schema.dump(page), status=201)


class PageDetailResource(Resource):
    @permission_required("pages.manage")
    def get(self, page_id):
        return success_response(page_schema.dump(_get_page_or_404(page_id)))

    @permission_required("pages.manage")
    def put(self, page_id):
        page = _get_page_or_404(page_id)
        data = PageUpdateSchema().load(request.get_json(silent=True) or {})

        if "slug" in data and data["slug"] and page.page_type == "general" and data["slug"] != page.slug:
            page.slug = _validate_general_page_slug(data["slug"], current_id=page.id)
            page.key = page.slug
        # A system page's slug/key are fixed to its route — any slug the
        # client sends for one is silently ignored rather than erroring,
        # so a generic "save" doesn't fail over a field the UI shouldn't
        # have let them touch in the first place.

        for field in ("title", "internal_name", "subtitle", "hero_media_id", "seo", "effective_date"):
            if field in data:
                setattr(page, field, data[field])
        if "content" in data:
            page.content = sanitize_content_blocks(data["content"])

        page.updated_by_id = current_user.id if current_user else None
        db.session.commit()
        _snapshot(page, current_user, note="Updated")
        db.session.commit()
        log_action(current_user, "page.update", "Page", page.id, _json_safe_changes(data))
        return success_response(page_schema.dump(page))

    @permission_required("pages.manage")
    def delete(self, page_id):
        page = _get_page_or_404(page_id)
        if page.is_system():
            raise ApiError(
                "This is a required system page and can't be deleted. Unpublish or archive it instead.",
                409,
                code="system_page_protected",
            )
        db.session.delete(page)
        db.session.commit()
        log_action(current_user, "page.delete", "Page", page_id, {"key": page.key, "title": page.title})
        return "", 204


class PageStatusResource(Resource):
    @permission_required("pages.manage")
    def put(self, page_id):
        page = _get_page_or_404(page_id)
        data = PageStatusUpdateSchema().load(request.get_json(silent=True) or {})
        new_status = data["status"]

        if new_status == "published" and not current_user.has_permission("pages.publish", "pages.manage"):
            raise ApiError("You do not have permission to publish pages.", 403, code="forbidden")
        if page.is_system() and new_status == "archived":
            raise ApiError(
                "Required system pages can't be archived — set to draft to take them offline temporarily, "
                "or keep them published.",
                409,
                code="system_page_protected",
            )

        previous_status = page.status
        page.status = new_status
        if new_status == "published" and previous_status != "published":
            page.published_at = db.func.now()
        page.updated_by_id = current_user.id if current_user else None
        db.session.commit()
        _snapshot(page, current_user, note=f"Status: {previous_status} → {new_status}")
        db.session.commit()
        log_action(current_user, "page.status_change", "Page", page.id, {"from": previous_status, "to": new_status})
        return success_response(page_schema.dump(page))


class PageReviewResource(Resource):
    @permission_required("pages.manage")
    def put(self, page_id):
        page = _get_page_or_404(page_id)
        data = PageReviewInputSchema().load(request.get_json(silent=True) or {})
        page.last_reviewed_at = db.func.now()
        page.last_reviewed_by_id = current_user.id if current_user else None
        db.session.commit()
        log_action(current_user, "page.reviewed", "Page", page.id, {"note": data.get("note")})
        return success_response(page_schema.dump(page))


class PageRevisionListResource(Resource):
    @permission_required("pages.manage")
    def get(self, page_id):
        _get_page_or_404(page_id)
        revisions = (
            PageRevision.query.filter_by(page_id=page_id).order_by(PageRevision.created_at.desc()).limit(50).all()
        )
        return success_response(page_revision_schema.dump(revisions, many=True))


api.add_resource(PublicPageResource, "/public/<string:key>")
api.add_resource(PageListResource, "")
api.add_resource(PageDetailResource, "/<int:page_id>")
api.add_resource(PageStatusResource, "/<int:page_id>/status")
api.add_resource(PageReviewResource, "/<int:page_id>/review")
api.add_resource(PageRevisionListResource, "/<int:page_id>/revisions")
