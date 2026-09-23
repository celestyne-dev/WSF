import csv
import io
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, Response, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.cms import SiteSetting
from app.models.media import Media
from app.models.newsletter import NewsletterIssue, NewsletterSubscriber
from app.models.taxonomy import Topic
from app.schemas.newsletter import (
    AudienceEstimateInputSchema,
    NewsletterAdminSubscriberUpdateSchema,
    NewsletterIssueInputSchema,
    NewsletterIssuePublicSchema,
    NewsletterIssueSchema,
    NewsletterSubscriberConfirmationSchema,
    NewsletterSubscriberSchema,
    SubscribeInputSchema,
    UnsubscribeInputSchema,
)
from app.services.audit import log_action
from app.services.content_blocks import sanitize_content_blocks
from app.services.newsletter import audience_query, count_audience, upsert_subscriber
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

newsletter_bp = Blueprint("newsletter", __name__)
api = Api(newsletter_bp)

subscriber_schema = NewsletterSubscriberSchema()
confirmation_schema = NewsletterSubscriberConfirmationSchema()
issue_schema = NewsletterIssueSchema()
public_issue_schema = NewsletterIssuePublicSchema()

_EXPORT_COLUMNS = [
    "Email", "First Name", "Last Name", "Status", "Source", "Subscribed At", "Unsubscribed At", "Interests",
]


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("newsletter.manage"):
        raise ApiError("You do not have permission to manage the newsletter.", 403, code="forbidden")
    return user


def _require_export():
    user = _require_active_user()
    if not user.has_permission("newsletter.export"):
        raise ApiError("You do not have permission to export subscribers.", 403, code="forbidden")
    return user


def _resolve_topics(topic_slugs):
    if not topic_slugs:
        return []
    found = {t.slug: t for t in Topic.query.filter(Topic.slug.in_(topic_slugs)).all()}
    missing = [slug for slug in topic_slugs if slug not in found]
    if missing:
        raise ApiError(f'Topic "{missing[0]}" not found.', 404, code="not_found")
    return [found[slug] for slug in topic_slugs]


def _resolve_featured_article(slug):
    if not slug:
        return None
    article = Article.query.filter_by(slug=slug).first()
    if article is None:
        raise ApiError(f'Article "{slug}" not found.', 404, code="not_found")
    return article


def _validate_cover_media(media_id):
    if not media_id:
        return
    if db.session.get(Media, media_id) is None:
        raise ApiError(f"Media #{media_id} not found.", 404, code="not_found")


def _validate_audience_filter(audience_filter):
    if not audience_filter:
        return
    topic_slugs = audience_filter.get("topicSlugs") or []
    if topic_slugs:
        _resolve_topics(topic_slugs)


def _validate_issue_readiness(issue):
    """A campaign should not become Scheduled without sufficient content
    and subject information. Draft issues may remain incomplete.
    """
    if issue.status not in ("scheduled",):
        return
    if not issue.subject:
        raise ApiError("A subject line is required before scheduling.", 422, code="validation_error")
    if not issue.content:
        raise ApiError("Newsletter content is required before scheduling.", 422, code="validation_error")
    if not issue.scheduled_at:
        raise ApiError("A scheduled date/time is required to mark this issue as scheduled.", 422, code="validation_error")


class SubscribeResource(Resource):
    def post(self):
        data = SubscribeInputSchema().load(request.get_json(silent=True) or {})
        subscriber, created, reactivated = upsert_subscriber(
            data["email"],
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            country_code=data.get("country_code"),
            placement=data.get("placement"),
            acquisition=data.get("acquisition"),
            topic_slugs=data.get("topic_slugs"),
        )
        db.session.commit()
        return success_response(confirmation_schema.dump(subscriber), status=201)


class UnsubscribeResource(Resource):
    """Manual fallback for a subscriber who knows their own email but
    doesn't have an unsubscribe link handy — requires POSTing the email
    itself (never a bare GET query param), so this is not the "expose a
    subscriber via a guessable link" mechanism the token route avoids.
    """

    def post(self):
        data = UnsubscribeInputSchema().load(request.get_json(silent=True) or {})
        subscriber = NewsletterSubscriber.query.filter_by(email=data["email"].strip().lower()).first()
        if subscriber is None:
            raise ApiError("No subscription found for this email.", 404, code="not_found")

        subscriber.status = "unsubscribed"
        subscriber.unsubscribed_at = datetime.now(timezone.utc)
        db.session.commit()
        return success_response(confirmation_schema.dump(subscriber), message="Unsubscribed.")


class UnsubscribeByTokenResource(Resource):
    """The primary unsubscribe mechanism — a stable, unguessable per-
    subscriber token, never a raw email or numeric id. Safe to expose as a
    plain link click (GET): unsubscribing an already-unsubscribed address
    is a harmless no-op, matching standard one-click email unsubscribe
    behavior.
    """

    def get(self, token):
        subscriber = NewsletterSubscriber.query.filter_by(unsubscribe_token=token).first()
        if subscriber is None:
            raise ApiError("This unsubscribe link is invalid or has expired.", 404, code="not_found")

        if subscriber.status == "active":
            subscriber.status = "unsubscribed"
            subscriber.unsubscribed_at = datetime.now(timezone.utc)
            db.session.commit()
        return success_response(confirmation_schema.dump(subscriber))


class NewsletterIssueListResource(Resource):
    def get(self):
        user = None
        try:
            verify_jwt_in_request(optional=True)
            if current_user and current_user.is_active and current_user.has_permission("newsletter.manage"):
                user = current_user
        except Exception:
            user = None

        query = NewsletterIssue.query.order_by(NewsletterIssue.created_at.desc())
        if user:
            status = request.args.get("status")
            if status:
                query = query.filter(NewsletterIssue.status == status)
        else:
            # Only explicitly sent issues are ever publicly visible.
            query = query.filter(NewsletterIssue.status == "sent").order_by(NewsletterIssue.sent_at.desc())

        query = apply_equality_filters(query, NewsletterIssue, request.args, [])
        query = apply_search(query, NewsletterIssue, request.args, ["title", "subject"])

        schema = issue_schema if user else public_issue_schema
        result = paginate(query, schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("newsletter.manage")
    def post(self):
        data = NewsletterIssueInputSchema().load(request.get_json(silent=True) or {})
        featured_article = _resolve_featured_article(data.get("featured_article_slug"))
        _validate_audience_filter(data.get("audience_filter"))

        issue = NewsletterIssue(featured_article=featured_article)
        issue.slug = (
            validate_explicit_slug(NewsletterIssue, data["slug"])
            if data.get("slug")
            else generate_unique_slug(NewsletterIssue, data["title"])
        )
        _apply_issue_fields(issue, data, featured_article)
        db.session.add(issue)
        db.session.commit()
        log_action(current_user, "newsletter_issue_created", "NewsletterIssue", issue.id)
        return success_response(issue_schema.dump(issue), status=201)


def _apply_issue_fields(issue, data, featured_article):
    issue.title = data["title"]
    issue.subject = data["subject"]
    issue.preheader = data.get("preheader")
    issue.issue_number = data.get("issue_number")
    issue.content = sanitize_content_blocks(data.get("content", []))
    _validate_cover_media(data.get("cover_media_id"))
    issue.cover_media_id = data.get("cover_media_id")
    issue.summary = data.get("summary")
    issue.featured_article = featured_article
    issue.status = data.get("status", "draft")
    issue.audience_filter = data.get("audience_filter")
    issue.scheduled_at = data.get("scheduled_at")
    issue.send_timezone = data.get("send_timezone", "UTC")
    _validate_issue_readiness(issue)


class NewsletterIssueDetailResource(Resource):
    def get(self, slug):
        issue = NewsletterIssue.query.filter_by(slug=slug).first()
        if issue is None:
            raise ApiError("Newsletter issue not found.", 404, code="not_found")

        editor = None
        try:
            verify_jwt_in_request(optional=True)
            if current_user and current_user.is_active and current_user.has_permission("newsletter.manage"):
                editor = current_user
        except Exception:
            editor = None

        if issue.status != "sent" and not editor:
            raise ApiError("Newsletter issue not found.", 404, code="not_found")

        schema = issue_schema if editor else public_issue_schema
        return success_response(schema.dump(issue))

    @permission_required("newsletter.manage")
    def put(self, slug):
        issue = NewsletterIssue.query.filter_by(slug=slug).first()
        if issue is None:
            raise ApiError("Newsletter issue not found.", 404, code="not_found")

        data = NewsletterIssueInputSchema().load(request.get_json(silent=True) or {})
        featured_article = _resolve_featured_article(data.get("featured_article_slug"))
        _validate_audience_filter(data.get("audience_filter"))

        if data.get("slug") and data["slug"] != issue.slug:
            issue.slug = validate_explicit_slug(NewsletterIssue, data["slug"], current_id=issue.id)

        previous_status = issue.status
        _apply_issue_fields(issue, data, featured_article)
        if issue.status != previous_status:
            log_action(
                current_user, "newsletter_issue_status_changed", "NewsletterIssue", issue.id,
                changes={"from": previous_status, "to": issue.status},
            )
        db.session.commit()
        return success_response(issue_schema.dump(issue))


class NewsletterIssueMarkSentResource(Resource):
    """The one honest, explicit action that records a newsletter as sent.
    Never a side effect of an ordinary save — see NewsletterIssueInputSchema,
    which does not accept "sent" as a settable status. This records that an
    admin has sent (or is manually logging having sent) the issue; it does
    not itself deliver any email — no provider integration exists yet.
    """

    @permission_required("newsletter.manage")
    def post(self, slug):
        issue = NewsletterIssue.query.filter_by(slug=slug).first()
        if issue is None:
            raise ApiError("Newsletter issue not found.", 404, code="not_found")
        if issue.status == "sent":
            raise ApiError("This issue is already marked as sent.", 409, code="already_sent")
        if not issue.subject:
            raise ApiError("A subject line is required before marking this issue as sent.", 422, code="validation_error")
        if not issue.content:
            raise ApiError("Newsletter content is required before marking this issue as sent.", 422, code="validation_error")

        previous_status = issue.status
        issue.status = "sent"
        issue.sent_at = datetime.now(timezone.utc)
        db.session.commit()
        log_action(
            current_user, "newsletter_issue_marked_sent", "NewsletterIssue", issue.id,
            changes={"from": previous_status, "to": "sent"},
        )
        return success_response(issue_schema.dump(issue))


class NewsletterIssueArchiveResource(Resource):
    @permission_required("newsletter.manage")
    def post(self, slug):
        issue = NewsletterIssue.query.filter_by(slug=slug).first()
        if issue is None:
            raise ApiError("Newsletter issue not found.", 404, code="not_found")

        previous_status = issue.status
        issue.status = "archived"
        db.session.commit()
        log_action(
            current_user, "newsletter_issue_archived", "NewsletterIssue", issue.id,
            changes={"from": previous_status, "to": "archived"},
        )
        return success_response(issue_schema.dump(issue))


class AudienceEstimateResource(Resource):
    @permission_required("newsletter.manage")
    def post(self):
        data = AudienceEstimateInputSchema().load(request.get_json(silent=True) or {})
        audience_filter = data.get("audience_filter")
        _validate_audience_filter(audience_filter)
        return success_response({"estimatedRecipients": count_audience(audience_filter)})


class NewsletterSubscriberListResource(Resource):
    @permission_required("newsletter.manage")
    def get(self):
        query = NewsletterSubscriber.query.order_by(NewsletterSubscriber.subscribed_at.desc())
        query = apply_equality_filters(query, NewsletterSubscriber, request.args, ["status", "placement"])
        query = apply_search(query, NewsletterSubscriber, request.args, ["email", "first_name", "last_name"])
        if request.args.get("topic"):
            query = query.filter(NewsletterSubscriber.interests.any(slug=request.args["topic"]))
        result = paginate(query, subscriber_schema)
        return success_response(result["items"], meta=result["meta"])


class NewsletterSubscriberDetailResource(Resource):
    @permission_required("newsletter.manage")
    def get(self, subscriber_id):
        subscriber = db.session.get(NewsletterSubscriber, subscriber_id)
        if subscriber is None:
            raise ApiError("Subscriber not found.", 404, code="not_found")
        return success_response(subscriber_schema.dump(subscriber))

    @permission_required("newsletter.manage")
    def patch(self, subscriber_id):
        subscriber = db.session.get(NewsletterSubscriber, subscriber_id)
        if subscriber is None:
            raise ApiError("Subscriber not found.", 404, code="not_found")

        data = NewsletterAdminSubscriberUpdateSchema().load(request.get_json(silent=True) or {})
        if "first_name" in data:
            subscriber.first_name = data["first_name"]
        if "last_name" in data:
            subscriber.last_name = data["last_name"]
        if "country_code" in data:
            subscriber.country_code = data["country_code"]
        if data.get("topic_slugs") is not None:
            subscriber.interests = _resolve_topics(data["topic_slugs"])

        db.session.commit()
        return success_response(subscriber_schema.dump(subscriber))


class NewsletterSubscriberSuppressResource(Resource):
    @permission_required("newsletter.manage")
    def post(self, subscriber_id):
        subscriber = db.session.get(NewsletterSubscriber, subscriber_id)
        if subscriber is None:
            raise ApiError("Subscriber not found.", 404, code="not_found")

        subscriber.status = "unsubscribed"
        subscriber.unsubscribed_at = datetime.now(timezone.utc)
        db.session.commit()
        log_action(current_user, "newsletter_subscriber_suppressed", "NewsletterSubscriber", subscriber.id)
        return success_response(subscriber_schema.dump(subscriber))


class NewsletterSubscriberReactivateResource(Resource):
    """A deliberate admin action — the one place a bounced/complained or
    unsubscribed address may be reactivated. An ordinary public signup
    never reaches this; see services/newsletter.py::upsert_subscriber.
    """

    @permission_required("newsletter.manage")
    def post(self, subscriber_id):
        subscriber = db.session.get(NewsletterSubscriber, subscriber_id)
        if subscriber is None:
            raise ApiError("Subscriber not found.", 404, code="not_found")

        subscriber.status = "active"
        subscriber.unsubscribed_at = None
        db.session.commit()
        log_action(current_user, "newsletter_subscriber_reactivated", "NewsletterSubscriber", subscriber.id)
        return success_response(subscriber_schema.dump(subscriber))


class NewsletterSubscriberExportResource(Resource):
    def get(self):
        _require_export()

        query = NewsletterSubscriber.query.order_by(NewsletterSubscriber.subscribed_at.desc())
        query = apply_equality_filters(query, NewsletterSubscriber, request.args, ["status", "placement"])
        subscribers = query.limit(20000).all()

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(_EXPORT_COLUMNS)
        for s in subscribers:
            writer.writerow(
                [
                    s.email,
                    s.first_name or "",
                    s.last_name or "",
                    s.status,
                    s.placement or "",
                    s.subscribed_at.isoformat() if s.subscribed_at else "",
                    s.unsubscribed_at.isoformat() if s.unsubscribed_at else "",
                    ", ".join(t.name for t in s.interests),
                ]
            )

        log_action(
            current_user, "newsletter_subscribers_exported", "NewsletterSubscriber", None,
            changes={"count": len(subscribers)},
        )
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=newsletter-subscribers-{date.today().isoformat()}.csv"
        return response


class NewsletterOverviewResource(Resource):
    """Real database counts only — no fabricated growth percentages."""

    @permission_required("newsletter.manage")
    def get(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        return success_response(
            {
                "activeSubscribers": NewsletterSubscriber.query.filter_by(status="active").count(),
                "newSubscribers30d": NewsletterSubscriber.query.filter(
                    NewsletterSubscriber.status == "active", NewsletterSubscriber.subscribed_at >= cutoff
                ).count(),
                "unsubscribedCount": NewsletterSubscriber.query.filter_by(status="unsubscribed").count(),
                "draftIssues": NewsletterIssue.query.filter_by(status="draft").count(),
                "scheduledIssues": NewsletterIssue.query.filter_by(status="scheduled").count(),
                "sentIssues": NewsletterIssue.query.filter_by(status="sent").count(),
            }
        )


class NewsletterStatsResource(Resource):
    """A live subscriber count plus whatever open-rate/cadence figures an
    admin has entered (SiteSetting key 'newsletter_stats' — same
    CMS-editable-number pattern as the Partnerships audience stats).
    """

    def get(self):
        subscriber_count = NewsletterSubscriber.query.filter_by(status="active").count()
        setting = db.session.get(SiteSetting, "newsletter_stats")
        extra = setting.value if setting else {}
        return success_response({"subscriberCount": subscriber_count, **extra})


class NewsletterSenderResource(Resource):
    """Read-only sender identity for the CMS to display — configured via
    the SiteSetting key 'newsletter_sender' (not editable from this
    module; Site Settings itself is out of this task's scope). Falls back
    to a placeholder until an admin sets it.
    """

    @permission_required("newsletter.manage")
    def get(self):
        setting = db.session.get(SiteSetting, "newsletter_sender")
        value = setting.value if setting else {}
        return success_response(
            {
                "name": value.get("name") or "Women Shaping Futures",
                "email": value.get("email") or "",
                "configured": bool(value.get("email")),
            }
        )


api.add_resource(SubscribeResource, "/subscribe")
api.add_resource(UnsubscribeResource, "/unsubscribe")
api.add_resource(UnsubscribeByTokenResource, "/unsubscribe/<string:token>")
api.add_resource(NewsletterIssueListResource, "/issues")
api.add_resource(NewsletterIssueDetailResource, "/issues/<string:slug>")
api.add_resource(NewsletterIssueMarkSentResource, "/issues/<string:slug>/mark-sent")
api.add_resource(NewsletterIssueArchiveResource, "/issues/<string:slug>/archive")
api.add_resource(AudienceEstimateResource, "/audience-estimate")
api.add_resource(NewsletterSubscriberListResource, "/subscribers")
api.add_resource(NewsletterSubscriberExportResource, "/subscribers/export")
api.add_resource(NewsletterSubscriberDetailResource, "/subscribers/<int:subscriber_id>")
api.add_resource(NewsletterSubscriberSuppressResource, "/subscribers/<int:subscriber_id>/suppress")
api.add_resource(NewsletterSubscriberReactivateResource, "/subscribers/<int:subscriber_id>/reactivate")
api.add_resource(NewsletterOverviewResource, "/overview")
api.add_resource(NewsletterStatsResource, "/stats")
api.add_resource(NewsletterSenderResource, "/sender")
