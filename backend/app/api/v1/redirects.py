from flask import Blueprint
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.models.article import Redirect
from app.utils.pagination import paginate
from app.utils.responses import success_response

redirects_bp = Blueprint("redirects", __name__)
api = Api(redirects_bp)


class RedirectSchemaLite:
    """Deliberately not a full Marshmallow schema — Redirect has no
    relations worth nesting, just four scalar columns.
    """

    @staticmethod
    def dump(redirect):
        return {
            "id": redirect.id,
            "fromSlug": redirect.from_slug,
            "toSlug": redirect.to_slug,
            "articleId": redirect.article_id,
            "createdAt": redirect.created_at.isoformat(),
        }


class RedirectListResource(Resource):
    @permission_required("articles.manage")
    def get(self):
        query = Redirect.query.order_by(Redirect.created_at.desc())
        result = paginate(query, None)
        items = [RedirectSchemaLite.dump(r) for r in result["items"]]
        return success_response(items, meta=result["meta"])


api.add_resource(RedirectListResource, "")
