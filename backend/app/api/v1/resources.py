from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.commerce import Product
from app.models.media import Media
from app.models.newsletter import NewsletterSubscriber
from app.models.people import Author, Organization
from app.models.resource import Resource as ResourceModel, ResourceImage, ResourceLead
from app.models.taxonomy import Tag, Topic
from app.schemas.resource import ResourceInputSchema, ResourceLeadInputSchema, ResourceSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.slugs import slugify
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

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
    guard already applied to Job/Event/Product.
    """
    if resource.status not in ("published", "scheduled"):
        return
    if not resource.description or not any(
        (block.get("text") or block.get("items")) for block in resource.description if isinstance(block, dict)
    ):
        raise ApiError("A published resource needs a description.", 422, code="validation_error")
    if resource.access_type == "external_link" and not resource.external_url:
        raise ApiError("A published external-link resource needs an external URL.", 422, code="validation_error")
    if resource.access_type in ("direct_download", "email_gate") and not resource.file_url and not resource.external_url:
        raise ApiError("A published resource needs a file URL or external URL.", 422, code="validation_error")


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
    # never drift out of sync with it.
    resource.is_premium = resource.access_type == "premium"
    resource.is_external = resource.access_type == "external_link"
    resource.is_downloadable = resource.access_type in ("direct_download", "email_gate")
    resource.file_url = data.get("file_url")
    resource.external_url = data.get("external_url")
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
    free = request.args.get("free")
    if free == "true":
        query = query.filter(ResourceModel.access_type != "premium")
    elif free == "false":
        query = query.filter(ResourceModel.access_type == "premium")

    return query


class ResourceListResource(Resource):
    def get(self):
        user = _current_user_or_none()
        query = _build_query(user)
        result = paginate(query, resource_schema)
        return success_response(result["items"], meta=result["meta"])

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
        publicly_visible = resource.status == "published" or (
            resource.status == "scheduled" and resource.published_date and resource.published_date <= date.today()
        )
        if not publicly_visible and not editor:
            raise ApiError("Resource not found.", 404, code="not_found")
        return success_response(resource_schema.dump(resource))

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


class ResourceAccessResource(Resource):
    """Grants access to a resource per its access_type — the one place the
    free lead-magnet flow, a plain direct download, and an external-link
    hand-off all resolve through. premium/member_only never had a real
    payment/account system to grant against, so they return a 403 the
    frontend renders as an honest "not yet available" state rather than
    faking a working entitlement.
    """

    def post(self, slug):
        resource = ResourceModel.query.filter_by(slug=slug).first()
        if resource is None or resource.status not in ("published", "scheduled"):
            raise ApiError("Resource not found.", 404, code="not_found")

        access_type = resource.access_type

        if access_type == "premium":
            raise ApiError(
                "This is a premium resource. Purchasing isn't available yet.", 403, code="premium_unavailable"
            )
        if access_type == "member_only":
            raise ApiError(
                "This resource requires an account. Accounts aren't available yet.", 403, code="account_required"
            )

        target_url = resource.external_url if access_type == "external_link" else (resource.file_url or resource.external_url)
        if not target_url:
            raise ApiError("This resource has no file or link configured yet.", 409, code="not_configured")

        lead = None
        if access_type == "email_gate":
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
            # list when the visitor explicitly consented.
            if data.get("newsletter_consent"):
                subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
                if subscriber is None:
                    subscriber = NewsletterSubscriber(email=email)
                    db.session.add(subscriber)
                subscriber.first_name = data.get("first_name") or subscriber.first_name
                subscriber.country_code = data.get("country_code") or subscriber.country_code
                subscriber.placement = subscriber.placement or "resource_download"
                subscriber.acquisition = data.get("acquisition") or subscriber.acquisition
                subscriber.status = "active"
                subscriber.unsubscribed_at = None

        resource.download_count = (resource.download_count or 0) + 1
        db.session.commit()

        response = {"url": target_url, "accessType": access_type}
        return success_response(response, status=201 if lead else 200)


api.add_resource(ResourceListResource, "")
api.add_resource(ResourceDetailResource, "/<string:slug>")
api.add_resource(ResourceAccessResource, "/<string:slug>/access")
