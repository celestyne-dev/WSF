from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.audit import AuditLog
from app.models.cms import AdvertiseMetric, AdvertiseOffering, AdvertisePage
from app.schemas.cms import (
    AdvertiseMetricInputSchema,
    AdvertiseMetricSchema,
    AdvertiseMetricUpdateSchema,
    AdvertiseOfferingInputSchema,
    AdvertiseOfferingSchema,
    AdvertiseOfferingUpdateSchema,
    AdvertisePageInputSchema,
    AdvertisePageSchema,
    AdvertisePageStatusInputSchema,
)
from app.schemas.media import MediaSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.audit import log_action
from app.utils.responses import ApiError, success_response

advertise_bp = Blueprint("advertise", __name__)
api = Api(advertise_bp)

page_schema = AdvertisePageSchema()
metric_schema = AdvertiseMetricSchema()
offering_schema = AdvertiseOfferingSchema()


def _get_page():
    page = db.session.get(AdvertisePage, 1)
    if page is None:
        raise ApiError("Advertise page not initialized.", 500, code="not_found")
    return page


def _get_metric_or_404(metric_id):
    metric = db.session.get(AdvertiseMetric, metric_id)
    if metric is None:
        raise ApiError("Metric not found.", 404, code="not_found")
    return metric


def _get_offering_or_404(offering_id):
    offering = db.session.get(AdvertiseOffering, offering_id)
    if offering is None:
        raise ApiError("Offering not found.", 404, code="not_found")
    return offering


class AdvertisePageResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        return success_response(page_schema.dump(_get_page()))

    @permission_required("partnerships.manage")
    def patch(self):
        page = _get_page()
        data = AdvertisePageInputSchema().load(request.get_json(silent=True) or {})
        if "intro_content" in data:
            data["intro_content"] = sanitize_content_blocks(data["intro_content"])
        if "why_content" in data:
            data["why_content"] = sanitize_content_blocks(data["why_content"])
        for field, value in data.items():
            setattr(page, field, value)
        db.session.commit()
        log_action(current_user, "advertise.page_update", "AdvertisePage", page.id)
        return success_response(page_schema.dump(page))


class AdvertisePageStatusResource(Resource):
    @permission_required("partnerships.manage")
    def patch(self):
        page = _get_page()
        data = AdvertisePageStatusInputSchema().load(request.get_json(silent=True) or {})
        previous_status = page.status
        page.status = data["status"]
        db.session.commit()
        log_action(
            current_user, "advertise.page_status_change", "AdvertisePage", page.id,
            changes={"from": previous_status, "to": page.status},
        )
        return success_response(page_schema.dump(page))


class AdvertiseMetricListResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        metrics = AdvertiseMetric.query.order_by(AdvertiseMetric.display_order).all()
        return success_response(metric_schema.dump(metrics, many=True))

    @permission_required("partnerships.manage")
    def post(self):
        data = AdvertiseMetricInputSchema().load(request.get_json(silent=True) or {})
        metric = AdvertiseMetric(**data)
        db.session.add(metric)
        db.session.commit()
        log_action(current_user, "advertise.metric_create", "AdvertiseMetric", metric.id)
        return success_response(metric_schema.dump(metric), status=201)


class AdvertiseMetricDetailResource(Resource):
    @permission_required("partnerships.manage")
    def patch(self, metric_id):
        metric = _get_metric_or_404(metric_id)
        data = AdvertiseMetricUpdateSchema().load(request.get_json(silent=True) or {})
        for field, value in data.items():
            setattr(metric, field, value)
        db.session.commit()
        log_action(current_user, "advertise.metric_update", "AdvertiseMetric", metric.id)
        return success_response(metric_schema.dump(metric))

    @permission_required("partnerships.manage")
    def delete(self, metric_id):
        metric = _get_metric_or_404(metric_id)
        db.session.delete(metric)
        db.session.commit()
        log_action(current_user, "advertise.metric_delete", "AdvertiseMetric", metric_id)
        return success_response(None, status=204)


class AdvertiseOfferingListResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        offerings = AdvertiseOffering.query.order_by(AdvertiseOffering.display_order).all()
        return success_response(offering_schema.dump(offerings, many=True))

    @permission_required("partnerships.manage")
    def post(self):
        data = AdvertiseOfferingInputSchema().load(request.get_json(silent=True) or {})
        offering = AdvertiseOffering(**data)
        db.session.add(offering)
        db.session.commit()
        log_action(current_user, "advertise.offering_create", "AdvertiseOffering", offering.id)
        return success_response(offering_schema.dump(offering), status=201)


class AdvertiseOfferingDetailResource(Resource):
    @permission_required("partnerships.manage")
    def patch(self, offering_id):
        offering = _get_offering_or_404(offering_id)
        data = AdvertiseOfferingUpdateSchema().load(request.get_json(silent=True) or {})
        for field, value in data.items():
            setattr(offering, field, value)
        db.session.commit()
        log_action(current_user, "advertise.offering_update", "AdvertiseOffering", offering.id)
        return success_response(offering_schema.dump(offering))

    @permission_required("partnerships.manage")
    def delete(self, offering_id):
        offering = _get_offering_or_404(offering_id)
        db.session.delete(offering)
        db.session.commit()
        log_action(current_user, "advertise.offering_delete", "AdvertiseOffering", offering_id)
        return success_response(None, status=204)


class AdvertiseHistoryResource(Resource):
    @permission_required("partnerships.manage")
    def get(self):
        entries = (
            AuditLog.query.filter(
                AuditLog.entity_type.in_(("AdvertisePage", "AdvertiseMetric", "AdvertiseOffering"))
            )
            .order_by(AuditLog.created_at.desc())
            .limit(200)
            .all()
        )
        return success_response(
            [
                {
                    "id": e.id,
                    "action": e.action,
                    "entityType": e.entity_type,
                    "changes": e.changes,
                    "user": e.user.full_name if e.user else None,
                    "createdAt": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ]
        )


def build_public_advertise_page(page):
    return {
        "hero": {
            "heading": page.hero_heading,
            "description": page.hero_description,
            "media": MediaSchema().dump(page.hero_media) if page.hero_media else None,
        },
        "introContent": page.intro_content or [],
        "audienceOverview": page.audience_overview,
        "whyContent": page.why_content or [],
        "cta": {
            "heading": page.cta_heading,
            "description": page.cta_description,
            "buttonLabel": page.cta_button_label,
        },
        "contact": {
            "email": page.contact_email,
            "note": page.contact_note,
        },
        "mediaKit": (
            {
                "title": page.media_kit_title,
                "url": page.media_kit_url,
                "updatedAt": page.media_kit_updated_at.isoformat() if page.media_kit_updated_at else None,
            }
            if page.media_kit_url else None
        ),
        "faq": page.faq or [],
        "seo": page.seo or {},
    }


def build_public_metric_payload(metric):
    # Deliberately excludes `source_note` — internal provenance, never
    # rendered publicly (see AdvertiseMetric's own docstring).
    return {
        "id": metric.id,
        "label": metric.label,
        "value": metric.value,
        "unit": metric.unit,
        "asOfDate": metric.as_of_date.isoformat() if metric.as_of_date else None,
    }


def build_public_offering_payload(offering):
    payload = {
        "id": offering.id,
        "name": offering.name,
        "shortDescription": offering.short_description,
        "fullDescription": offering.full_description,
        "features": offering.features or [],
        "ctaLabel": offering.cta_label,
        "featured": offering.featured,
        "pricingMode": offering.pricing_mode,
    }
    if offering.pricing_mode in ("starting_from", "fixed"):
        payload["priceAmount"] = offering.price_amount
        payload["currency"] = offering.currency
    if offering.pricing_mode != "hidden":
        payload["pricingNote"] = offering.pricing_note
    return payload


class PublicAdvertiseResource(Resource):
    """One composite call so the public /advertise page never has to
    fan out into three separate requests.
    """

    def get(self):
        page = db.session.get(AdvertisePage, 1)
        if page is None or page.status != "published":
            raise ApiError("Advertise page not available.", 404, code="not_found")

        metrics = (
            AdvertiseMetric.query.filter_by(public_visible=True)
            .order_by(AdvertiseMetric.display_order)
            .all()
        )
        offerings = (
            AdvertiseOffering.query.filter_by(status="active")
            .order_by(AdvertiseOffering.display_order)
            .all()
        )
        return success_response(
            {
                "page": build_public_advertise_page(page),
                "metrics": [build_public_metric_payload(m) for m in metrics],
                "offerings": [build_public_offering_payload(o) for o in offerings],
            }
        )


api.add_resource(PublicAdvertiseResource, "/public")
api.add_resource(AdvertisePageResource, "/page")
api.add_resource(AdvertisePageStatusResource, "/page/status")
api.add_resource(AdvertiseMetricListResource, "/metrics")
api.add_resource(AdvertiseMetricDetailResource, "/metrics/<int:metric_id>")
api.add_resource(AdvertiseOfferingListResource, "/offerings")
api.add_resource(AdvertiseOfferingDetailResource, "/offerings/<int:offering_id>")
api.add_resource(AdvertiseHistoryResource, "/history")
