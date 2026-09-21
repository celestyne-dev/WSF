from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.opportunity import Job
from app.models.people import Organization
from app.schemas.opportunity import JobInputSchema, JobSchema
from app.services.slugs import generate_unique_slug
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

jobs_bp = Blueprint("jobs", __name__)
api = Api(jobs_bp)

job_schema = JobSchema()


class JobListResource(Resource):
    def get(self):
        query = Job.query.filter_by(status="published").order_by(Job.featured.desc(), Job.published_date.desc())
        query = apply_country_or_region_filter(query, Job, request.args)
        query = apply_equality_filters(
            query, Job, request.args, ["industry", "employment_type", "career_level", "work_mode"]
        )
        query = apply_search(query, Job, request.args, ["title", "company_name"], param="query")
        if request.args.get("organization"):
            query = query.filter(Job.organization.has(slug=request.args["organization"]))
        if request.args.get("featured") == "true":
            query = query.filter(Job.featured.is_(True))
        result = paginate(query, job_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("jobs.manage", "jobs.create_own")
    def post(self):
        data = JobInputSchema().load(request.get_json(silent=True) or {})
        job = Job(**{k: v for k, v in data.items() if k != "slug"})
        if data.get("organization_id"):
            org = db.session.get(Organization, data["organization_id"])
            if org is None:
                raise ApiError("Organization not found.", 404, code="not_found")
        job.slug = data.get("slug") or generate_unique_slug(Job, data["title"])
        db.session.add(job)
        db.session.commit()
        return success_response(job_schema.dump(job), status=201)


class JobDetailResource(Resource):
    def get(self, slug):
        job = Job.query.filter_by(slug=slug).first()
        if job is None:
            raise ApiError("Job not found.", 404, code="not_found")
        return success_response(job_schema.dump(job))


api.add_resource(JobListResource, "")
api.add_resource(JobDetailResource, "/<string:slug>")
