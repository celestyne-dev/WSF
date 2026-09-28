import csv
import io
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, Response, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.analytics import AnalyticsEvent
from app.models.newsletter import NewsletterSubscriber
from app.schemas.analytics import AnalyticsEventInputSchema, AnalyticsEventSchema
from app.services import analytics_reports as reports
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

analytics_bp = Blueprint("analytics", __name__)
api = Api(analytics_bp)

event_schema = AnalyticsEventSchema()

# A year is generous for any of these reports and keeps a client from
# requesting an unbounded, expensive range (spec section 63).
MAX_RANGE_DAYS = 366
DEFAULT_RANGE_DAYS = 30


class DateRangeSchema(Schema):
    """`?start=YYYY-MM-DD&end=YYYY-MM-DD` — both optional (defaults to the
    last 30 days); validated so a client can't send end-before-start or an
    unbounded range (spec section 63).
    """

    start = fields.Date(required=False, allow_none=True)
    end = fields.Date(required=False, allow_none=True)
    compare = fields.Boolean(required=False, load_default=False)

    class Meta:
        unknown = EXCLUDE

    @validates_schema
    def _validate_range(self, data, **kwargs):
        start = data.get("start")
        end = data.get("end")
        if start and end:
            if end < start:
                raise ValidationError("end date must be on or after the start date.", field_name="end")
            if (end - start).days > MAX_RANGE_DAYS:
                raise ValidationError(f"Date range cannot exceed {MAX_RANGE_DAYS} days.", field_name="end")


def _resolve_date_range():
    params = DateRangeSchema().load(request.args.to_dict())
    end = params.get("end") or date.today()
    start = params.get("start") or (end - timedelta(days=DEFAULT_RANGE_DAYS - 1))
    if end < start:
        raise ApiError("end date must be on or after the start date.", 422, code="invalid_date_range")
    return start, end, params.get("compare", False)


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _require_commercial():
    user = _require_active_user()
    if not user.has_permission("analytics.commercial"):
        raise ApiError("You do not have permission to view commercial analytics.", 403, code="forbidden")
    return user


def _require_export():
    user = _require_active_user()
    if not user.has_permission("analytics.export"):
        raise ApiError("You do not have permission to export analytics.", 403, code="forbidden")
    return user


def _csv_safe(value):
    """Prevents CSV formula injection — a text field a visitor themselves
    typed (a search query, a title) must never be interpreted as a
    formula by the spreadsheet app that opens this export (spec 96).
    """
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def _optional_current_user_id():
    """Analytics ingestion is public (anonymous visitors trigger most of
    these events), but attribute the event to a logged-in user when a
    valid token happens to be present.
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    return current_user.id if current_user else None


class AnalyticsEventListResource(Resource):
    def post(self):
        data = AnalyticsEventInputSchema().load(request.get_json(silent=True) or {})
        event = AnalyticsEvent(
            event_name=data["event_name"],
            entity_type=data.get("entity_type"),
            entity_id=data.get("entity_id"),
            payload=data.get("payload"),
            acquisition=data.get("acquisition"),
            session_id=data.get("session_id"),
            user_id=_optional_current_user_id(),
        )
        db.session.add(event)
        db.session.commit()
        return success_response(None, status=201)

    @permission_required("analytics.view")
    def get(self):
        query = AnalyticsEvent.query.order_by(AnalyticsEvent.created_at.desc())
        event_name = request.args.get("event_name")
        if event_name:
            query = query.filter_by(event_name=event_name)
        result = paginate(query, event_schema)
        return success_response(result["items"], meta=result["meta"])


class AnalyticsSummaryResource(Resource):
    @permission_required("analytics.view")
    def get(self):
        rows = (
            db.session.query(AnalyticsEvent.event_name, db.func.count(AnalyticsEvent.id))
            .group_by(AnalyticsEvent.event_name)
            .order_by(db.func.count(AnalyticsEvent.id).desc())
            .all()
        )
        return success_response([{"eventName": name, "count": count} for name, count in rows])


def _last_six_month_boundaries():
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    boundaries = []
    cursor = month_start
    for _ in range(6):
        boundaries.append(cursor)
        prev_month_end = cursor - timedelta(seconds=1)
        cursor = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    boundaries.reverse()
    return boundaries, now


class AnalyticsTrafficSourceResource(Resource):
    """Referral-source breakdown from the acquisition context every
    tracked event carries (see frontend/src/utils/analytics.js) — direct/
    LinkedIn/other-referrer/UTM-campaign, whichever `source` visitors
    actually arrived from, not a fabricated split.
    """

    @permission_required("analytics.view")
    def get(self):
        rows = (
            db.session.query(
                AnalyticsEvent.acquisition.op("->>")("source").label("source"),
                db.func.count(AnalyticsEvent.id),
            )
            .group_by("source")
            .order_by(db.func.count(AnalyticsEvent.id).desc())
            .all()
        )
        return success_response([{"name": source or "Direct", "value": count} for source, count in rows])


class AnalyticsSubscriberGrowthResource(Resource):
    @permission_required("analytics.view")
    def get(self):
        boundaries, now = _last_six_month_boundaries()
        growth = []
        for idx, start in enumerate(boundaries):
            end = boundaries[idx + 1] if idx + 1 < len(boundaries) else now
            count = NewsletterSubscriber.query.filter(
                NewsletterSubscriber.subscribed_at >= start, NewsletterSubscriber.subscribed_at < end
            ).count()
            growth.append({"month": start.strftime("%b"), "subscribers": count})
        return success_response(growth)


class AnalyticsOverviewResource(Resource):
    """Headline KPI cards + trend + audience-by-source for the Overview
    tab (spec section 10, 15, 41) — a small, prioritized set of real
    metrics, never dozens of cards.
    """

    @permission_required("analytics.view")
    def get(self):
        start, end, compare = _resolve_date_range()
        overview = reports.get_overview(start, end, compare=compare)
        trend = reports.get_trend(start, end)
        return success_response(
            {
                "range": {"start": start.isoformat(), "end": end.isoformat()},
                "metrics": overview["metrics"],
                "comparison": overview["comparison"],
                "audienceBySource": overview["audienceBySource"],
                "trend": trend,
            }
        )


class AnalyticsContentResource(Resource):
    """Top Articles by real article_view events (spec section 16-17),
    plus current Topic/Series aggregate views (spec section 18).
    """

    @permission_required("analytics.view")
    def get(self):
        start, end, _ = _resolve_date_range()
        sort = request.args.get("sort", "views")
        if sort not in ("views", "date", "date_asc"):
            raise ApiError("Invalid sort value.", 422, code="invalid_sort")
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 50)
        content = reports.get_content_performance(start, end, sort=sort, page=page, per_page=per_page)
        topic_series = reports.get_topic_series_performance(start, end)
        return success_response({**content, "topics": topic_series["topics"], "series": topic_series["series"]})


class AnalyticsSearchResource(Resource):
    """Search activity from the Search & Discovery system's own events —
    never a personalized search profile (spec section 20-21).
    """

    @permission_required("analytics.view")
    def get(self):
        start, end, _ = _resolve_date_range()
        return success_response(reports.get_search_analytics(start, end))


class AnalyticsNewsletterResource(Resource):
    @permission_required("analytics.view")
    def get(self):
        start, end, _ = _resolve_date_range()
        return success_response(reports.get_newsletter_analytics(start, end))


class AnalyticsCareersResource(Resource):
    """Jobs/Opportunities/Events/Resources engagement — views are real;
    apply/registration clicks stay labeled as clicks, never completed
    applications/registrations (spec section 24-27).
    """

    @permission_required("analytics.view")
    def get(self):
        start, end, _ = _resolve_date_range()
        return success_response(reports.get_careers_analytics(start, end))


class AnalyticsCommunityProgramsResource(Resource):
    """Community/Mentorship/Story Submission/Nomination aggregates —
    general analytics.view, not commercial (no money involved); the
    service layer itself never returns an identity, only counts.
    """

    @permission_required("analytics.view")
    def get(self):
        start, end, _ = _resolve_date_range()
        return success_response(reports.get_community_programs_analytics(start, end))


class AnalyticsCommercialResource(Resource):
    """Sponsor/Advertise/Partnership/Orders — restricted to
    analytics.commercial (spec section 37-38, 71-77).
    """

    def get(self):
        _require_commercial()
        start, end, _ = _resolve_date_range()
        return success_response(reports.get_commercial_analytics(start, end))


class AnalyticsContentExportResource(Resource):
    def get(self):
        _require_export()
        start, end, _ = _resolve_date_range()
        content = reports.get_content_performance(start, end, sort="views", page=1, per_page=500)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Article", "Slug", "Views", "Published Date", "Topic"])
        for row in content["results"]:
            writer.writerow(
                [_csv_safe(row["title"]), _csv_safe(row["slug"]), row["views"], row["publishedDate"] or "", _csv_safe(row["topic"] or "")]
            )
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=wsf-content-analytics-{date.today().isoformat()}.csv"
        return response


class AnalyticsSearchExportResource(Resource):
    def get(self):
        _require_export()
        start, end, _ = _resolve_date_range()
        search = reports.get_search_analytics(start, end)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Query", "Search Count", "Last Searched"])
        for row in search["topQueries"]:
            writer.writerow([_csv_safe(row["query"]), row["count"], _csv_safe(row["lastSearched"] or "")])
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=wsf-search-analytics-{date.today().isoformat()}.csv"
        return response


class AnalyticsSponsorExportResource(Resource):
    """Sponsor campaign performance export — requires BOTH analytics.export
    AND analytics.commercial (this is commercially sensitive data, not
    just any aggregate report).
    """

    def get(self):
        _require_export()
        _require_commercial()
        start, end, _ = _resolve_date_range()
        commercial = reports.get_commercial_analytics(start, end)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Sponsor", "Impressions", "Clicks", "CTR (%)"])
        for row in commercial["sponsors"]:
            writer.writerow([_csv_safe(row["sponsor"]), row["impressions"], row["clicks"], row["ctr"] if row["ctr"] is not None else ""])
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=wsf-sponsor-analytics-{date.today().isoformat()}.csv"
        return response


api.add_resource(AnalyticsEventListResource, "/events")
api.add_resource(AnalyticsSummaryResource, "/summary")
api.add_resource(AnalyticsTrafficSourceResource, "/traffic-sources")
api.add_resource(AnalyticsSubscriberGrowthResource, "/subscriber-growth")
api.add_resource(AnalyticsOverviewResource, "/overview")
api.add_resource(AnalyticsContentResource, "/content")
api.add_resource(AnalyticsSearchResource, "/search-report")
api.add_resource(AnalyticsNewsletterResource, "/newsletter")
api.add_resource(AnalyticsCareersResource, "/careers")
api.add_resource(AnalyticsCommunityProgramsResource, "/community-programs")
api.add_resource(AnalyticsCommercialResource, "/commercial")
api.add_resource(AnalyticsContentExportResource, "/export/content")
api.add_resource(AnalyticsSearchExportResource, "/export/search")
api.add_resource(AnalyticsSponsorExportResource, "/export/sponsors")
