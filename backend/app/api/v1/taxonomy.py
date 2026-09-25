from flask import Blueprint

from flask_restful import Api, Resource

from app.models.article import Article
from app.models.taxonomy import Category, Series, Topic
from app.schemas.article import article_summary_schema
from app.schemas.taxonomy import CategorySchema, SeriesSchema, TopicSchema
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

# Public, unauthenticated, published-only — the read side of Topic/
# Category/Series taxonomy. All create/update/delete/status/merge
# operations live in app/api/v1/admin_taxonomy.py under taxonomy.manage;
# this file's response contract (flat arrays, {topic/category/series,
# articles} detail shape) is unchanged so TopicsIndexPage/TopicDetailPage/
# SeriesIndexPage/SeriesDetailPage and every other editor's selector
# (Article/Person/Resource/...) that calls fetchTopics/fetchCategories/
# fetchSeries need no frontend changes.

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
        topics = Topic.query.filter_by(status="published").order_by(Topic.sort_order, Topic.name).all()
        return success_response(topic_schema.dump(topics, many=True))


class TopicDetailResource(Resource):
    def get(self, slug):
        topic = Topic.query.filter_by(slug=slug, status="published").first()
        if topic is None:
            raise ApiError("Topic not found.", 404, code="not_found")
        result = _articles_for(Article.query.filter(Article.topics.any(id=topic.id)))
        articles = article_summary_schema(many=True).dump(result["items"])
        return success_response({"topic": topic_schema.dump(topic), "articles": articles}, meta=result["meta"])


class CategoryListResource(Resource):
    def get(self):
        categories = Category.query.filter_by(status="published").order_by(Category.sort_order, Category.name).all()
        return success_response(category_schema.dump(categories, many=True))


class CategoryDetailResource(Resource):
    def get(self, slug):
        category = Category.query.filter_by(slug=slug, status="published").first()
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")
        result = _articles_for(Article.query.filter_by(category_id=category.id))
        articles = article_summary_schema(many=True).dump(result["items"])
        return success_response(
            {"category": category_schema.dump(category), "articles": articles}, meta=result["meta"]
        )


class SeriesListResource(Resource):
    def get(self):
        items = Series.query.filter_by(status="published").order_by(Series.sort_order, Series.name).all()
        return success_response(series_schema.dump(items, many=True))


class SeriesDetailResource(Resource):
    def get(self, slug):
        item = Series.query.filter_by(slug=slug, status="published").first()
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
