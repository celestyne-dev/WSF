"""Supports the private "save for later" feature (see app/models/saved_item.py
and app/api/v1/saved.py): for a given (content_type, content_id), decides
whether that target is a real, currently publicly-visible piece of content,
and if so returns the same public representation its own public API would.

A SavedItem row never carries the saved entity's own data — only a pointer.
So every read (GET /saved, GET /saved/check, and the existence check behind
POST /saved) re-resolves that pointer against the entity's own current
state through the functions below, each one reusing that type's existing
public-visibility rule and public schema rather than inventing a new one:

- Article: ArticleDetailResource.get() in app/api/v1/articles.py
  (status == "published")
- Job: JobDetailResource.get() in app/api/v1/jobs.py (published, or
  scheduled with a past-or-today published_date), plus the same
  salary-redaction _dump_job() applies there when salary_visible is False
- Opportunity: OpportunityDetailResource.get() in app/api/v1/opportunities.py
  (status == "published")
- Event: EventDetailResource.get() in app/api/v1/events.py (published,
  cancelled, postponed, or scheduled with a past-or-today published_date)
- Resource: ResourceDetailResource.get() in app/api/v1/resources.py
  (published, or scheduled with a past-or-today published_date)
- LearningProgram: LearningProgramPublicDetailResource.get() in
  app/api/v1/learning.py (status == "published")

A nonexistent id, an unsupported content_type, or a target that exists but
is no longer public all return None here — the same safe "not found"
outcome, so nothing about a hidden/draft/archived row is ever revealed
through this feature.
"""
from datetime import date

from app.extensions import db
from app.models.article import Article
from app.models.learning import LearningProgram
from app.models.opportunity import Event, Job, Opportunity
from app.models.resource import Resource
from app.schemas.article import article_summary_schema
from app.schemas.learning import learning_program_summary_schema
from app.schemas.opportunity import EventSchema, JobSchema, OpportunitySchema
from app.schemas.resource import ResourceSchema

SAVED_CONTENT_TYPES = ("article", "job", "opportunity", "resource", "event", "learning_program")

_job_schema = JobSchema()
_opportunity_schema = OpportunitySchema()
_event_schema = EventSchema()
_resource_schema = ResourceSchema()

# Mirrors jobs.py's own _dump_job(): a job that opted out of salary
# disclosure never shows salary figures to a public viewer.
_SALARY_FIELDS = ("salary_min", "salary_max", "currency", "salary_period")


def _fetch_public_article(content_id):
    article = db.session.get(Article, content_id)
    if article is None or article.status != "published":
        return None
    return article_summary_schema().dump(article)


def _fetch_public_job(content_id):
    job = db.session.get(Job, content_id)
    if job is None:
        return None
    publicly_visible = job.status == "published" or (
        job.status == "scheduled" and job.published_date is not None and job.published_date <= date.today()
    )
    if not publicly_visible:
        return None
    data = _job_schema.dump(job)
    if not job.salary_visible:
        for field in _SALARY_FIELDS:
            data[field] = None
    return data


def _fetch_public_opportunity(content_id):
    opportunity = db.session.get(Opportunity, content_id)
    if opportunity is None or opportunity.status != "published":
        return None
    return _opportunity_schema.dump(opportunity)


def _fetch_public_event(content_id):
    event = db.session.get(Event, content_id)
    if event is None:
        return None
    publicly_visible = event.status in ("published", "cancelled", "postponed") or (
        event.status == "scheduled" and event.published_date is not None and event.published_date <= date.today()
    )
    if not publicly_visible:
        return None
    return _event_schema.dump(event)


def _fetch_public_resource(content_id):
    resource = db.session.get(Resource, content_id)
    if resource is None:
        return None
    publicly_visible = resource.status == "published" or (
        resource.status == "scheduled"
        and resource.published_date is not None
        and resource.published_date <= date.today()
    )
    if not publicly_visible:
        return None
    return _resource_schema.dump(resource)


def _fetch_public_learning_program(content_id):
    program = db.session.get(LearningProgram, content_id)
    if program is None or program.status != "published":
        return None
    return learning_program_summary_schema().dump(program)


_FETCHERS = {
    "article": _fetch_public_article,
    "job": _fetch_public_job,
    "opportunity": _fetch_public_opportunity,
    "resource": _fetch_public_resource,
    "event": _fetch_public_event,
    "learning_program": _fetch_public_learning_program,
}


def fetch_public_content(content_type, content_id):
    """The entity's public representation if (content_type, content_id) is
    currently a real, publicly-visible row of that type, or None otherwise
    (nonexistent, draft/private, archived/expired, or an unsupported
    content_type).
    """
    fetcher = _FETCHERS.get(content_type)
    if fetcher is None:
        return None
    return fetcher(content_id)


def is_publicly_visible(content_type, content_id):
    """True iff (content_type, content_id) currently exists and is publicly
    visible. Used by POST /saved to validate a save target.
    """
    return fetch_public_content(content_type, content_id) is not None
