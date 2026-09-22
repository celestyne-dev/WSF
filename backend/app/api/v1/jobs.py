from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.opportunity import Job
from app.models.people import Organization
from app.schemas.opportunity import JobInputSchema, JobSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

jobs_bp = Blueprint("jobs", __name__)
api = Api(jobs_bp)
job_schema = JobSchema()


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _current_user_or_none():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    return current_user


def _can_create():
    user = _require_active_user()
    if not user.has_permission("jobs.manage", "jobs.create_own"):
        raise ApiError("You do not have permission to create jobs.", 403, code="forbidden")
    return user


def _can_edit(job):
    user = _require_active_user()
    if user.has_permission("jobs.manage"):
        return user
    if user.has_permission("jobs.create_own") and job.posted_by_id == user.id:
        return user
    raise ApiError("You do not have permission to edit this job.", 403, code="forbidden")


def _can_edit_or_none(job):
    try:
        return _can_edit(job)
    except Exception:
        return None


def _resolve_organization(organization_id):
    if not organization_id:
        return None
    org = db.session.get(Organization, organization_id)
    if org is None:
        raise ApiError("Organization not found.", 404, code="not_found")
    return org


def _apply_fields(job, data, organization):
    job.title = data["title"]
    job.organization = organization
    job.company_name = data.get("company_name") or (organization.name if organization else job.company_name)
    job.logo_media_id = data.get("logo_media_id")
    job.location = data.get("location")
    job.country_code = data.get("country_code")
    job.work_mode = data.get("work_mode")
    job.remote_scope = data.get("remote_scope") if data.get("work_mode") == "Remote" else None
    job.remote_region = data.get("remote_region") if job.remote_scope == "region" else None
    job.employment_type = data.get("employment_type")
    job.career_level = data.get("career_level")
    job.industry = data.get("industry")
    job.salary_min = data.get("salary_min")
    job.salary_max = data.get("salary_max")
    job.currency = data.get("currency")
    job.salary_period = data.get("salary_period")
    job.short_description = data.get("short_description")
    job.description = sanitize_content_blocks(data.get("description", []))
    job.application_url = data.get("application_url")
    job.application_instructions = data.get("application_instructions")
    job.deadline = data.get("deadline")
    job.expiry_date = data.get("expiry_date")
    job.featured = data.get("featured", False)
    job.sponsored = data.get("sponsored", False)
    job.status = data.get("status", "published")
    job.seo = data.get("seo")
    if job.status == "published" and job.published_date is None:
        job.published_date = data.get("published_date") or date.today()
    elif data.get("published_date"):
        job.published_date = data["published_date"]


def _validate_for_publish(job):
    """A published job needs a real description and a real way to apply;
    a draft may stay incomplete indefinitely.
    """
    errors = []
    if not job.description:
        errors.append("Add a job description before publishing.")
    if not job.application_url:
        errors.append("Add an application URL before publishing — WSF never shows a fake Apply button.")
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


class JobListResource(Resource):
    def get(self):
        user = _current_user_or_none()
        can_manage = bool(user and user.has_permission("jobs.manage"))
        can_own = bool(user and user.has_permission("jobs.create_own"))

        query = Job.query.order_by(Job.featured.desc(), Job.published_date.desc())
        if can_manage:
            if request.args.get("status"):
                query = query.filter(Job.status == request.args["status"])
        elif can_own:
            query = query.filter(Job.posted_by_id == user.id)
            if request.args.get("status"):
                query = query.filter(Job.status == request.args["status"])
        else:
            query = query.filter(Job.status == "published")
            query = query.filter(or_(Job.expiry_date.is_(None), Job.expiry_date >= date.today()))

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

    def post(self):
        user = _can_create()
        data = JobInputSchema().load(request.get_json(silent=True) or {})
        organization = _resolve_organization(data.get("organization_id"))

        job = Job(posted_by_id=user.id)
        if data.get("slug"):
            job.slug = validate_explicit_slug(Job, data["slug"])
        else:
            job.slug = generate_unique_slug(Job, data["title"])

        _apply_fields(job, data, organization)
        if job.status == "published":
            _validate_for_publish(job)
        db.session.add(job)
        db.session.commit()
        return success_response(job_schema.dump(job), status=201)


class JobDetailResource(Resource):
    def get(self, slug):
        job = Job.query.filter_by(slug=slug).first()
        if job is None:
            raise ApiError("Job not found.", 404, code="not_found")
        if job.status != "published" and not _can_edit_or_none(job):
            raise ApiError("Job not found.", 404, code="not_found")
        return success_response(job_schema.dump(job))

    def put(self, slug):
        job = Job.query.filter_by(slug=slug).first()
        if job is None:
            raise ApiError("Job not found.", 404, code="not_found")
        _can_edit(job)

        data = JobInputSchema().load(request.get_json(silent=True) or {})
        organization = _resolve_organization(data.get("organization_id"))

        if data.get("slug") and data["slug"] != job.slug:
            job.slug = validate_explicit_slug(Job, data["slug"], current_id=job.id)

        _apply_fields(job, data, organization)
        if job.status == "published":
            _validate_for_publish(job)
        db.session.commit()
        return success_response(job_schema.dump(job))

    def delete(self, slug):
        job = Job.query.filter_by(slug=slug).first()
        if job is None:
            raise ApiError("Job not found.", 404, code="not_found")
        _can_edit(job)

        db.session.delete(job)
        db.session.commit()
        return success_response({"deleted": True})


class JobDuplicateResource(Resource):
    def post(self, slug):
        job = Job.query.filter_by(slug=slug).first()
        if job is None:
            raise ApiError("Job not found.", 404, code="not_found")
        user = _can_edit(job)

        copy = Job(
            title=job.title,
            organization_id=job.organization_id,
            company_name=job.company_name,
            logo_media_id=job.logo_media_id,
            location=job.location,
            country_code=job.country_code,
            work_mode=job.work_mode,
            remote_scope=job.remote_scope,
            remote_region=job.remote_region,
            employment_type=job.employment_type,
            career_level=job.career_level,
            industry=job.industry,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            currency=job.currency,
            salary_period=job.salary_period,
            description=job.description,
            application_url=job.application_url,
            application_instructions=job.application_instructions,
            deadline=job.deadline,
            featured=False,
            sponsored=False,
            status="draft",
            seo=job.seo,
            posted_by_id=user.id,
        )
        copy.slug = generate_unique_slug(Job, f"{job.title} copy")
        db.session.add(copy)
        db.session.commit()
        return success_response(job_schema.dump(copy), status=201)


api.add_resource(JobListResource, "")
api.add_resource(JobDetailResource, "/<string:slug>")
api.add_resource(JobDuplicateResource, "/<string:slug>/duplicate")
