from marshmallow import fields, validate

from app.extensions import ma
from app.models.community import Nomination, StorySubmission
from app.schemas.geography import CountrySchema


class StorySubmissionSchema(ma.SQLAlchemyAutoSchema):
    country = fields.Nested(CountrySchema, dump_only=True)

    class Meta:
        model = StorySubmission
        load_instance = False


class NominationSchema(ma.SQLAlchemyAutoSchema):
    country = fields.Nested(CountrySchema, dump_only=True)

    class Meta:
        model = Nomination
        load_instance = False


class StorySubmissionInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    email = fields.Email(required=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    title = fields.String(required=True, validate=validate.Length(min=1, max=300))
    excerpt = fields.String(required=False, allow_none=True)
    body = fields.String(required=False, allow_none=True)
    acquisition = fields.Dict(required=False, allow_none=True)


class NominationInputSchema(ma.Schema):
    nominee_name = fields.String(required=True, validate=validate.Length(min=1, max=200), data_key="nomineeName")
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    profession = fields.String(required=False, allow_none=True)
    organization = fields.String(required=False, allow_none=True)
    achievements = fields.String(required=False, allow_none=True)
    nominator_name = fields.String(required=True, data_key="nominatorName")
    nominator_email = fields.Email(required=True, data_key="nominatorEmail")
    relationship_to_nominee = fields.String(required=False, allow_none=True, data_key="relationship")
    category = fields.String(required=False, allow_none=True)
    acquisition = fields.Dict(required=False, allow_none=True)


class ReviewStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(["new", "reviewing", "accepted", "declined"]))
