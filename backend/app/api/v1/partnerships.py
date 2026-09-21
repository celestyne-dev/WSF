from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.cms import SiteSetting
from app.models.commerce import PartnershipInquiry, Sponsor
from app.models.people import Organization
from app.schemas.commerce import (
    PartnershipInquiryInputSchema,
    PartnershipInquirySchema,
    PartnershipStatusInputSchema,
    SponsorInputSchema,
    SponsorSchema,
)
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

partnerships_bp = Blueprint("partnerships", __name__)
api = Api(partnerships_bp)

inquiry_schema = PartnershipInquirySchema()
sponsor_schema = SponsorSchema()


class PartnershipInquiryListResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        query = PartnershipInquiry.query.order_by(PartnershipInquiry.submitted_at.desc())
        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)
        result = paginate(query, inquiry_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        data = PartnershipInquiryInputSchema().load(request.get_json(silent=True) or {})
        inquiry = PartnershipInquiry(**data)
        db.session.add(inquiry)
        db.session.commit()
        return success_response(inquiry_schema.dump(inquiry), status=201)


class PartnershipInquiryStatusResource(Resource):
    @permission_required("partnerships.manage")
    def patch(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")

        data = PartnershipStatusInputSchema().load(request.get_json(silent=True) or {})
        inquiry.status = data["status"]
        db.session.commit()
        return success_response(inquiry_schema.dump(inquiry))


class SponsorListResource(Resource):
    def get(self):
        sponsors = Sponsor.query.filter_by(active=True).all()
        return success_response(sponsor_schema.dump(sponsors, many=True))

    @permission_required("partnerships.manage")
    def post(self):
        data = SponsorInputSchema().load(request.get_json(silent=True) or {})
        organization = Organization.query.filter_by(slug=data.pop("organization_slug")).first()
        if organization is None:
            raise ApiError("Organization not found.", 404, code="not_found")

        sponsor = Sponsor(organization=organization, **data)
        db.session.add(sponsor)
        db.session.commit()
        return success_response(sponsor_schema.dump(sponsor), status=201)


class AudienceStatsResource(Resource):
    """CMS-editable LinkedIn/newsletter/website audience numbers for the
    Partnerships page and media kit — stored as a SiteSetting row
    ('audience_stats') and edited via PUT /api/v1/admin/settings, never
    hard-coded into a frontend component.
    """

    def get(self):
        setting = db.session.get(SiteSetting, "audience_stats")
        return success_response(setting.value if setting else {})


api.add_resource(PartnershipInquiryListResource, "/inquiries")
api.add_resource(PartnershipInquiryStatusResource, "/inquiries/<int:inquiry_id>/status")
api.add_resource(SponsorListResource, "/sponsors")
api.add_resource(AudienceStatsResource, "/audience")
