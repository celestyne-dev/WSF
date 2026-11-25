from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, Response, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db, limiter
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
from app.services.indexnow import capture_public_urls, notify_public_change
from app.services.engagement_settings import NEWSLETTER_CONSENT_VERSION
from app.services.newsletter import (
    NewsletterError,
    approve_after_deliverability_review,
    confirm_subscription,
    count_audience,
    export_csv,
    import_suppressions,
    record_export,
    record_external_send,
    request_reconfirmation,
    request_subscription,
    unsubscribe,
)
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.services.rate_limits import limit
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

newsletter_bp = Blueprint("newsletter", __name__)
api = Api(newsletter_bp)

subscriber_schema = NewsletterSubscriberSchema()
confirmation_schema = NewsletterSubscriberConfirmationSchema()
issue_schema = NewsletterIssueSchema()
public_issue_schema = NewsletterIssuePublicSchema()

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
    """An issue can't be marked Ready without a subject and content.
    Draft issues may stay incomplete. The planned date is optional and
    informational (WSF never sends on a schedule)."""
    if issue.status not in ("ready",):
        return
    if not issue.subject:
        raise ApiError("A subject line is required before marking this issue ready.", 422, code="validation_error")
    if not issue.content:
        raise ApiError("Newsletter content is required before marking this issue ready.", 422, code="validation_error")


class SubscribeResource(Resource):
    """Step 1 of double opt-in. Requires the explicit, unticked-by-default
    consent checkbox (`consent: true`); nothing is stored without it. Never
    subscribes anyone directly: it sends a confirmation link
    (app/services/newsletter.py request_subscription)."""

    @limiter.limit(limit("newsletter_subscribe"))
    def post(self):
        data = SubscribeInputSchema().load(request.get_json(silent=True) or {})
        if data.get("consent") is not True:
            raise ApiError("Please tick the box to agree to receive the WSF Weekly newsletter.", 422,
                           code="newsletter_consent_required")
        try:
            _subscriber, outcome = request_subscription(
                data["email"], consent_version=NEWSLETTER_CONSENT_VERSION, first_name=data.get("first_name"),
                last_name=data.get("last_name"), country_code=data.get("country_code"),
                placement=data.get("placement"), acquisition=data.get("acquisition"),
                topic_slugs=data.get("topic_slugs"))
        except NewsletterError as exc:
            raise ApiError(str(exc), exc.status, code=exc.code)
        db.session.commit()
        if outcome == "confirmation_failed":
            # Truthful: the email service reported a failure. (Reveals nothing
            # about list membership: it can only happen when a send was tried.)
            raise ApiError("We couldn't send the confirmation email just now. Please try again in a few minutes.",
                           503, code="email_send_failed")
        # One uniform answer whatever the address's state (new, pending,
        # already confirmed, suppressed), so it never reveals list membership.
        return success_response(
            {"email": data["email"].strip().lower(), "status": "confirmation_required"}, status=201,
            message="Almost done: check your inbox and click the link to confirm your subscription.")


class ConfirmSubscriptionResource(Resource):
    """Step 2 of double opt-in: the emailed link's token. POST (the link
    opens a page that posts it), so mail scanners prefetching the link
    can't confirm on someone's behalf. Idempotent."""

    @limiter.limit(limit("newsletter_confirm"))
    def post(self):
        payload = request.get_json(silent=True) or {}
        result = confirm_subscription(payload.get("token"))
        if result in ("confirmed", "already_confirmed"):
            return success_response({"result": result}, message="You're subscribed to WSF Weekly.")
        if result == "review_required":
            return success_response({"result": result}, message=(
                "Thanks, your confirmation is recorded. Earlier emails to this address bounced or were reported, so our "
                "team will check delivery before we send WSF Weekly again."))
        if result == "expired":
            raise ApiError("This confirmation link has expired. Please sign up again to get a new one.", 410,
                           code="confirmation_expired")
        raise ApiError("This confirmation link isn't valid.", 404, code="confirmation_invalid")


class UnsubscribeResource(Resource):
    """Manual fallback for a subscriber who knows their own email but
    doesn't have an unsubscribe link handy — requires POSTing the email
    itself (never a bare GET query param), so this is not the "expose a
    subscriber via a guessable link" mechanism the token route avoids.
    """

    @limiter.limit(limit("newsletter_unsubscribe"))
    def post(self):
        data = UnsubscribeInputSchema().load(request.get_json(silent=True) or {})
        subscriber = NewsletterSubscriber.query.filter_by(email=data["email"].strip().lower()).first()
        if subscriber is None:
            raise ApiError("No subscription found for this email.", 404, code="not_found")

        unsubscribe(subscriber, "form")
        db.session.commit()
        return success_response(confirmation_schema.dump(subscriber), message="Unsubscribed.")


class UnsubscribeByTokenResource(Resource):
    """The primary unsubscribe mechanism — a stable, unguessable per-
    subscriber token, never a raw email or numeric id. Safe to expose as a
    plain link click (GET): unsubscribing an already-unsubscribed address
    is a harmless no-op, matching standard one-click email unsubscribe
    behavior.
    """

    @limiter.limit(limit("newsletter_unsubscribe_link"))
    def get(self, token):
        subscriber = NewsletterSubscriber.query.filter_by(unsubscribe_token=token).first()
        if subscriber is None:
            raise ApiError("This unsubscribe link is invalid or has expired.", 404, code="not_found")

        unsubscribe(subscriber, "link")  # idempotent; also voids any pending confirmation link
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
        notify_public_change({}, issue)
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
        public_before = capture_public_urls(issue)

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
        notify_public_change(public_before, issue)
        return success_response(issue_schema.dump(issue))


def _issue_or_404(slug):
    issue = NewsletterIssue.query.filter_by(slug=slug).first()
    if issue is None:
        raise ApiError("Newsletter issue not found.", 404, code="not_found")
    return issue


def _send_record_dump(r):
    return {"id": r.id, "kind": r.kind, "providerName": r.provider_name, "externalReference": r.external_reference,
            "recipientCount": r.recipient_count, "occurredAt": r.occurred_at.isoformat() if r.occurred_at else None,
            "note": r.note, "recordedBy": r.actor.full_name if r.actor else None}


class NewsletterIssueRecordSendResource(Resource):
    """Records that staff SENT this issue through an external service
    (replaces the old "mark as sent"). WSF itself transmits nothing: the
    record says which service, its campaign reference, how many recipients
    and when."""

    @permission_required("newsletter.manage")
    def post(self, slug):
        issue = _issue_or_404(slug)
        public_before = capture_public_urls(issue)
        if issue.status == "sent":
            raise ApiError("A send is already recorded for this issue.", 409, code="already_sent")
        if not issue.subject or not issue.content:
            raise ApiError("Add a subject and content before recording a send.", 422, code="validation_error")
        data = request.get_json(silent=True) or {}
        sent_at = None
        if data.get("sentAt"):
            try:
                sent_at = datetime.fromisoformat(str(data["sentAt"]).replace("Z", "+00:00"))
            except ValueError:
                raise ApiError("sentAt must be an ISO date-time.", 422, code="validation_error")
        previous_status = issue.status
        try:
            record = record_external_send(issue, provider_name=data.get("providerName"),
                                          recipient_count=data.get("recipientCount"),
                                          external_reference=data.get("externalReference"), sent_at=sent_at,
                                          note=data.get("note"), actor=current_user)
        except NewsletterError as exc:
            raise ApiError(str(exc), exc.status, code=exc.code)
        log_action(current_user, "newsletter_issue_external_send_recorded", "NewsletterIssue", issue.id,
                   changes={"from": previous_status, "to": "sent", "provider": record.provider_name,
                            "recipients": record.recipient_count})
        notify_public_change(public_before, issue)
        return success_response({**issue_schema.dump(issue), "sendRecord": _send_record_dump(record)})


class NewsletterIssueExportResource(Resource):
    """Confirmed, active recipients for this issue's audience as CSV, for
    upload to an external sending service. Each download is recorded."""

    def get(self, slug):
        _require_export()
        issue = _issue_or_404(slug)
        text, count = export_csv(issue.audience_filter)
        record_export(issue, count, current_user)
        log_action(current_user, "newsletter_issue_exported", "NewsletterIssue", issue.id, changes={"count": count})
        response = Response(text, mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=wsf-weekly-{issue.slug}-recipients.csv"
        return response


class NewsletterIssueSendRecordsResource(Resource):
    @permission_required("newsletter.manage")
    def get(self, slug):
        from app.models.newsletter import NewsletterSendRecord

        issue = _issue_or_404(slug)
        rows = (NewsletterSendRecord.query.filter_by(issue_id=issue.id)
                .order_by(NewsletterSendRecord.occurred_at.desc()).all())
        return success_response({"records": [_send_record_dump(r) for r in rows]})


class NewsletterIssueArchiveResource(Resource):
    @permission_required("newsletter.manage")
    def post(self, slug):
        issue = NewsletterIssue.query.filter_by(slug=slug).first()
        if issue is None:
            raise ApiError("Newsletter issue not found.", 404, code="not_found")
        public_before = capture_public_urls(issue)

        previous_status = issue.status
        issue.status = "archived"
        db.session.commit()
        log_action(
            current_user, "newsletter_issue_archived", "NewsletterIssue", issue.id,
            changes={"from": previous_status, "to": "archived"},
        )
        notify_public_change(public_before, issue)
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

        reason = (request.get_json(silent=True) or {}).get("reason")
        unsubscribe(subscriber, "studio", reason=reason if isinstance(reason, str) else None, actor=current_user)
        db.session.commit()
        log_action(current_user, "newsletter_subscriber_suppressed", "NewsletterSubscriber", subscriber.id)
        return success_response(subscriber_schema.dump(subscriber))


class NewsletterSubscriberReactivateResource(Resource):
    """Retired: Studio can no longer switch an address back on. Under double
    opt-in only the person can, by signing up again and clicking the
    confirmation link (fresh consent, recorded in their trail)."""

    @permission_required("newsletter.manage")
    def post(self, subscriber_id):
        raise ApiError("Only the person can resubscribe: ask them to sign up again and click the confirmation "
                       "link we email them.", 409, code="reactivation_requires_confirmation")


class NewsletterSubscriberDeliverabilityReviewResource(Resource):
    """Bounced/complained address: reactivate only if the person has given and
    confirmed fresh consent since the suppression; this records the staff
    deliverability review (audited). Never a substitute for their consent."""

    @permission_required("newsletter.manage")
    def post(self, subscriber_id):
        subscriber = db.session.get(NewsletterSubscriber, subscriber_id)
        if subscriber is None:
            raise ApiError("Subscriber not found.", 404, code="not_found")
        note = (request.get_json(silent=True) or {}).get("note")
        try:
            approve_after_deliverability_review(subscriber, current_user, note if isinstance(note, str) else "")
        except NewsletterError as exc:
            db.session.rollback()
            raise ApiError(str(exc), exc.status, code=exc.code)
        db.session.commit()
        log_action(current_user, "newsletter_subscriber_deliverability_review_approved", "NewsletterSubscriber",
                   subscriber.id, changes={"note": note[:200] if isinstance(note, str) else None})
        return success_response(subscriber_schema.dump(subscriber), message="Reactivated after review.")


class NewsletterSubscriberRequestConfirmationResource(Resource):
    """Ask a legacy (pre-double-opt-in) subscriber to confirm by email."""

    @permission_required("newsletter.manage")
    @limiter.limit("30 per minute")
    def post(self, subscriber_id):
        subscriber = db.session.get(NewsletterSubscriber, subscriber_id)
        if subscriber is None:
            raise ApiError("Subscriber not found.", 404, code="not_found")
        try:
            request_reconfirmation(subscriber, current_user)
        except NewsletterError as exc:
            db.session.commit()  # keep the audit trail of the failed attempt
            raise ApiError(str(exc), exc.status, code=exc.code)
        db.session.commit()
        log_action(current_user, "newsletter_subscriber_confirmation_requested", "NewsletterSubscriber", subscriber.id)
        return success_response(subscriber_schema.dump(subscriber), message="Confirmation email sent.")


class NewsletterSuppressionImportResource(Resource):
    """Unsubscribes reported by an external sending service (CSV text with an
    email column, or one address per line) -> suppressed in WSF. Never
    reactivates; repeat imports change nothing more."""

    @permission_required("newsletter.manage")
    @limiter.limit("10 per minute")
    def post(self):
        data = request.get_json(silent=True) or {}
        text = data.get("csv")
        if not isinstance(text, str) or not text.strip():
            raise ApiError("Paste or upload the CSV of unsubscribed addresses.", 422, code="validation_error")
        if len(text) > 5_000_000:
            raise ApiError("That file is too large; please split it.", 422, code="validation_error")
        try:
            batch = import_suppressions(data.get("provider"), text, data.get("filename"), current_user,
                                        kind=data.get("kind") or "unsubscribed")
        except NewsletterError as exc:
            raise ApiError(str(exc), exc.status, code=exc.code)
        counts = {"rows": batch.rows, "invalid": batch.invalid, "newlySuppressed": batch.newly_suppressed,
                  "alreadySuppressed": batch.already_suppressed, "addedUnknown": batch.added_unknown}
        log_action(current_user, "newsletter_suppression_import", "NewsletterSuppressionImport", batch.id,
                   changes={"provider": batch.provider, **counts})
        return success_response({"id": batch.id, "provider": batch.provider, **counts})


class NewsletterSubscriberExportResource(Resource):
    def get(self):
        _require_export()

        # Confirmed, currently active subscribers only; delivery fields only.
        text, count = export_csv()
        log_action(
            current_user, "newsletter_subscribers_exported", "NewsletterSubscriber", None,
            changes={"count": count},
        )
        response = Response(text, mimetype="text/csv")
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
                "pendingSubscribers": NewsletterSubscriber.query.filter_by(status="pending").count(),
                "legacyUnconfirmed": NewsletterSubscriber.query.filter_by(status="legacy_unconfirmed").count(),
                "newSubscribers30d": NewsletterSubscriber.query.filter(
                    NewsletterSubscriber.status == "active", NewsletterSubscriber.subscribed_at >= cutoff
                ).count(),
                "unsubscribedCount": NewsletterSubscriber.query.filter_by(status="unsubscribed").count(),
                "draftIssues": NewsletterIssue.query.filter_by(status="draft").count(),
                "readyIssues": NewsletterIssue.query.filter_by(status="ready").count(),
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
api.add_resource(ConfirmSubscriptionResource, "/confirm")
api.add_resource(UnsubscribeResource, "/unsubscribe")
api.add_resource(UnsubscribeByTokenResource, "/unsubscribe/<string:token>")
api.add_resource(NewsletterIssueListResource, "/issues")
api.add_resource(NewsletterIssueDetailResource, "/issues/<string:slug>")
api.add_resource(NewsletterIssueRecordSendResource, "/issues/<string:slug>/record-send")
api.add_resource(NewsletterIssueExportResource, "/issues/<string:slug>/export")
api.add_resource(NewsletterIssueSendRecordsResource, "/issues/<string:slug>/send-records")
api.add_resource(NewsletterIssueArchiveResource, "/issues/<string:slug>/archive")
api.add_resource(AudienceEstimateResource, "/audience-estimate")
api.add_resource(NewsletterSubscriberListResource, "/subscribers")
api.add_resource(NewsletterSubscriberExportResource, "/subscribers/export")
api.add_resource(NewsletterSubscriberDetailResource, "/subscribers/<int:subscriber_id>")
api.add_resource(NewsletterSubscriberSuppressResource, "/subscribers/<int:subscriber_id>/suppress")
api.add_resource(NewsletterSubscriberReactivateResource, "/subscribers/<int:subscriber_id>/reactivate")
api.add_resource(NewsletterSubscriberDeliverabilityReviewResource,
                 "/subscribers/<int:subscriber_id>/deliverability-review")
api.add_resource(NewsletterSubscriberRequestConfirmationResource,
                 "/subscribers/<int:subscriber_id>/request-confirmation")
api.add_resource(NewsletterSuppressionImportResource, "/subscribers/suppression-import")
api.add_resource(NewsletterOverviewResource, "/overview")
api.add_resource(NewsletterStatsResource, "/stats")
api.add_resource(NewsletterSenderResource, "/sender")
