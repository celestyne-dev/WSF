"""GET /api/v1/career-outcomes — approved, consented Career Outcomes
(public, read-only, bounded). See app/services/career_outcomes.py."""
from flask import Blueprint
from flask_restful import Api, Resource

from app.services.career_outcomes import public_outcomes
from app.utils.responses import success_response

career_outcomes_bp = Blueprint("career_outcomes", __name__)
api = Api(career_outcomes_bp)


class CareerOutcomeListResource(Resource):
    def get(self):
        return success_response(public_outcomes())


api.add_resource(CareerOutcomeListResource, "")
