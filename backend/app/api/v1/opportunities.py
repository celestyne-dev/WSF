from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.opportunity import Opportunity
from app.models.taxonomy import Topic
from app.schemas.opportunity import OpportunityInputSchema, OpportunitySchema
from app.services.slugs import generate_unique_slug
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

opportunities_bp = Blueprint("opportunities", __name__)
api = Api(opportunities_bp)

opportunity_schema = OpportunitySchema()


class OpportunityListResource(Resource):
    def get(self):
        query = Opportunity.query.filter_by(status="published").order_by(
            Opportunity.featured.desc(), Opportunity.deadline
        )
        opp_type = request.args.get("type")
        if opp_type:
            query = query.filter(Opportunity.type == opp_type)
        country = request.args.get("country")
        if country:
            query = query.filter(Opportunity.countries_eligible.any(code=country.upper()))
        region = request.args.get("region")
        if region:
            from app.models.geography import Country

            query = query.filter(Opportunity.countries_eligible.any(Country.region == region))
        topic = request.args.get("topic")
        if topic:
            query = query.filter(Opportunity.topics.any(slug=topic))
        query = apply_search(query, Opportunity, request.args, ["title", "organization_name"], param="query")

        result = paginate(query, opportunity_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("opportunities.manage")
    def post(self):
        data = OpportunityInputSchema().load(request.get_json(silent=True) or {})

        from app.models.geography import Country

        codes = data.pop("countries_eligible", [])
        countries = Country.query.filter(Country.code.in_([c.upper() for c in codes])).all()
        if len(countries) != len(set(codes)):
            found = {c.code for c in countries}
            missing = [c for c in codes if c.upper() not in found]
            raise ApiError(f'Country "{missing[0]}" not found.', 404, code="not_found")

        topic_slugs = data.pop("topic_slugs", [])
        topics = Topic.query.filter(Topic.slug.in_(topic_slugs)).all()
        if len(topics) != len(set(topic_slugs)):
            found = {t.slug for t in topics}
            missing = [s for s in topic_slugs if s not in found]
            raise ApiError(f'Topic "{missing[0]}" not found.', 404, code="not_found")

        opportunity = Opportunity(**{k: v for k, v in data.items() if k != "slug"})
        opportunity.slug = data.get("slug") or generate_unique_slug(Opportunity, data["title"])
        opportunity.countries_eligible = countries
        opportunity.topics = topics
        db.session.add(opportunity)
        db.session.commit()
        return success_response(opportunity_schema.dump(opportunity), status=201)


class OpportunityDetailResource(Resource):
    def get(self, slug):
        opportunity = Opportunity.query.filter_by(slug=slug).first()
        if opportunity is None:
            raise ApiError("Opportunity not found.", 404, code="not_found")
        return success_response(opportunity_schema.dump(opportunity))


api.add_resource(OpportunityListResource, "")
api.add_resource(OpportunityDetailResource, "/<string:slug>")
