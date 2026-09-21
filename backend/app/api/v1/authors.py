from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.people import Author
from app.schemas.article import article_summary_schema
from app.schemas.people import AuthorInputSchema, AuthorSchema
from app.services.slugs import generate_unique_slug
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

authors_bp = Blueprint("authors", __name__)
api = Api(authors_bp)

author_schema = AuthorSchema()


class AuthorListResource(Resource):
    def get(self):
        authors = Author.query.order_by(Author.name).all()
        return success_response(author_schema.dump(authors, many=True))

    @permission_required("people.manage")
    def post(self):
        data = AuthorInputSchema().load(request.get_json(silent=True) or {})
        author = Author(**{k: v for k, v in data.items() if k != "slug"})
        author.slug = data.get("slug") or generate_unique_slug(Author, data["name"])
        db.session.add(author)
        db.session.commit()
        return success_response(author_schema.dump(author), status=201)


class AuthorDetailResource(Resource):
    def get(self, slug):
        author = Author.query.filter_by(slug=slug).first()
        if author is None:
            raise ApiError("Author not found.", 404, code="not_found")
        query = Article.query.filter_by(author_id=author.id, status="published").order_by(
            Article.publish_date.desc()
        )
        result = paginate(query, None)
        articles = article_summary_schema(many=True).dump(result["items"])
        return success_response(
            {"author": author_schema.dump(author), "articles": articles}, meta=result["meta"]
        )


api.add_resource(AuthorListResource, "")
api.add_resource(AuthorDetailResource, "/<string:slug>")
