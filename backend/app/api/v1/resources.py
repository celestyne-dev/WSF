from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.people import Author
from app.models.resource import Resource as ResourceModel
from app.models.taxonomy import Topic
from app.schemas.resource import ResourceInputSchema, ResourceSchema
from app.services.slugs import generate_unique_slug
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

resources_bp = Blueprint("resources", __name__)
api = Api(resources_bp)

resource_schema = ResourceSchema()


class ResourceListResource(Resource):
    def get(self):
        query = ResourceModel.query.filter_by(status="published").order_by(ResourceModel.featured.desc())
        if request.args.get("topic"):
            query = query.join(Topic).filter(Topic.slug == request.args["topic"])
        query = apply_equality_filters(query, ResourceModel, request.args, ["type", "is_premium"])
        query = apply_search(query, ResourceModel, request.args, ["name", "description"])
        result = paginate(query, resource_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("resources.manage")
    def post(self):
        data = ResourceInputSchema().load(request.get_json(silent=True) or {})

        topic = None
        if data.get("topic_slug"):
            topic = Topic.query.filter_by(slug=data["topic_slug"]).first()
            if topic is None:
                raise ApiError(f"Topic \"{data['topic_slug']}\" not found.", 404, code="not_found")

        author = None
        if data.get("author_slug"):
            author = Author.query.filter_by(slug=data["author_slug"]).first()
            if author is None:
                raise ApiError(f"Author \"{data['author_slug']}\" not found.", 404, code="not_found")

        fields = {k: v for k, v in data.items() if k not in ("slug", "topic_slug", "author_slug")}
        item = ResourceModel(**fields, topic=topic, author=author)
        item.slug = data.get("slug") or generate_unique_slug(ResourceModel, data["name"])
        db.session.add(item)
        db.session.commit()
        return success_response(resource_schema.dump(item), status=201)


class ResourceDetailResource(Resource):
    def get(self, slug):
        item = ResourceModel.query.filter_by(slug=slug).first()
        if item is None:
            raise ApiError("Resource not found.", 404, code="not_found")
        return success_response(resource_schema.dump(item))


api.add_resource(ResourceListResource, "")
api.add_resource(ResourceDetailResource, "/<string:slug>")
