from flask import Blueprint, request
from flask_restful import Api, Resource
from marshmallow import EXCLUDE, Schema, fields, validate

from app.services.search import (
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    SEARCHABLE_TYPES,
    SearchValidationError,
    normalize_query,
    search,
    validate_query,
)
from app.utils.responses import ApiError, success_response

search_bp = Blueprint("search", __name__)
api = Api(search_bp)


class SearchQuerySchema(Schema):
    """GET /api/v1/search?q=&type=&page=&per_page=&topic=&country=&region=&remote=
    `type` is validated against the controlled type vocabulary (a typo
    here is a real mistake worth a clear error, unlike `country`/`topic`,
    which are open, data-driven values that just naturally match nothing
    when wrong).
    """

    type = fields.String(required=False, load_default="all", validate=validate.OneOf(("all",) + SEARCHABLE_TYPES))
    page = fields.Integer(required=False, load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(
        required=False, load_default=DEFAULT_PER_PAGE, validate=validate.Range(min=1, max=MAX_PER_PAGE)
    )
    topic = fields.String(required=False, allow_none=True)
    country = fields.String(required=False, allow_none=True)
    region = fields.String(required=False, allow_none=True)
    remote = fields.Boolean(required=False, allow_none=True)

    class Meta:
        unknown = EXCLUDE


class SearchResource(Resource):
    """The single public search endpoint — see app/services/search.py for
    every eligibility/relevance/field decision. This route only validates
    input and shapes the response envelope.
    """

    def get(self):
        params = SearchQuerySchema().load(request.args.to_dict())
        query = normalize_query(request.args.get("q"))

        try:
            validate_query(query)
        except SearchValidationError as exc:
            raise ApiError(exc.message, 422, code=exc.code) from exc

        filters = {
            "topic": params.get("topic"),
            "country": params.get("country"),
            "region": params.get("region"),
            "remote": params.get("remote"),
        }
        result = search(
            query, result_type=params["type"], filters=filters, page=params["page"], per_page=params["per_page"]
        )

        # Pagination is nested inside `data` (not passed as the top-level
        # `meta` kwarg) deliberately: the shared axios response interceptor
        # (frontend/src/api/client.js) only preserves `meta` when `data` is
        # an array — for an object response like this one, a top-level
        # `meta` block would be silently dropped.
        return success_response(
            {
                "query": query,
                "type": params["type"],
                "results": result["results"],
                "pagination": {
                    "page": result["page"],
                    "perPage": result["per_page"],
                    "total": result["total"],
                    "totalPages": result["total_pages"],
                },
            }
        )


api.add_resource(SearchResource, "")
