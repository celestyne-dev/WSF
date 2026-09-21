from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.taxonomy import Category, Series, Topic
from app.schemas.article import article_summary_schema
from app.schemas.taxonomy import (
    CategoryInputSchema,
    CategorySchema,
    SeriesInputSchema,
    SeriesSchema,
    TopicInputSchema,
    TopicSchema,
)
from app.services.slugs import generate_unique_slug
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

topics_bp = Blueprint("topics", __name__)
categories_bp = Blueprint("categories", __name__)
series_bp = Blueprint("series", __name__)

topics_api = Api(topics_bp)
categories_api = Api(categories_bp)
series_api = Api(series_bp)

topic_schema = TopicSchema()
category_schema = CategorySchema()
series_schema = SeriesSchema()


def _articles_for(query):
    query = query.filter(Article.status == "published").order_by(Article.publish_date.desc())
    return paginate(query, None)


class TopicListResource(Resource):
    def get(self):
        topics = Topic.query.order_by(Topic.sort_order, Topic.name).all()
        return success_response(topic_schema.dump(topics, many=True))

    @permission_required("taxonomy.manage")
    def post(self):
        data = TopicInputSchema().load(request.get_json(silent=True) or {})
        topic = Topic(
            name=data["name"],
            description=data.get("description"),
            sort_order=data.get("sort_order", 0),
        )
        topic.slug = data.get("slug") or generate_unique_slug(Topic, data["name"])
        db.session.add(topic)
        db.session.commit()
        return success_response(topic_schema.dump(topic), status=201)


class TopicDetailResource(Resource):
    def get(self, slug):
        topic = Topic.query.filter_by(slug=slug).first()
        if topic is None:
            raise ApiError("Topic not found.", 404, code="not_found")
        result = _articles_for(Article.query.filter(Article.topics.any(id=topic.id)))
        articles = article_summary_schema(many=True).dump(result["items"])
        return success_response({"topic": topic_schema.dump(topic), "articles": articles}, meta=result["meta"])


class CategoryListResource(Resource):
    def get(self):
        categories = Category.query.order_by(Category.name).all()
        return success_response(category_schema.dump(categories, many=True))

    @permission_required("taxonomy.manage")
    def post(self):
        data = CategoryInputSchema().load(request.get_json(silent=True) or {})
        category = Category(name=data["name"], description=data.get("description"))
        category.slug = data.get("slug") or generate_unique_slug(Category, data["name"])
        db.session.add(category)
        db.session.commit()
        return success_response(category_schema.dump(category), status=201)


class CategoryDetailResource(Resource):
    def get(self, slug):
        category = Category.query.filter_by(slug=slug).first()
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")
        result = _articles_for(Article.query.filter_by(category_id=category.id))
        articles = article_summary_schema(many=True).dump(result["items"])
        return success_response(
            {"category": category_schema.dump(category), "articles": articles}, meta=result["meta"]
        )


class SeriesListResource(Resource):
    def get(self):
        items = Series.query.order_by(Series.name).all()
        return success_response(series_schema.dump(items, many=True))

    @permission_required("taxonomy.manage")
    def post(self):
        data = SeriesInputSchema().load(request.get_json(silent=True) or {})
        item = Series(
            name=data["name"],
            description=data.get("description"),
            cover_media_id=data.get("cover_media_id"),
            sponsor_organization_id=data.get("sponsor_organization_id"),
            featured=data.get("featured", False),
        )
        item.slug = data.get("slug") or generate_unique_slug(Series, data["name"])
        db.session.add(item)
        db.session.commit()
        return success_response(series_schema.dump(item), status=201)


class SeriesDetailResource(Resource):
    def get(self, slug):
        item = Series.query.filter_by(slug=slug).first()
        if item is None:
            raise ApiError("Series not found.", 404, code="not_found")
        result = _articles_for(Article.query.filter_by(series_id=item.id))
        articles = article_summary_schema(many=True).dump(result["items"])
        return success_response({"series": series_schema.dump(item), "articles": articles}, meta=result["meta"])


topics_api.add_resource(TopicListResource, "")
topics_api.add_resource(TopicDetailResource, "/<string:slug>")

categories_api.add_resource(CategoryListResource, "")
categories_api.add_resource(CategoryDetailResource, "/<string:slug>")

series_api.add_resource(SeriesListResource, "")
series_api.add_resource(SeriesDetailResource, "/<string:slug>")
