from marshmallow import fields, validate

from app.extensions import ma
from app.models.newsletter import NewsletterIssue, NewsletterSubscriber
from app.schemas.geography import CountrySchema


class NewsletterSubscriberSchema(ma.SQLAlchemyAutoSchema):
    country = fields.Nested(CountrySchema, dump_only=True)

    class Meta:
        model = NewsletterSubscriber
        load_instance = False


class NewsletterIssueSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = NewsletterIssue
        load_instance = False


class SubscribeInputSchema(ma.Schema):
    email = fields.Email(required=True)
    first_name = fields.String(required=False, allow_none=True, data_key="firstName")
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    placement = fields.String(required=False, allow_none=True)
    acquisition = fields.Dict(required=False, allow_none=True)


class UnsubscribeInputSchema(ma.Schema):
    email = fields.Email(required=True)


class NewsletterIssueInputSchema(ma.Schema):
    issue_number = fields.Integer(required=True, data_key="issueNumber")
    subject = fields.String(required=True, validate=validate.Length(min=1, max=300))
    slug = fields.String(required=False, allow_none=True)
    send_date = fields.Date(required=True, data_key="sendDate")
    featured_article_slug = fields.String(required=False, allow_none=True, data_key="featuredArticleSlug")
    summary = fields.String(required=False, allow_none=True)
