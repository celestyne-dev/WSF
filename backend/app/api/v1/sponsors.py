from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.audit import AuditLog
from app.models.analytics import AnalyticsEvent
from app.models.commerce import PartnershipInquiry, Sponsor, SponsorPlacement, SPONSOR_PLACEMENT_KEYS
from app.models.opportunity import Job
from app.models.people import Organization
from app.schemas.commerce import (
    SponsorAdminUpdateSchema,
    SponsorInputSchema,
    SponsorPlacementInputSchema,
    SponsorPlacementSchema,
    SponsorSchema,
    SponsorStatusInputSchema,
)
from app.schemas.media import MediaSchema
from app.services.audit import log_action
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

sponsors_bp = Blueprint("sponsors", __name__)
api = Api(sponsors_bp)

sponsor_schema = SponsorSchema()
placement_schema = SponsorPlacementSchema()


def _resolve_organization(slug):
    organization = Organization.query.filter_by(slug=slug).first()
    if organization is None:
        raise ApiError(f'Organization "{slug}" not found.', 404, code="not_found")
    return organization


def _resolve_partnership(partnership_id):
    if not partnership_id:
        return None
    partnership = db.session.get(PartnershipInquiry, partnership_id)
    if partnership is None:
        raise ApiError("Linked partnership not found.", 404, code="not_found")
    return partnership


def _get_sponsor_or_404(sponsor_id):
    sponsor = db.session.get(Sponsor, sponsor_id)
    if sponsor is None:
        raise ApiError("Sponsor not found.", 404, code="not_found")
    return sponsor


def _build_query():
    query = Sponsor.query.order_by(Sponsor.updated_at.desc())
    query = apply_equality_filters(query, Sponsor, request.args, ["status", "sponsorship_type"])
    query = apply_search(query, Sponsor, request.args, ["campaign_name", "internal_reference"])

    organization_slug = request.args.get("organization")
    if organization_slug:
        query = query.join(Organization).filter(Organization.slug == organization_slug)

    placement = request.args.get("placement")
    if placement:
        query = query.join(SponsorPlacement).filter(SponsorPlacement.placement_key == placement)

    availability = request.args.get("availability")  # "active" | "expired"
    today = date.today()
    if availability == "active":
        query = query.filter(db.or_(Sponsor.ends_at.is_(None), Sponsor.ends_at >= today))
    elif availability == "expired":
        query = query.filter(Sponsor.ends_at.isnot(None), Sponsor.ends_at < today)

    date_from = request.args.get("date_from")
    if date_from:
        query = query.filter(db.or_(Sponsor.ends_at.is_(None), Sponsor.ends_at >= date_from))
    date_to = request.args.get("date_to")
    if date_to:
        query = query.filter(db.or_(Sponsor.starts_at.is_(None), Sponsor.starts_at <= date_to))

    return query.distinct()


def _apply_fields(sponsor, data):
    """Applies every SponsorInputSchema/SponsorAdminUpdateSchema field
    except organization/partnership (resolved separately) and status
    (dedicated action only).
    """
    for field in (
        "campaign_name", "internal_reference", "public_name_override", "public_description",
        "sponsorship_type", "starts_at", "ends_at", "logo_media_id", "creative_media_id",
        "sponsor_url", "cta_label", "disclosure_label", "public_visible", "is_exclusive",
        "exclusivity_notes", "tier", "estimated_value", "currency", "commercial_notes", "internal_notes",
    ):
        if field in data:
            setattr(sponsor, field, data[field])

    if "organization_slug" in data and data["organization_slug"]:
        sponsor.organization = _resolve_organization(data["organization_slug"])
    if "partnership_id" in data:
        sponsor.partnership = _resolve_partnership(data["partnership_id"])


class SponsorListResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        result = paginate(_build_query(), sponsor_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("partnerships.manage")
    def post(self):
        data = SponsorInputSchema().load(request.get_json(silent=True) or {})
        organization = _resolve_organization(data.pop("organization_slug"))
        partnership = _resolve_partnership(data.pop("partnership_id", None))
        sponsor = Sponsor(organization=organization, partnership=partnership, **data)
        db.session.add(sponsor)
        db.session.commit()
        log_action(current_user, "sponsor.create", "Sponsor", sponsor.id)
        return success_response(sponsor_schema.dump(sponsor), status=201)


class SponsorDetailResource(Resource):
    @permission_required("partnerships.manage")
    def get(self, sponsor_id):
        return success_response(sponsor_schema.dump(_get_sponsor_or_404(sponsor_id)))

    @permission_required("partnerships.manage")
    def patch(self, sponsor_id):
        sponsor = _get_sponsor_or_404(sponsor_id)
        data = SponsorAdminUpdateSchema().load(request.get_json(silent=True) or {})
        _apply_fields(sponsor, data)
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            raise ApiError("Couldn't save — check that the end date isn't before the start date.", 422, code="validation_error") from exc
        log_action(current_user, "sponsor.update", "Sponsor", sponsor.id)
        return success_response(sponsor_schema.dump(sponsor))

    @permission_required("partnerships.manage")
    def delete(self, sponsor_id):
        sponsor = _get_sponsor_or_404(sponsor_id)
        if sponsor.status != "draft":
            raise ApiError(
                "Only Draft sponsors can be deleted. Archive established sponsors instead.",
                409, code="delete_restricted",
            )
        referenced = (
            Job.query.filter_by(sponsor_id=sponsor.id).count()
            or Article.query.filter_by(sponsor_id=sponsor.id).count()
        )
        if referenced:
            raise ApiError(
                "This sponsor is referenced by other content and can't be deleted. Archive it instead.",
                409, code="delete_restricted",
            )
        db.session.delete(sponsor)
        db.session.commit()
        log_action(current_user, "sponsor.delete", "Sponsor", sponsor_id)
        return success_response(None, status=204)


class SponsorStatusResource(Resource):
    @permission_required("partnerships.manage")
    def patch(self, sponsor_id):
        sponsor = _get_sponsor_or_404(sponsor_id)
        data = SponsorStatusInputSchema().load(request.get_json(silent=True) or {})
        previous_status = sponsor.status
        sponsor.status = data["status"]
        db.session.commit()
        log_action(
            current_user, "sponsor.status_change", "Sponsor", sponsor.id,
            changes={"from": previous_status, "to": sponsor.status},
        )
        return success_response(sponsor_schema.dump(sponsor))


class SponsorPlacementListResource(Resource):
    @permission_required("partnerships.manage")
    def post(self, sponsor_id):
        sponsor = _get_sponsor_or_404(sponsor_id)
        data = SponsorPlacementInputSchema().load(request.get_json(silent=True) or {})
        placement = SponsorPlacement(sponsor=sponsor, **data)
        db.session.add(placement)
        db.session.commit()
        log_action(
            current_user, "sponsor.placement_add", "Sponsor", sponsor.id,
            changes={"placementKey": placement.placement_key},
        )
        return success_response(sponsor_schema.dump(sponsor), status=201)


class SponsorPlacementDetailResource(Resource):
    @permission_required("partnerships.manage")
    def patch(self, sponsor_id, placement_id):
        sponsor = _get_sponsor_or_404(sponsor_id)
        placement = SponsorPlacement.query.filter_by(id=placement_id, sponsor_id=sponsor.id).first()
        if placement is None:
            raise ApiError("Placement not found.", 404, code="not_found")
        data = SponsorPlacementInputSchema(partial=True).load(request.get_json(silent=True) or {})
        for field, value in data.items():
            setattr(placement, field, value)
        db.session.commit()
        log_action(current_user, "sponsor.placement_update", "Sponsor", sponsor.id, changes={"placementId": placement.id})
        return success_response(sponsor_schema.dump(sponsor))

    @permission_required("partnerships.manage")
    def delete(self, sponsor_id, placement_id):
        sponsor = _get_sponsor_or_404(sponsor_id)
        placement = SponsorPlacement.query.filter_by(id=placement_id, sponsor_id=sponsor.id).first()
        if placement is None:
            raise ApiError("Placement not found.", 404, code="not_found")
        placement_key = placement.placement_key
        db.session.delete(placement)
        db.session.commit()
        log_action(
            current_user, "sponsor.placement_remove", "Sponsor", sponsor.id, changes={"placementKey": placement_key}
        )
        return success_response(sponsor_schema.dump(sponsor))


class SponsorHistoryResource(Resource):
    @permission_required("partnerships.manage")
    def get(self, sponsor_id):
        _get_sponsor_or_404(sponsor_id)
        entries = (
            AuditLog.query.filter_by(entity_type="Sponsor", entity_id=str(sponsor_id))
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


class SponsorAnalyticsResource(Resource):
    """Real counts only — no fabricated metrics. CTR is omitted (not
    zeroed) when there are no impressions to divide by.
    """

    @permission_required("partnerships.manage")
    def get(self, sponsor_id):
        _get_sponsor_or_404(sponsor_id)
        rows = (
            db.session.query(AnalyticsEvent.event_name, db.func.count(AnalyticsEvent.id))
            .filter(AnalyticsEvent.entity_type == "Sponsor", AnalyticsEvent.entity_id == str(sponsor_id))
            .group_by(AnalyticsEvent.event_name)
            .all()
        )
        counts = {name: count for name, count in rows}
        impressions = counts.get("sponsor_impression", 0)
        clicks = counts.get("sponsor_click", 0)
        ctr = round(clicks / impressions * 100, 2) if impressions else None
        return success_response({"impressions": impressions, "clicks": clicks, "clickThroughRate": ctr})


def build_public_sponsor_payload(sponsor, placement):
    logo = sponsor.logo or (sponsor.organization.logo if sponsor.organization else None)
    return {
        "id": sponsor.id,
        "campaignName": sponsor.campaign_name,
        "publicName": sponsor.resolved_public_name,
        "publicDescription": sponsor.public_description,
        "organization": (
            {"slug": sponsor.organization.slug, "name": sponsor.organization.name}
            if sponsor.organization else None
        ),
        "logo": MediaSchema().dump(logo) if logo else None,
        "creative": MediaSchema().dump(sponsor.creative) if sponsor.creative else None,
        "disclosureLabel": sponsor.disclosure_label,
        "sponsorUrl": sponsor.sponsor_url,
        "ctaLabel": sponsor.cta_label,
        "placementKey": placement.placement_key,
        "position": placement.position,
    }


class PublicSponsorPlacementResource(Resource):
    def get(self):
        placement_key = request.args.get("placement")
        if not placement_key or placement_key not in SPONSOR_PLACEMENT_KEYS:
            raise ApiError("A valid placement is required.", 422, code="validation_error")

        today = date.today()
        rows = (
            db.session.query(Sponsor, SponsorPlacement)
            .join(SponsorPlacement, SponsorPlacement.sponsor_id == Sponsor.id)
            .filter(
                SponsorPlacement.placement_key == placement_key,
                SponsorPlacement.active.is_(True),
                Sponsor.status == "active",
                Sponsor.public_visible.is_(True),
                db.or_(Sponsor.starts_at.is_(None), Sponsor.starts_at <= today),
                db.or_(Sponsor.ends_at.is_(None), Sponsor.ends_at >= today),
                db.or_(SponsorPlacement.starts_at.is_(None), SponsorPlacement.starts_at <= today),
                db.or_(SponsorPlacement.ends_at.is_(None), SponsorPlacement.ends_at >= today),
            )
            .order_by(SponsorPlacement.position)
            .all()
        )
        return success_response([build_public_sponsor_payload(sponsor, placement) for sponsor, placement in rows])


api.add_resource(SponsorListResource, "/")
api.add_resource(PublicSponsorPlacementResource, "/public")
api.add_resource(SponsorDetailResource, "/<int:sponsor_id>")
api.add_resource(SponsorStatusResource, "/<int:sponsor_id>/status")
api.add_resource(SponsorPlacementListResource, "/<int:sponsor_id>/placements")
api.add_resource(SponsorPlacementDetailResource, "/<int:sponsor_id>/placements/<int:placement_id>")
api.add_resource(SponsorHistoryResource, "/<int:sponsor_id>/history")
api.add_resource(SponsorAnalyticsResource, "/<int:sponsor_id>/analytics")
