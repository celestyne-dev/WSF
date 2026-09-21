from flask import Blueprint
from flask_restful import Api, Resource

from app.models.geography import Country
from app.schemas.geography import CountrySchema
from app.utils.responses import success_response

# Read-only, unauthenticated endpoints the public frontend needs before a
# more specific namespace exists for them (site-wide reference data).
# Article/topic/etc. listings get their own namespaces once built.
public_bp = Blueprint("public", __name__)
api = Api(public_bp)

country_schema = CountrySchema()


class CountriesResource(Resource):
    def get(self):
        countries = Country.query.order_by(Country.name).all()
        return success_response(country_schema.dump(countries, many=True))


api.add_resource(CountriesResource, "/countries")
