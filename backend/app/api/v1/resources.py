"""Resources — public catalog, the one access-grant endpoint, and staff
CRUD. See app/models/resource.py (Resource.ACCESS_TYPES/
is_publicly_visible) and app/services/resource_access.py (the one place
access_type rules — including WSF Circle, via app/services/circle.py's
has_circle_access — are actually evaluated).

SECURITY: an anonymous/ordinary public caller must never receive
file_url/external_url directly from the list/detail endpoints — only
build_public_resource_payload() below is ever returned to such a caller,
and only POST /resources/{slug}/access, after check_resource_access()
succeeds, ever hands back a real target URL. Staff holding
resources.manage still receive the full ResourceSchema dump they need to
edit the resource.
"""
from datetime import date

from flask import Blueprint, current_app, request, send_from_directory
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.commerce import Product
from app.models.media import Media
from app.models.people import Author, Organization
from app.models.resource import Resource as ResourceModel, ResourceImage, ResourceLead
from app.models.taxonomy import Tag, Topic
from app.schemas.media import MediaSchema
from app.schemas.people import AuthorSchema, OrganizationSchema
from app.schemas.resource import ResourceInputSchema, ResourceLeadInputSchema, ResourceSchema
from app.schemas.taxonomy import TagSchema, TopicSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.newsletter import upsert_subscriber
from app.services.resource_access import check_resource_access, viewer_can_access
from app.services.resource_downloads import (
    is_safe_protected_path,
    issue_download_token,
    resolve_download_token,
)
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.slugs import slugify
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response
from app.utils.urls import is_safe_http_url, is_safe_resource_target

resources_bp = Blueprint("resources", __name__)
api = Api(resources_bp)

resource_schema = ResourceSchema()


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _current_user_or_none():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    return current_user


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("resources.manage"):
        raise ApiError("You do not have permission to manage resources.", 403, code="forbidden")
    return user


def _viewer_for_access_check():
    """Distinct from _current_user_or_none(): this one does NOT collapse
    an authenticated-but-inactive account into anonymous — it must reach
    check_resource_access() as itself so that function can tell "no
    account at all" (401 account_required) apart from "a real account
    that's inactive" (403 forbidden), per spec. Same unfiltered pattern
    as app/api/v1/circle.py's _current_user_or_none().
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    return current_user if current_user else None


def _can_edit_or_none():
    try:
        return _require_manage()
    except Exception:
        return None


def _resolve_topics(topic_slugs):
    if not topic_slugs:
        return []
    found = {t.slug: t for t in Topic.query.filter(Topic.slug.in_(topic_slugs)).all()}
    missing = [slug for slug in topic_slugs if slug not in found]
    if missing:
        raise ApiError(f'Topic "{missing[0]}" not found.', 404, code="not_found")
    return [found[slug] for slug in topic_slugs]


def _resolve_tags(raw_tag_slugs):
    # Tags are freeform — same get-or-create-by-slug behavior as Article
    # tags — rather than a hard 404 for a tag an editor is typing for the
    # first time.
    tags = []
    for raw in raw_tag_slugs or []:
        slug = slugify(raw)
        tag = Tag.query.filter_by(slug=slug).first()
        if tag is None:
            tag = Tag(slug=slug, name=raw.replace("-", " ").replace("_", " ").title())
            db.session.add(tag)
        tags.append(tag)
    return tags


def _resolve_author(author_slug):
    if not author_slug:
        return None
    author = Author.query.filter_by(slug=author_slug).first()
    if author is None:
        raise ApiError(f'Author "{author_slug}" not found.', 404, code="not_found")
    return author


def _resolve_sponsor(sponsor_slug):
    if not sponsor_slug:
        return None
    sponsor = Organization.query.filter_by(slug=sponsor_slug).first()
    if sponsor is None:
        raise ApiError(f'Organization "{sponsor_slug}" not found.', 404, code="not_found")
    return sponsor


def _resolve_gallery(media_ids):
    if not media_ids:
        return []
    found = {m.id: m for m in Media.query.filter(Media.id.in_(media_ids)).all()}
    missing = [mid for mid in media_ids if mid not in found]
    if missing:
        raise ApiError(f"Media #{missing[0]} not found.", 404, code="not_found")
    return [ResourceImage(media_id=mid, position=i) for i, mid in enumerate(media_ids)]


def _validate_publish(resource):
    """A published (or scheduled) resource needs a real description and a
    real way to actually get it — same "don't let an empty shell go live"
    guard already applied to Job/Event/Product. Every access type whose
    target the /access endpoint would need to resolve (everything except
    premium, which has no real target yet) must have one configured
    before it can go live — including circle_only, so a Circle member
    can never reach a published resource with nothing behind it.

    circle_only deliberately does NOT accept `file_url` here (Module 10,
    part A) — that field points into the publicly-served MEDIA_ROOT tree,
    which is exactly the "a Circle file must not rely on a publicly
    accessible raw URL" problem this module closes. A circle_only
    resource needs either `protected_file_path` (served only through the
    short-lived token in ResourceDownloadResource below) or an
    `external_url` (an explicit, staff-chosen non-WSF-hosted link — still
    gated by check_resource_access() before it's ever handed back, same
    as before). Every other access type's file_url behavior is
    unchanged.
    """
    if resource.status not in ("published", "scheduled"):
        return
    if not resource.description or not any(
        (block.get("text") or block.get("items")) for block in resource.description if isinstance(block, dict)
    ):
        raise ApiError("A published resource needs a description.", 422, code="validation_error")
    if resource.access_type == "external_link" and not resource.external_url:
        raise ApiError("A published external-link resource needs an external URL.", 422, code="validation_error")
    if resource.access_type in ("direct_download", "email_gate", "member_only") and not (
        resource.file_url or resource.external_url
    ):
        raise ApiError("A published resource needs a file URL or external URL.", 422, code="validation_error")
    if resource.access_type == "circle_only" and not (resource.protected_file_path or resource.external_url):
        raise ApiError(
            "A published WSF Circle resource needs a protected file or an external URL.",
            422,
            code="validation_error",
        )


def _apply_fields(resource, data, topics, tags, author, sponsor, gallery_images):
    resource.name = data["name"]
    resource.subtitle = data.get("subtitle")
    resource.short_description = data.get("short_description")
    resource.description = sanitize_content_blocks(data.get("description", []))
    resource.cover_media_id = data.get("cover_media_id")
    resource.images = gallery_images
    resource.type = data.get("type")
    resource.topics = topics
    resource.tags = tags
    resource.author = author
    resource.author_name = data.get("author_name")
    resource.price = data.get("price", 0)
    resource.currency = data.get("currency", "USD")
    resource.access_type = data.get("access_type", "direct_download")
    # is_premium/is_downloadable/is_external are legacy stored booleans kept
    # for existing call sites (Product-resource linkage, old mock parity);
    # derived here from the one field an editor actually sets, so they can
    # never drift out of sync with it. circle_only is deliberately NOT
    # is_premium — WSF Circle membership and a one-off premium resource
    # purchase are separate commercial concepts (see model docstring).
    resource.is_premium = resource.access_type == "premium"
    resource.is_external = resource.access_type == "external_link"
    resource.is_downloadable = resource.access_type in ("direct_download", "email_gate", "member_only", "circle_only")
    resource.file_url = data.get("file_url")
    resource.external_url = data.get("external_url")
    resource.protected_file_path = data.get("protected_file_path")
    resource.file_format = data.get("file_format")
    resource.file_size = data.get("file_size")
    resource.page_count = data.get("page_count")
    resource.sponsor = sponsor
    resource.sponsored = data.get("sponsored", False)
    resource.featured = data.get("featured", False)
    resource.status = data.get("status", "draft")
    resource.seo = data.get("seo")
    if resource.status in ("published", "scheduled") and resource.published_date is None:
        resource.published_date = data.get("published_date") or date.today()
    elif data.get("published_date"):
        resource.published_date = data["published_date"]
    _validate_publish(resource)


def _is_referenced(resource):
    return Product.query.filter_by(resource_id=resource.id).first() is not None


def _build_query(user):
    can_manage = bool(user and user.has_permission("resources.manage"))
    query = ResourceModel.query.order_by(ResourceModel.featured.desc(), ResourceModel.published_date.desc())

    if can_manage and request.args.get("status"):
        query = query.filter(ResourceModel.status == request.args["status"])
    elif not can_manage:
        today = date.today()
        # Mirrors Resource.is_publicly_visible() exactly — a scheduled
        # resource with a NULL published_date is excluded here the same
        # way that method excludes it (NULL <= today evaluates to NULL/
        # false in SQL, same as the explicit `is not None` check there).
        query = query.filter(
            or_(
                ResourceModel.status == "published",
                (ResourceModel.status == "scheduled") & (ResourceModel.published_date <= today),
            )
        )

    query = apply_equality_filters(query, ResourceModel, request.args, ["type", "access_type"])
    query = apply_search(query, ResourceModel, request.args, ["name", "subtitle", "short_description"])

    if request.args.get("topic"):
        query = query.filter(ResourceModel.topics.any(slug=request.args["topic"]))
    if request.args.get("author"):
        query = query.filter(ResourceModel.author.has(slug=request.args["author"]))
    if request.args.get("featured") == "true":
        query = query.filter(ResourceModel.featured.is_(True))
    # "Free" must exclude circle_only too — it requires an active, paid
    # WSF Circle membership, so it is not genuinely free to a visitor who
    # doesn't have one. ?access_type=circle_only (via apply_equality_filters
    # above) is the public listing's own, correctly-labeled way to find
    # WSF Circle resources; "Free" here means truly free/public access.
    free = request.args.get("free")
    if free == "true":
        query = query.filter(ResourceModel.access_type.notin_(["premium", "circle_only"]))
    elif free == "false":
        query = query.filter(ResourceModel.access_type == "premium")

    return query


def build_public_resource_payload(resource, viewer):
    """The one public-safe Resource representation — never includes
    file_url/external_url (see module docstring). `viewerCanAccess` is a
    serialization-only hint (app/services/resource_access.py never
    resolves or leaks the target itself); POST /access remains the sole
    authoritative grant.
    """
    return {
        "id": resource.id,
        "slug": resource.slug,
        "name": resource.name,
        "subtitle": resource.subtitle,
        "shortDescription": resource.short_description,
        "description": resource.description or [],
        "coverMedia": MediaSchema().dump(resource.cover_media) if resource.cover_media else None,
        "images": [
            {"id": img.id, "position": img.position, "media": MediaSchema().dump(img.media)}
            for img in resource.images
        ],
        "type": resource.type,
        "topics": TopicSchema(many=True, exclude=("article_count",)).dump(resource.topics),
        "tags": TagSchema(many=True).dump(resource.tags),
        "author": AuthorSchema(exclude=("article_count",)).dump(resource.author) if resource.author else None,
        "authorName": resource.author_name,
        "price": resource.price,
        "currency": resource.currency,
        "accessType": resource.access_type,
        "isFree": resource.access_type != "premium",
        "isPremium": resource.is_premium,
        "isDownloadable": resource.is_downloadable,
        "isExternal": resource.is_external,
        "requiresEmail": resource.access_type == "email_gate",
        "requiresAccount": resource.access_type in ("member_only", "circle_only"),
        "requiresCircle": resource.access_type == "circle_only",
        "viewerCanAccess": viewer_can_access(resource, viewer),
        "fileFormat": resource.file_format,
        "fileSize": resource.file_size,
        "pageCount": resource.page_count,
        "sponsor": (
            OrganizationSchema(only=("id", "slug", "name", "logo")).dump(resource.sponsor)
            if resource.sponsor
            else None
        ),
        "sponsored": resource.sponsored,
        "downloadCount": resource.download_count,
        "featured": resource.featured,
        "status": resource.status,
        "publishedDate": resource.published_date.isoformat() if resource.published_date else None,
        "seo": resource.seo or {},
        "linkedProduct": _linked_product_payload(resource),
    }


def _linked_product_payload(resource):
    product = Product.query.filter_by(resource_id=resource.id).first()
    if product is None:
        return None
    return {"id": product.id, "slug": product.slug, "name": product.name, "status": product.status}


class ResourceListResource(Resource):
    def get(self):
        user = _current_user_or_none()
        query = _build_query(user)
        can_manage = bool(user and user.has_permission("resources.manage"))
        result = paginate(query, resource_schema if can_manage else None)
        if can_manage:
            return success_response(result["items"], meta=result["meta"])
        items = [build_public_resource_payload(r, user) for r in result["items"]]
        return success_response(items, meta=result["meta"])

    def post(self):
        _require_manage()
        data = ResourceInputSchema().load(request.get_json(silent=True) or {})
        topics = _resolve_topics(data.get("topic_slugs", []))
        tags = _resolve_tags(data.get("tag_slugs", []))
        author = _resolve_author(data.get("author_slug"))
        sponsor = _resolve_sponsor(data.get("sponsor_slug"))
        gallery_images = _resolve_gallery(data.get("gallery_media_ids", []))

        resource = ResourceModel()
        if data.get("slug"):
            resource.slug = validate_explicit_slug(ResourceModel, data["slug"])
        else:
            resource.slug = generate_unique_slug(ResourceModel, data["name"])

        _apply_fields(resource, data, topics, tags, author, sponsor, gallery_images)
        db.session.add(resource)
        db.session.commit()
        return success_response(resource_schema.dump(resource), status=201)


class ResourceDetailResource(Resource):
    def get(self, slug):
        resource = ResourceModel.query.filter_by(slug=slug).first()
        if resource is None:
            raise ApiError("Resource not found.", 404, code="not_found")
        editor = _can_edit_or_none()
        if not resource.is_publicly_visible() and not editor:
            raise ApiError("Resource not found.", 404, code="not_found")
        if editor:
            return success_response(resource_schema.dump(resource))
        return success_response(build_public_resource_payload(resource, _current_user_or_none()))

    def put(self, slug):
        resource = ResourceModel.query.filter_by(slug=slug).first()
        if resource is None:
            raise ApiError("Resource not found.", 404, code="not_found")
        _require_manage()

        data = ResourceInputSchema().load(request.get_json(silent=True) or {})
        topics = _resolve_topics(data.get("topic_slugs", []))
        tags = _resolve_tags(data.get("tag_slugs", []))
        author = _resolve_author(data.get("author_slug"))
        sponsor = _resolve_sponsor(data.get("sponsor_slug"))
        gallery_images = _resolve_gallery(data.get("gallery_media_ids", []))

        if data.get("slug") and data["slug"] != resource.slug:
            resource.slug = validate_explicit_slug(ResourceModel, data["slug"], current_id=resource.id)

        _apply_fields(resource, data, topics, tags, author, sponsor, gallery_images)
        db.session.commit()
        return success_response(resource_schema.dump(resource))

    def delete(self, slug):
        resource = ResourceModel.query.filter_by(slug=slug).first()
        if resource is None:
            raise ApiError("Resource not found.", 404, code="not_found")
        _require_manage()

        if _is_referenced(resource):
            raise ApiError(
                "This resource is linked to a Shop product and can't be deleted. "
                "Archive it instead to keep the product listing intact.",
                409,
                code="reference_conflict",
            )

        db.session.delete(resource)
        db.session.commit()
        return success_response({"deleted": True})


def _resolve_target_url(resource, viewer):
    """The one place a real target is ever computed — only ever called
    after check_resource_access() has already succeeded. Re-validates
    safety at resolution time too (not just at save time), so a row
    saved before this validation existed can never hand back an unsafe
    scheme or a raw filesystem path.

    circle_only with a protected_file_path never hands back a raw
    filesystem path or public URL — it issues a short-lived,
    resource-bound download token (Module 10, part A) and returns the
    path to ResourceDownloadResource below instead. A circle_only
    resource configured with only an external_url (no protected file)
    still returns that URL directly, same as before — an explicit,
    staff-chosen non-WSF-hosted link, already gated by
    check_resource_access() having just succeeded.
    """
    if resource.access_type == "external_link":
        candidate = resource.external_url
        if not candidate or not is_safe_http_url(candidate):
            raise ApiError("This resource has no file or link configured yet.", 409, code="not_configured")
        return candidate

    if resource.access_type == "circle_only" and resource.protected_file_path:
        if not is_safe_protected_path(resource.protected_file_path):
            raise ApiError("This resource has no file or link configured yet.", 409, code="not_configured")
        raw_token = issue_download_token(resource, viewer)
        return f"/api/v1/resources/downloads/{raw_token}"

    candidate = resource.file_url or resource.external_url
    if not candidate or not is_safe_resource_target(candidate):
        raise ApiError("This resource has no file or link configured yet.", 409, code="not_configured")
    return candidate


class ResourceAccessResource(Resource):
    """The ONE access-grant endpoint — every access_type's real target
    resolves through here, and only here. See
    app/services/resource_access.py's check_resource_access() for the
    actual entitlement rules (member_only/circle_only/premium); nothing
    here re-derives WSF Circle logic.
    """

    def post(self, slug):
        resource = ResourceModel.query.filter_by(slug=slug).first()
        if resource is None or not resource.is_publicly_visible():
            raise ApiError("Resource not found.", 404, code="not_found")

        viewer = _viewer_for_access_check()
        # Raises (401/403) and stops here on denial — no target is
        # resolved, no lead is recorded, no download_count increment
        # happens for a denied request of any kind.
        check_resource_access(resource, viewer)

        target_url = _resolve_target_url(resource, viewer)

        lead = None
        if resource.access_type == "email_gate":
            data = ResourceLeadInputSchema().load(request.get_json(silent=True) or {})
            email = data["email"].lower()
            lead = ResourceLead(
                resource_id=resource.id,
                email=email,
                first_name=data.get("first_name"),
                country_code=data.get("country_code"),
                newsletter_consent=data.get("newsletter_consent", False),
                acquisition=data.get("acquisition"),
            )
            db.session.add(lead)

            # Never force a subscription — only upsert into the newsletter
            # list when the visitor explicitly consented. Goes through the
            # one shared newsletter consent function so suppression/
            # resubscribe rules stay consistent with every other signup
            # surface on the site.
            if data.get("newsletter_consent"):
                upsert_subscriber(
                    email,
                    first_name=data.get("first_name"),
                    country_code=data.get("country_code"),
                    placement="resource_download",
                    acquisition=data.get("acquisition"),
                )

        resource.download_count = (resource.download_count or 0) + 1
        db.session.commit()

        response = {"url": target_url, "accessType": resource.access_type}
        return success_response(response, status=201 if lead else 200)


class ResourceDownloadResource(Resource):
    """Redeems a short-lived download token issued by
    ResourceAccessResource above and streams the protected file. The
    token alone is the credential — no JWT/session is checked here, and
    Circle entitlement is NOT re-verified (see
    app/services/resource_downloads.py's module docstring for why that's
    the correct, deliberate design, not an oversight).

    Served by Flask/Gunicorn directly (send_from_directory), never by
    Nginx — see the final report's "Flask streaming vs X-Accel-Redirect"
    comparison for why that's the right choice at WSF's current scale.
    send_from_directory() itself refuses any `..` traversal attempt
    inside `filename`; resolve_download_token() additionally refuses to
    return a resource at all unless its stored protected_file_path is
    independently judged safe by the same is_safe_protected_path() check
    applied at save time.
    """

    def get(self, token):
        resource = resolve_download_token(token)
        return send_from_directory(
            current_app.config["PROTECTED_MEDIA_ROOT"],
            resource.protected_file_path,
            as_attachment=True,
        )


api.add_resource(ResourceListResource, "")
api.add_resource(ResourceDetailResource, "/<string:slug>")
api.add_resource(ResourceAccessResource, "/<string:slug>/access")
api.add_resource(ResourceDownloadResource, "/downloads/<string:token>")
