from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.community import Nomination
from app.schemas.community import NominationInputSchema, NominationSchema, ReviewStatusInputSchema
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

nominations_bp = Blueprint("nominations", __name__)
api = Api(nominations_bp)

nomination_schema = NominationSchema()


class NominationListResource(Resource):
    @permission_required("nominations.manage")
    def get(self):
        query = Nomination.query.order_by(Nomination.submitted_at.desc())
        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)
        result = paginate(query, nomination_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        data = NominationInputSchema().load(request.get_json(silent=True) or {})
        nomination = Nomination(**data)
        db.session.add(nomination)
        db.session.commit()
        return success_response(nomination_schema.dump(nomination), status=201)


class NominationStatusResource(Resource):
    @permission_required("nominations.manage")
    def patch(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")

        data = ReviewStatusInputSchema().load(request.get_json(silent=True) or {})
        nomination.status = data["status"]
        db.session.commit()
        return success_response(nomination_schema.dump(nomination))


api.add_resource(NominationListResource, "")
api.add_resource(NominationStatusResource, "/<int:nomination_id>/status")
