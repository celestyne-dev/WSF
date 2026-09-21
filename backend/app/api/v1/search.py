from flask import Blueprint, request
from flask_restful import Api, Resource

from app.models.article import Article
from app.models.opportunity import Event, Job, Opportunity
from app.models.people import Organization, Person
from app.models.resource import Resource as ResourceModel
from app.utils.responses import success_response

search_bp = Blueprint("search", __name__)
api = Api(search_bp)

RESULT_LIMIT = 20


def _media_url(media):
    return media.public_url if media else None


class SearchResource(Resource):
    """A single cross-content search — see frontend/src/api/search.js
    (globalSearch) for the exact result shape this mirrors:
    {"query": ..., "results": [{"resultType", "title", "excerpt", "url", "image"}]}.
    """

    def get(self):
        query = (request.args.get("q") or "").strip()
        result_type = request.args.get("type", "all")

        if not query:
            return success_response({"query": query, "results": []})

        term = f"%{query}%"
        results = []

        if result_type in ("all", "articles"):
            articles = (
                Article.query.filter(Article.status == "published")
                .filter((Article.title.ilike(term)) | (Article.excerpt.ilike(term)))
                .limit(RESULT_LIMIT)
            )
            for a in articles:
                results.append(
                    {
                        "resultType": "Article",
                        "title": a.title,
                        "excerpt": a.excerpt,
                        "url": f"/{a.slug}",
                        "image": _media_url(a.hero_media),
                    }
                )

        if result_type in ("all", "people"):
            people = Person.query.filter(
                (Person.name.ilike(term)) | (Person.industry.ilike(term))
            ).limit(RESULT_LIMIT)
            for p in people:
                results.append(
                    {
                        "resultType": "Person",
                        "title": p.name,
                        "excerpt": p.short_bio,
                        "url": f"/people/{p.slug}",
                        "image": _media_url(p.photo),
                    }
                )

        if result_type in ("all", "jobs"):
            jobs = (
                Job.query.filter(Job.status == "published")
                .filter((Job.title.ilike(term)) | (Job.company_name.ilike(term)))
                .limit(RESULT_LIMIT)
            )
            for j in jobs:
                excerpt = " — ".join(filter(None, [j.company_name, j.location]))
                results.append(
                    {
                        "resultType": "Job",
                        "title": j.title,
                        "excerpt": excerpt,
                        "url": f"/jobs/{j.slug}",
                        "image": _media_url(j.logo),
                    }
                )

        if result_type in ("all", "opportunities"):
            opportunities = (
                Opportunity.query.filter(Opportunity.status == "published")
                .filter((Opportunity.title.ilike(term)) | (Opportunity.organization_name.ilike(term)))
                .limit(RESULT_LIMIT)
            )
            for o in opportunities:
                results.append(
                    {
                        "resultType": "Opportunity",
                        "title": o.title,
                        "excerpt": o.organization_name,
                        "url": f"/opportunities/{o.slug}",
                        "image": _media_url(o.logo),
                    }
                )

        if result_type in ("all", "events"):
            events = Event.query.filter(Event.title.ilike(term)).limit(RESULT_LIMIT)
            for e in events:
                results.append(
                    {
                        "resultType": "Event",
                        "title": e.title,
                        "excerpt": e.location,
                        "url": f"/events/{e.slug}",
                        "image": _media_url(e.cover_media),
                    }
                )

        if result_type in ("all", "resources"):
            resources = (
                ResourceModel.query.filter(ResourceModel.status == "published")
                .filter(ResourceModel.name.ilike(term))
                .limit(RESULT_LIMIT)
            )
            for r in resources:
                results.append(
                    {
                        "resultType": "Resource",
                        "title": r.name,
                        "excerpt": r.description,
                        "url": f"/resources/{r.slug}",
                        "image": _media_url(r.cover_media),
                    }
                )

        if result_type in ("all", "organizations"):
            organizations = Organization.query.filter(Organization.name.ilike(term)).limit(RESULT_LIMIT)
            for org in organizations:
                results.append(
                    {
                        "resultType": "Organization",
                        "title": org.name,
                        "excerpt": org.description,
                        "url": f"/organizations/{org.slug}",
                        "image": _media_url(org.logo),
                    }
                )

        return success_response({"query": query, "results": results})


api.add_resource(SearchResource, "")
