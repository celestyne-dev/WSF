from datetime import datetime, timezone

from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.newsletter import NewsletterIssue, NewsletterSubscriber
from app.schemas.newsletter import (
    NewsletterIssueInputSchema,
    NewsletterIssueSchema,
    NewsletterSubscriberSchema,
    SubscribeInputSchema,
    UnsubscribeInputSchema,
)
from app.services.slugs import generate_unique_slug
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

newsletter_bp = Blueprint("newsletter", __name__)
api = Api(newsletter_bp)

subscriber_schema = NewsletterSubscriberSchema()
issue_schema = NewsletterIssueSchema()


class SubscribeResource(Resource):
    def post(self):
        data = SubscribeInputSchema().load(request.get_json(silent=True) or {})
        email = data["email"].lower()

        subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
        if subscriber is None:
            subscriber = NewsletterSubscriber(email=email)
            db.session.add(subscriber)

        subscriber.first_name = data.get("first_name") or subscriber.first_name
        subscriber.country_code = data.get("country_code") or subscriber.country_code
        subscriber.placement = data.get("placement") or subscriber.placement
        subscriber.acquisition = data.get("acquisition") or subscriber.acquisition
        subscriber.status = "active"
        subscriber.unsubscribed_at = None

        db.session.commit()
        return success_response(subscriber_schema.dump(subscriber), status=201)


class UnsubscribeResource(Resource):
    def post(self):
        data = UnsubscribeInputSchema().load(request.get_json(silent=True) or {})
        subscriber = NewsletterSubscriber.query.filter_by(email=data["email"].lower()).first()
        if subscriber is None:
            raise ApiError("No subscription found for this email.", 404, code="not_found")

        subscriber.status = "unsubscribed"
        subscriber.unsubscribed_at = datetime.now(timezone.utc)
        db.session.commit()
        return success_response(None, message="Unsubscribed.")


class NewsletterIssueListResource(Resource):
    def get(self):
        query = NewsletterIssue.query.order_by(NewsletterIssue.issue_number.desc())
        result = paginate(query, issue_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("newsletter.manage")
    def post(self):
        data = NewsletterIssueInputSchema().load(request.get_json(silent=True) or {})

        featured_article = None
        if data.get("featured_article_slug"):
            featured_article = Article.query.filter_by(slug=data["featured_article_slug"]).first()
            if featured_article is None:
                raise ApiError(
                    f"Article \"{data['featured_article_slug']}\" not found.", 404, code="not_found"
                )

        issue = NewsletterIssue(
            issue_number=data["issue_number"],
            subject=data["subject"],
            send_date=data["send_date"],
            summary=data.get("summary"),
            featured_article=featured_article,
        )
        issue.slug = data.get("slug") or generate_unique_slug(NewsletterIssue, data["subject"])
        db.session.add(issue)
        db.session.commit()
        return success_response(issue_schema.dump(issue), status=201)


class NewsletterSubscriberListResource(Resource):
    @permission_required("newsletter.manage")
    def get(self):
        query = NewsletterSubscriber.query.order_by(NewsletterSubscriber.subscribed_at.desc())
        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)
        result = paginate(query, subscriber_schema)
        return success_response(result["items"], meta=result["meta"])


api.add_resource(SubscribeResource, "/subscribe")
api.add_resource(UnsubscribeResource, "/unsubscribe")
api.add_resource(NewsletterIssueListResource, "/issues")
api.add_resource(NewsletterSubscriberListResource, "/subscribers")
