from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.commerce import Sponsor
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

# Public users never see salary figures on a job that opted out of salary
# disclosure — stripped from the dumped response rather than the field
# being conditionally excluded at the schema level, since visibility here
# depends on row data (salary_visible), not on who's asking.
_SALARY_FIELDS = ("salary_min", "salary_max", "currency", "salary_period")


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


def _resolve_sponsor(sponsor_id):
    if not sponsor_id:
        return None
    sponsor = db.session.get(Sponsor, sponsor_id)
    if sponsor is None:
        raise ApiError("Sponsor not found.", 404, code="not_found")
    return sponsor


def _dump_job(job, can_view_all):
    """Dumps a Job, withholding salary figures from anyone who isn't
    permitted to manage/own the listing when the poster set
    salary_visible=False.
    """
    data = job_schema.dump(job)
    if not job.salary_visible and not can_view_all:
        for field in _SALARY_FIELDS:
            data[field] = None
    return data


def _apply_fields(job, data, organization, sponsor):
    job.title = data["title"]
    job.organization = organization
    job.company_name = data.get("company_name") or (organization.name if organization else job.company_name)
    job.logo_media_id = data.get("logo_media_id")
    job.location = data.get("location")
    job.city = data.get("city")
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
    job.salary_visible = data.get("salary_visible", True)
    job.short_description = data.get("short_description")
    job.description = sanitize_content_blocks(data.get("description", []))
    job.responsibilities = [item.strip() for item in data.get("responsibilities", []) if item and item.strip()]
    job.requirements = [item.strip() for item in data.get("requirements", []) if item and item.strip()]
    job.qualifications = [item.strip() for item in data.get("qualifications", []) if item and item.strip()]
    job.skills = [item.strip() for item in data.get("skills", []) if item and item.strip()]
    job.benefits = [item.strip() for item in data.get("benefits", []) if item and item.strip()]
    job.application_url = data.get("application_url")
    job.application_email = data.get("application_email")
    job.application_instructions = data.get("application_instructions")
    job.deadline = data.get("deadline")
    job.expiry_date = data.get("expiry_date")
    job.featured = data.get("featured", False)
    job.sponsored = data.get("sponsored", False)
    job.sponsor = sponsor
    job.status = data.get("status", "published")
    job.seo = data.get("seo")
    if job.status in ("published", "scheduled") and job.published_date is None:
        job.published_date = data.get("published_date") or date.today()
    elif data.get("published_date"):
        job.published_date = data["published_date"]


def _validate_for_publish(job):
    """A published (or scheduled) job needs a real description and a real
    way to apply; a draft or a job under review may stay incomplete
    indefinitely.
    """
    errors = []
    if not job.description:
        errors.append("Add a job description before publishing.")
    if not job.application_url and not job.application_email:
        errors.append("Add an application URL or email before publishing — WSF never shows a fake Apply button.")
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


class JobListResource(Resource):
    def get(self):
        user = _current_user_or_none()
        can_manage = bool(user and user.has_permission("jobs.manage"))
        can_own = bool(user and user.has_permission("jobs.create_own"))

        query = Job.query
        if request.args.get("sort") == "deadline":
            query = query.order_by(Job.featured.desc(), Job.deadline.is_(None), Job.deadline.asc())
        else:
            query = query.order_by(Job.featured.desc(), Job.published_date.desc())

        if can_manage:
            if request.args.get("status"):
                query = query.filter(Job.status == request.args["status"])
        elif can_own:
            query = query.filter(Job.posted_by_id == user.id)
            if request.args.get("status"):
                query = query.filter(Job.status == request.args["status"])
        else:
            today = date.today()
            query = query.filter(
                or_(
                    Job.status == "published",
                    (Job.status == "scheduled") & (Job.published_date <= today),
                )
            )
            query = query.filter(or_(Job.expiry_date.is_(None), Job.expiry_date >= today))

        query = apply_country_or_region_filter(query, Job, request.args)
        query = apply_equality_filters(
            query, Job, request.args, ["industry", "employment_type", "career_level", "work_mode", "city"]
        )
        query = apply_search(query, Job, request.args, ["title", "company_name"], param="query")
        if request.args.get("organization"):
            query = query.filter(Job.organization.has(slug=request.args["organization"]))
        if request.args.get("featured") == "true":
            query = query.filter(Job.featured.is_(True))
        salary_min_param = request.args.get("salaryMin")
        if salary_min_param:
            query = query.filter(or_(Job.salary_max.is_(None), Job.salary_max >= int(salary_min_param)))
        salary_max_param = request.args.get("salaryMax")
        if salary_max_param:
            query = query.filter(or_(Job.salary_min.is_(None), Job.salary_min <= int(salary_max_param)))
        closing_within_days = request.args.get("closingWithinDays")
        if closing_within_days:
            from datetime import timedelta

            cutoff = date.today() + timedelta(days=int(closing_within_days))
            query = query.filter(Job.deadline.isnot(None), Job.deadline <= cutoff)

        result = paginate(query, schema=None)
        viewer_id = getattr(user, "id", None)
        result["items"] = [
            _dump_job(job, can_manage or (can_own and job.posted_by_id == viewer_id))
            for job in result["items"]
        ]
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        user = _can_create()
        data = JobInputSchema().load(request.get_json(silent=True) or {})
        organization = _resolve_organization(data.get("organization_id"))
        sponsor = _resolve_sponsor(data.get("sponsor_id"))

        job = Job(posted_by_id=user.id)
        if data.get("slug"):
            job.slug = validate_explicit_slug(Job, data["slug"])
        else:
            job.slug = generate_unique_slug(Job, data["title"])

        _apply_fields(job, data, organization, sponsor)
        if job.status in ("published", "scheduled"):
            _validate_for_publish(job)
        db.session.add(job)
        db.session.commit()
        return success_response(_dump_job(job, True), status=201)


class JobDetailResource(Resource):
    def get(self, slug):
        job = Job.query.filter_by(slug=slug).first()
        if job is None:
            raise ApiError("Job not found.", 404, code="not_found")
        editor = _can_edit_or_none(job)
        publicly_visible = job.status == "published" or (
            job.status == "scheduled" and job.published_date and job.published_date <= date.today()
        )
        if not publicly_visible and not editor:
            raise ApiError("Job not found.", 404, code="not_found")
        return success_response(_dump_job(job, bool(editor)))

    def put(self, slug):
        job = Job.query.filter_by(slug=slug).first()
        if job is None:
            raise ApiError("Job not found.", 404, code="not_found")
        _can_edit(job)

        data = JobInputSchema().load(request.get_json(silent=True) or {})
        organization = _resolve_organization(data.get("organization_id"))
        sponsor = _resolve_sponsor(data.get("sponsor_id"))

        if data.get("slug") and data["slug"] != job.slug:
            job.slug = validate_explicit_slug(Job, data["slug"], current_id=job.id)

        _apply_fields(job, data, organization, sponsor)
        if job.status in ("published", "scheduled"):
            _validate_for_publish(job)
        db.session.commit()
        return success_response(_dump_job(job, True))

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
            city=job.city,
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
            salary_visible=job.salary_visible,
            short_description=job.short_description,
            description=job.description,
            responsibilities=job.responsibilities,
            requirements=job.requirements,
            qualifications=job.qualifications,
            skills=job.skills,
            benefits=job.benefits,
            application_url=job.application_url,
            application_email=job.application_email,
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
        return success_response(_dump_job(copy, True), status=201)


api.add_resource(JobListResource, "")
api.add_resource(JobDetailResource, "/<string:slug>")
api.add_resource(JobDuplicateResource, "/<string:slug>/duplicate")
