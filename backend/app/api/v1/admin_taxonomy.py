from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.taxonomy import Category, Series, Tag, Topic
from app.schemas.taxonomy import (
    CategoryInputSchema,
    CategorySchema,
    CategoryUpdateSchema,
    SeriesInputSchema,
    SeriesSchema,
    SeriesUpdateSchema,
    TagInputSchema,
    TagMergeSchema,
    TagSchema,
    TagUpdateSchema,
    TaxonomyStatusUpdateSchema,
    TopicInputSchema,
    TopicSchema,
    TopicUpdateSchema,
)
from app.services.audit import log_action
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.services.taxonomy import (
    category_usage_counts,
    find_duplicate_name,
    merge_tags,
    series_usage_counts,
    tag_usage_counts,
    topic_usage_counts,
)
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

# Authenticated CRUD/status/merge management for Topic/Category/Series/Tag,
# gated by taxonomy.manage. The read-only public contract (flat published-
# only arrays + detail pages) lives entirely in app/api/v1/taxonomy.py and
# is untouched by anything here.
admin_taxonomy_bp = Blueprint("admin_taxonomy", __name__)
api = Api(admin_taxonomy_bp)

topic_schema = TopicSchema()
category_schema = CategorySchema()
series_schema = SeriesSchema()
tag_schema = TagSchema()


def _with_usage(dumped_items, usage_counts):
    for item in dumped_items:
        item["usageCount"] = usage_counts.get(item["id"], 0)
    return dumped_items


def _apply_slug(model, instance, data, base_name):
    """Slug is stable by default — a rename never silently changes the
    URL. Only touch it when the request explicitly sends a `slug`, or on
    first creation when none was given.
    """
    if data.get("slug"):
        if data["slug"] != instance.slug:
            instance.slug = validate_explicit_slug(model, data["slug"], current_id=instance.id)
    elif instance.slug is None:
        instance.slug = generate_unique_slug(model, base_name)


def _reject_duplicate_name(model, name, exclude_id=None):
    existing = find_duplicate_name(model, name, exclude_id=exclude_id)
    if existing is not None:
        raise ApiError(
            f'"{name}" is already in use (as "{existing.name}"). Choose a different name, or edit the existing one.',
            409,
            code="duplicate_name",
        )


class TopicAdminListResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self):
        query = Topic.query
        if request.args.get("status"):
            query = query.filter(Topic.status == request.args["status"])
        query = apply_search(query, Topic, request.args, ["name", "description"], param="q")
        query = query.order_by(Topic.sort_order, Topic.name)
        result = paginate(query, None)
        items = topic_schema.dump(result["items"], many=True)
        usage = topic_usage_counts([t.id for t in result["items"]])
        return success_response(_with_usage(items, usage), meta=result["meta"])

    @permission_required("taxonomy.manage")
    def post(self):
        data = TopicInputSchema().load(request.get_json(silent=True) or {})
        _reject_duplicate_name(Topic, data["name"])

        topic = Topic(
            name=data["name"],
            description=data.get("description"),
            hero_media_id=data.get("hero_media_id"),
            seo=data.get("seo"),
            status=data.get("status", "draft"),
            sort_order=data.get("sort_order", 0),
        )
        topic.slug = data.get("slug") or generate_unique_slug(Topic, data["name"])
        db.session.add(topic)
        db.session.commit()
        log_action(current_user, "topic.create", "Topic", topic.id, {"name": topic.name})
        return success_response(topic_schema.dump(topic), status=201)


class TopicAdminDetailResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self, topic_id):
        topic = Topic.query.get(topic_id)
        if topic is None:
            raise ApiError("Topic not found.", 404, code="not_found")
        dumped = topic_schema.dump(topic)
        dumped["usageCount"] = topic_usage_counts([topic.id]).get(topic.id, 0)
        return success_response(dumped)

    @permission_required("taxonomy.manage")
    def put(self, topic_id):
        topic = Topic.query.get(topic_id)
        if topic is None:
            raise ApiError("Topic not found.", 404, code="not_found")

        data = TopicUpdateSchema().load(request.get_json(silent=True) or {})
        if "name" in data:
            _reject_duplicate_name(Topic, data["name"], exclude_id=topic.id)
            topic.name = data["name"]
        _apply_slug(Topic, topic, data, topic.name)
        for field in ("description", "hero_media_id", "seo", "status", "sort_order"):
            if field in data:
                setattr(topic, field, data[field])

        db.session.commit()
        log_action(current_user, "topic.update", "Topic", topic.id, data)
        return success_response(topic_schema.dump(topic))

    @permission_required("taxonomy.manage")
    def delete(self, topic_id):
        topic = Topic.query.get(topic_id)
        if topic is None:
            raise ApiError("Topic not found.", 404, code="not_found")

        usage = topic_usage_counts([topic.id]).get(topic.id, 0)
        if usage > 0:
            raise ApiError(
                f"This topic is used by {usage} item(s) and can't be deleted. "
                "Archive it instead, or reassign those items to a different topic first.",
                409,
                code="reference_conflict",
            )

        db.session.delete(topic)
        db.session.commit()
        log_action(current_user, "topic.delete", "Topic", topic_id, {"name": topic.name})
        return "", 204


class TopicAdminStatusResource(Resource):
    @permission_required("taxonomy.manage")
    def put(self, topic_id):
        topic = Topic.query.get(topic_id)
        if topic is None:
            raise ApiError("Topic not found.", 404, code="not_found")
        data = TaxonomyStatusUpdateSchema().load(request.get_json(silent=True) or {})
        topic.status = data["status"]
        db.session.commit()
        log_action(current_user, "topic.status_change", "Topic", topic.id, {"status": topic.status})
        return success_response(topic_schema.dump(topic))


class CategoryAdminListResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self):
        query = Category.query
        if request.args.get("status"):
            query = query.filter(Category.status == request.args["status"])
        query = apply_search(query, Category, request.args, ["name", "description"], param="q")
        query = query.order_by(Category.sort_order, Category.name)
        result = paginate(query, None)
        items = category_schema.dump(result["items"], many=True)
        usage = category_usage_counts([c.id for c in result["items"]])
        return success_response(_with_usage(items, usage), meta=result["meta"])

    @permission_required("taxonomy.manage")
    def post(self):
        data = CategoryInputSchema().load(request.get_json(silent=True) or {})
        _reject_duplicate_name(Category, data["name"])

        category = Category(
            name=data["name"],
            description=data.get("description"),
            status=data.get("status", "draft"),
            sort_order=data.get("sort_order", 0),
        )
        category.slug = data.get("slug") or generate_unique_slug(Category, data["name"])
        db.session.add(category)
        db.session.commit()
        log_action(current_user, "category.create", "Category", category.id, {"name": category.name})
        return success_response(category_schema.dump(category), status=201)


class CategoryAdminDetailResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self, category_id):
        category = Category.query.get(category_id)
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")
        dumped = category_schema.dump(category)
        dumped["usageCount"] = category_usage_counts([category.id]).get(category.id, 0)
        return success_response(dumped)

    @permission_required("taxonomy.manage")
    def put(self, category_id):
        category = Category.query.get(category_id)
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")

        data = CategoryUpdateSchema().load(request.get_json(silent=True) or {})
        if "name" in data:
            _reject_duplicate_name(Category, data["name"], exclude_id=category.id)
            category.name = data["name"]
        _apply_slug(Category, category, data, category.name)
        for field in ("description", "status", "sort_order"):
            if field in data:
                setattr(category, field, data[field])

        db.session.commit()
        log_action(current_user, "category.update", "Category", category.id, data)
        return success_response(category_schema.dump(category))

    @permission_required("taxonomy.manage")
    def delete(self, category_id):
        category = Category.query.get(category_id)
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")

        usage = category_usage_counts([category.id]).get(category.id, 0)
        if usage > 0:
            raise ApiError(
                f"This category is used by {usage} article(s) and can't be deleted. "
                "Archive it instead, or reassign those articles to a different category first.",
                409,
                code="reference_conflict",
            )

        db.session.delete(category)
        db.session.commit()
        log_action(current_user, "category.delete", "Category", category_id, {"name": category.name})
        return "", 204


class CategoryAdminStatusResource(Resource):
    @permission_required("taxonomy.manage")
    def put(self, category_id):
        category = Category.query.get(category_id)
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")
        data = TaxonomyStatusUpdateSchema().load(request.get_json(silent=True) or {})
        category.status = data["status"]
        db.session.commit()
        log_action(current_user, "category.status_change", "Category", category.id, {"status": category.status})
        return success_response(category_schema.dump(category))


class SeriesAdminListResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self):
        query = Series.query
        if request.args.get("status"):
            query = query.filter(Series.status == request.args["status"])
        query = apply_search(query, Series, request.args, ["name", "subtitle", "description"], param="q")
        query = query.order_by(Series.sort_order, Series.name)
        result = paginate(query, None)
        items = series_schema.dump(result["items"], many=True)
        usage = series_usage_counts([s.id for s in result["items"]])
        return success_response(_with_usage(items, usage), meta=result["meta"])

    @permission_required("taxonomy.manage")
    def post(self):
        data = SeriesInputSchema().load(request.get_json(silent=True) or {})
        _reject_duplicate_name(Series, data["name"])

        series = Series(
            name=data["name"],
            subtitle=data.get("subtitle"),
            description=data.get("description"),
            cover_media_id=data.get("cover_media_id"),
            sponsor_organization_id=data.get("sponsor_organization_id"),
            seo=data.get("seo"),
            featured=data.get("featured", False),
            status=data.get("status", "draft"),
            sort_order=data.get("sort_order", 0),
        )
        series.slug = data.get("slug") or generate_unique_slug(Series, data["name"])
        db.session.add(series)
        db.session.commit()
        log_action(current_user, "series.create", "Series", series.id, {"name": series.name})
        return success_response(series_schema.dump(series), status=201)


class SeriesAdminDetailResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self, series_id):
        series = Series.query.get(series_id)
        if series is None:
            raise ApiError("Series not found.", 404, code="not_found")
        dumped = series_schema.dump(series)
        dumped["usageCount"] = series_usage_counts([series.id]).get(series.id, 0)
        return success_response(dumped)

    @permission_required("taxonomy.manage")
    def put(self, series_id):
        series = Series.query.get(series_id)
        if series is None:
            raise ApiError("Series not found.", 404, code="not_found")

        data = SeriesUpdateSchema().load(request.get_json(silent=True) or {})
        if "name" in data:
            _reject_duplicate_name(Series, data["name"], exclude_id=series.id)
            series.name = data["name"]
        _apply_slug(Series, series, data, series.name)
        for field in (
            "subtitle",
            "description",
            "cover_media_id",
            "sponsor_organization_id",
            "seo",
            "featured",
            "status",
            "sort_order",
        ):
            if field in data:
                setattr(series, field, data[field])

        db.session.commit()
        log_action(current_user, "series.update", "Series", series.id, data)
        return success_response(series_schema.dump(series))

    @permission_required("taxonomy.manage")
    def delete(self, series_id):
        series = Series.query.get(series_id)
        if series is None:
            raise ApiError("Series not found.", 404, code="not_found")

        usage = series_usage_counts([series.id]).get(series.id, 0)
        if usage > 0:
            raise ApiError(
                f"This series is used by {usage} item(s) and can't be deleted. "
                "Archive it instead, or reassign those items first.",
                409,
                code="reference_conflict",
            )

        db.session.delete(series)
        db.session.commit()
        log_action(current_user, "series.delete", "Series", series_id, {"name": series.name})
        return "", 204


class SeriesAdminStatusResource(Resource):
    @permission_required("taxonomy.manage")
    def put(self, series_id):
        series = Series.query.get(series_id)
        if series is None:
            raise ApiError("Series not found.", 404, code="not_found")
        data = TaxonomyStatusUpdateSchema().load(request.get_json(silent=True) or {})
        series.status = data["status"]
        db.session.commit()
        log_action(current_user, "series.status_change", "Series", series.id, {"status": series.status})
        return success_response(series_schema.dump(series))


class TagAdminListResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self):
        query = Tag.query
        if request.args.get("status"):
            query = query.filter(Tag.status == request.args["status"])
        query = apply_search(query, Tag, request.args, ["name"], param="q")
        query = query.order_by(Tag.name)
        result = paginate(query, None)
        items = tag_schema.dump(result["items"], many=True)
        usage = tag_usage_counts([t.id for t in result["items"]])
        return success_response(_with_usage(items, usage), meta=result["meta"])

    @permission_required("taxonomy.manage")
    def post(self):
        data = TagInputSchema().load(request.get_json(silent=True) or {})
        _reject_duplicate_name(Tag, data["name"])

        tag = Tag(name=data["name"], status=data.get("status", "published"))
        tag.slug = data.get("slug") or generate_unique_slug(Tag, data["name"])
        db.session.add(tag)
        db.session.commit()
        log_action(current_user, "tag.create", "Tag", tag.id, {"name": tag.name})
        return success_response(tag_schema.dump(tag), status=201)


class TagAdminDetailResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self, tag_id):
        tag = Tag.query.get(tag_id)
        if tag is None:
            raise ApiError("Tag not found.", 404, code="not_found")
        dumped = tag_schema.dump(tag)
        dumped["usageCount"] = tag_usage_counts([tag.id]).get(tag.id, 0)
        return success_response(dumped)

    @permission_required("taxonomy.manage")
    def put(self, tag_id):
        tag = Tag.query.get(tag_id)
        if tag is None:
            raise ApiError("Tag not found.", 404, code="not_found")

        data = TagUpdateSchema().load(request.get_json(silent=True) or {})
        if "name" in data:
            _reject_duplicate_name(Tag, data["name"], exclude_id=tag.id)
            tag.name = data["name"]
        _apply_slug(Tag, tag, data, tag.name)
        if "status" in data:
            tag.status = data["status"]

        db.session.commit()
        log_action(current_user, "tag.update", "Tag", tag.id, data)
        return success_response(tag_schema.dump(tag))

    @permission_required("taxonomy.manage")
    def delete(self, tag_id):
        tag = Tag.query.get(tag_id)
        if tag is None:
            raise ApiError("Tag not found.", 404, code="not_found")

        usage = tag_usage_counts([tag.id]).get(tag.id, 0)
        if usage > 0:
            raise ApiError(
                f"This tag is used by {usage} item(s) and can't be deleted. "
                "Merge it into another tag instead, or reassign those items first.",
                409,
                code="reference_conflict",
            )

        db.session.delete(tag)
        db.session.commit()
        log_action(current_user, "tag.delete", "Tag", tag_id, {"name": tag.name})
        return "", 204


class TagAdminMergeResource(Resource):
    """Moves every Article/Resource relationship off the source tag onto
    the destination tag, then deletes the source. Safe and transactional
    (see app/services/taxonomy.merge_tags) — the only bulk-editing
    operation this CMS offers for taxonomy.
    """

    @permission_required("taxonomy.manage")
    def post(self):
        data = TagMergeSchema().load(request.get_json(silent=True) or {})
        from_tag = Tag.query.get(data["from_tag_id"])
        to_tag = Tag.query.get(data["to_tag_id"])
        if from_tag is None or to_tag is None:
            raise ApiError("One or both tags were not found.", 404, code="not_found")

        merge_tags(from_tag, to_tag)
        db.session.commit()
        log_action(
            current_user,
            "tag.merge",
            "Tag",
            to_tag.id,
            {"fromTagId": data["from_tag_id"], "fromTagName": from_tag.name, "toTagId": to_tag.id},
        )
        return success_response(tag_schema.dump(to_tag))


api.add_resource(TopicAdminListResource, "/topics")
api.add_resource(TopicAdminDetailResource, "/topics/<int:topic_id>")
api.add_resource(TopicAdminStatusResource, "/topics/<int:topic_id>/status")

api.add_resource(CategoryAdminListResource, "/categories")
api.add_resource(CategoryAdminDetailResource, "/categories/<int:category_id>")
api.add_resource(CategoryAdminStatusResource, "/categories/<int:category_id>/status")

api.add_resource(SeriesAdminListResource, "/series")
api.add_resource(SeriesAdminDetailResource, "/series/<int:series_id>")
api.add_resource(SeriesAdminStatusResource, "/series/<int:series_id>/status")

api.add_resource(TagAdminListResource, "/tags")
api.add_resource(TagAdminMergeResource, "/tags/merge")
api.add_resource(TagAdminDetailResource, "/tags/<int:tag_id>")
