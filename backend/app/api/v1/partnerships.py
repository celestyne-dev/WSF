import csv
import io
from datetime import date, datetime, timezone

from flask import Blueprint, Response, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.audit import AuditLog
from app.models.cms import SiteSetting
from app.models.commerce import PartnershipInquiry, PartnershipNote, Sponsor
from app.models.people import Organization
from app.models.user import User
from app.schemas.commerce import (
    PartnershipAdminUpdateSchema,
    PartnershipAssignInputSchema,
    PartnershipInquiryConfirmationSchema,
    PartnershipInquiryInputSchema,
    PartnershipInquirySchema,
    PartnershipNoteInputSchema,
    PartnershipOrganizationLinkInputSchema,
    PartnershipStatusInputSchema,
    SponsorInputSchema,
    SponsorSchema,
)
from app.services.audit import log_action
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

partnerships_bp = Blueprint("partnerships", __name__)
api = Api(partnerships_bp)

inquiry_schema = PartnershipInquirySchema()
confirmation_schema = PartnershipInquiryConfirmationSchema()
sponsor_schema = SponsorSchema()

_EXPORT_COLUMNS = (
    "company", "contact_name", "work_email", "partnership_type", "status", "country",
    "created_date", "assigned_owner", "estimated_value", "currency",
)


def _require_manage():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    if not current_user.has_permission("partnerships.manage"):
        raise ApiError("You do not have permission to manage partnerships.", 403, code="forbidden")
    return current_user


def _resolve_organization(slug):
    if not slug:
        return None
    organization = Organization.query.filter_by(slug=slug).first()
    if organization is None:
        raise ApiError(f'Organization "{slug}" not found.', 404, code="not_found")
    return organization


def _resolve_assignee(user_id):
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        raise ApiError("Assignee not found.", 404, code="not_found")
    return user


def _build_query():
    query = PartnershipInquiry.query.order_by(PartnershipInquiry.submitted_at.desc())
    query = apply_equality_filters(query, PartnershipInquiry, request.args, ["status", "partnership_type", "assigned_to_id"])
    query = apply_search(query, PartnershipInquiry, request.args, ["company", "contact_name", "email", "subject"])
    query = apply_country_or_region_filter(query, PartnershipInquiry, request.args)

    organization_slug = request.args.get("organization")
    if organization_slug:
        query = query.join(Organization).filter(Organization.slug == organization_slug)

    date_from = request.args.get("date_from")
    if date_from:
        query = query.filter(PartnershipInquiry.submitted_at >= date_from)
    date_to = request.args.get("date_to")
    if date_to:
        query = query.filter(PartnershipInquiry.submitted_at <= date_to)

    return query


class PartnershipInquiryListResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        result = paginate(_build_query(), inquiry_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        data = PartnershipInquiryInputSchema().load(request.get_json(silent=True) or {})
        inquiry = PartnershipInquiry(**data)
        db.session.add(inquiry)
        db.session.commit()
        return success_response(confirmation_schema.dump(inquiry), status=201)


class PartnershipInquiryDetailResource(Resource):
    @permission_required("partnerships.manage")
    def get(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")
        return success_response(inquiry_schema.dump(inquiry))

    @permission_required("partnerships.manage")
    def patch(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")

        data = PartnershipAdminUpdateSchema().load(request.get_json(silent=True) or {})
        for field, value in data.items():
            setattr(inquiry, field, value)
        db.session.commit()
        log_action(current_user, "partnership.update", "PartnershipInquiry", inquiry.id)
        return success_response(inquiry_schema.dump(inquiry))


class PartnershipInquiryStatusResource(Resource):
    @permission_required("partnerships.manage")
    def patch(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")

        data = PartnershipStatusInputSchema().load(request.get_json(silent=True) or {})
        previous_status = inquiry.status
        inquiry.status = data["status"]
        db.session.commit()
        log_action(
            current_user, "partnership.status_change", "PartnershipInquiry", inquiry.id,
            changes={"from": previous_status, "to": inquiry.status},
        )
        return success_response(inquiry_schema.dump(inquiry))


class PartnershipInquiryAssignResource(Resource):
    @permission_required("partnerships.manage")
    def post(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")

        data = PartnershipAssignInputSchema().load(request.get_json(silent=True) or {})
        assignee = _resolve_assignee(data.get("assigned_to_id"))
        inquiry.assigned_to = assignee
        db.session.commit()
        log_action(
            current_user, "partnership.assign", "PartnershipInquiry", inquiry.id,
            changes={"assignedTo": assignee.email if assignee else None},
        )
        return success_response(inquiry_schema.dump(inquiry))


class PartnershipInquiryOrganizationResource(Resource):
    @permission_required("partnerships.manage")
    def post(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")

        data = PartnershipOrganizationLinkInputSchema().load(request.get_json(silent=True) or {})
        organization = _resolve_organization(data.get("organization_slug"))
        inquiry.organization = organization
        db.session.commit()
        log_action(
            current_user, "partnership.organization_link", "PartnershipInquiry", inquiry.id,
            changes={"organization": organization.slug if organization else None},
        )
        return success_response(inquiry_schema.dump(inquiry))


class PartnershipInquiryNoteListResource(Resource):
    @permission_required("partnerships.manage")
    def post(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")

        data = PartnershipNoteInputSchema().load(request.get_json(silent=True) or {})
        note = PartnershipNote(partnership=inquiry, user=current_user, body=data["body"])
        db.session.add(note)
        db.session.commit()
        log_action(current_user, "partnership.note_add", "PartnershipInquiry", inquiry.id)
        return success_response(inquiry_schema.dump(inquiry), status=201)


class PartnershipInquiryArchiveResource(Resource):
    @permission_required("partnerships.manage")
    def post(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")

        previous_status = inquiry.status
        inquiry.status = "archived"
        db.session.commit()
        log_action(
            current_user, "partnership.archive", "PartnershipInquiry", inquiry.id,
            changes={"from": previous_status, "to": "archived"},
        )
        return success_response(inquiry_schema.dump(inquiry))


class PartnershipInquiryHistoryResource(Resource):
    @permission_required("partnerships.manage")
    def get(self, inquiry_id):
        inquiry = db.session.get(PartnershipInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Partnership inquiry not found.", 404, code="not_found")

        entries = (
            AuditLog.query.filter_by(entity_type="PartnershipInquiry", entity_id=str(inquiry.id))
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        return success_response(
            [
                {
                    "id": e.id,
                    "action": e.action,
                    "changes": e.changes,
                    "user": e.user.full_name if e.user else None,
                    "createdAt": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ]
        )


class PartnershipInquiryExportResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        inquiries = _build_query().limit(5000).all()

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(_EXPORT_COLUMNS)
        for i in inquiries:
            writer.writerow(
                [
                    i.company,
                    i.contact_name,
                    i.email,
                    i.partnership_type or "",
                    i.status,
                    i.country.name if i.country else "",
                    i.submitted_at.isoformat() if i.submitted_at else "",
                    i.assigned_to.full_name if i.assigned_to else "",
                    i.estimated_value if i.estimated_value is not None else "",
                    i.currency or "",
                ]
            )

        log_action(
            current_user, "partnership.export", "PartnershipInquiry", None, changes={"count": len(inquiries)}
        )
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=partnership-inquiries-{date.today().isoformat()}.csv"
        return response


class PartnershipOverviewResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        under_review_statuses = ("reviewing", "contacted", "qualified", "proposal", "negotiating")
        return success_response(
            {
                "newInquiries": PartnershipInquiry.query.filter_by(status="new").count(),
                "underReview": PartnershipInquiry.query.filter(
                    PartnershipInquiry.status.in_(under_review_statuses)
                ).count(),
                "active": PartnershipInquiry.query.filter_by(status="active").count(),
                "completed": PartnershipInquiry.query.filter_by(status="completed").count(),
            }
        )


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
api.add_resource(PartnershipInquiryExportResource, "/inquiries/export")
api.add_resource(PartnershipOverviewResource, "/overview")
api.add_resource(PartnershipInquiryDetailResource, "/inquiries/<int:inquiry_id>")
api.add_resource(PartnershipInquiryStatusResource, "/inquiries/<int:inquiry_id>/status")
api.add_resource(PartnershipInquiryAssignResource, "/inquiries/<int:inquiry_id>/assign")
api.add_resource(PartnershipInquiryOrganizationResource, "/inquiries/<int:inquiry_id>/organization")
api.add_resource(PartnershipInquiryNoteListResource, "/inquiries/<int:inquiry_id>/notes")
api.add_resource(PartnershipInquiryArchiveResource, "/inquiries/<int:inquiry_id>/archive")
api.add_resource(PartnershipInquiryHistoryResource, "/inquiries/<int:inquiry_id>/history")
api.add_resource(SponsorListResource, "/sponsors")
api.add_resource(AudienceStatsResource, "/audience")
