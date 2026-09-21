from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.people import Person
from app.models.taxonomy import Series
from app.schemas.people import PersonInputSchema, PersonSchema
from app.services.slugs import generate_unique_slug
from app.utils.filtering import apply_country_or_region_filter, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

people_bp = Blueprint("people", __name__)
api = Api(people_bp)

person_schema = PersonSchema()


class PersonListResource(Resource):
    def get(self):
        query = Person.query.order_by(Person.featured.desc(), Person.name)
        query = apply_country_or_region_filter(query, Person, request.args)
        query = apply_search(query, Person, request.args, ["name", "title", "industry"])
        result = paginate(query, person_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("people.manage")
    def post(self):
        data = PersonInputSchema().load(request.get_json(silent=True) or {})
        series_slugs = data.pop("series_slugs", [])
        person = Person(**{k: v for k, v in data.items() if k != "slug"})
        person.slug = data.get("slug") or generate_unique_slug(Person, data["name"])
        if series_slugs:
            person.series = Series.query.filter(Series.slug.in_(series_slugs)).all()
        db.session.add(person)
        db.session.commit()
        return success_response(person_schema.dump(person), status=201)


class PersonDetailResource(Resource):
    def get(self, slug):
        person = Person.query.filter_by(slug=slug).first()
        if person is None:
            raise ApiError("Person not found.", 404, code="not_found")
        return success_response(person_schema.dump(person))


api.add_resource(PersonListResource, "")
api.add_resource(PersonDetailResource, "/<string:slug>")
