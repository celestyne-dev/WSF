"""AI Search / GEO Phase 3B3 — the representative public items each hub/
listing page's server prerender shows (app/services/prerender.py's
render_hub_prerender / render_homepage_prerender).

Every fetcher mirrors that hub's own PUBLIC list endpoint: the same
anonymous visibility filter and the same default ordering, capped at a
small representative batch (HUB_BATCH_SIZE) — never every paginated
result, never a query-string permutation. Each item is built with the
SAME anonymous builder/schema the public API returns, followed by the
public linked-entity filtering in app/services/public_visibility.py, so
a hub can never show more than an anonymous API caller already gets
(no unpublished linked People/Organizations/Authors/Topics/Tags/Series,
no Sponsor internals, no Resource delivery data, no Learning
curriculum, no subscriber/applicant/attendee data).
"""
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

HUB_BATCH_SIZE = 8


def jobs_hub(limit=HUB_BATCH_SIZE):
    from app.api.v1.jobs import build_public_job_payload
    from app.models.opportunity import Job
    from app.services.job_access import is_job_publicly_visible

    rows = (
        Job.query.options(selectinload(Job.organization))
        .filter(Job.status.in_(["published", "scheduled"]))
        .order_by(Job.featured.desc(), Job.published_date.desc())
        .limit(limit * 3)
        .all()
    )
    return [build_public_job_payload(j, None, detail=False) for j in rows if is_job_publicly_visible(j)][:limit]


def opportunities_hub(limit=HUB_BATCH_SIZE):
    from app.api.v1.opportunities import build_public_opportunity_payload
    from app.models.opportunity import Opportunity

    rows = (
        Opportunity.query.options(selectinload(Opportunity.organization), selectinload(Opportunity.topics))
        .filter(Opportunity.status == "published")
        .filter(or_(Opportunity.expiry_date.is_(None), Opportunity.expiry_date >= date.today()))
        .order_by(Opportunity.featured.desc(), Opportunity.deadline)
        .limit(limit)
        .all()
    )
    return [build_public_opportunity_payload(o, None, detail=False) for o in rows]


def events_hub(limit=HUB_BATCH_SIZE):
    """Upcoming publicly visible events — the public list's default
    (it shows upcoming events unless `when=past` is asked for)."""
    from app.extensions import db
    from app.models.opportunity import Event
    from app.schemas.opportunity import EventSchema
    from app.services.event_registrations import is_event_publicly_visible
    from app.services.public_visibility import public_event_dump

    today = date.today()
    rows = (
        Event.query.options(selectinload(Event.organizer), selectinload(Event.speakers), selectinload(Event.sponsors))
        .filter(Event.status.in_(["published", "cancelled", "postponed", "scheduled"]))
        # coalesce(end_date, date) >= today — the public list's upcoming default.
        .filter(db.func.coalesce(Event.end_date, Event.date) >= today)
        .order_by(Event.featured.desc(), Event.date)
        .limit(limit * 3)
        .all()
    )
    schema = EventSchema()
    return [public_event_dump(schema.dump(e), e) for e in rows if is_event_publicly_visible(e)][:limit]


def resources_hub(limit=HUB_BATCH_SIZE):
    from app.api.v1.resources import build_public_resource_payload
    from app.models.resource import Resource

    rows = (
        Resource.query.options(
            selectinload(Resource.images), selectinload(Resource.topics), selectinload(Resource.tags),
            selectinload(Resource.author), selectinload(Resource.sponsor), selectinload(Resource.cover_media),
        )
        .filter(Resource.status.in_(["published", "scheduled"]))
        .order_by(Resource.featured.desc(), Resource.published_date.desc())
        .limit(limit * 3)
        .all()
    )
    return [build_public_resource_payload(r, None) for r in rows if r.is_publicly_visible()][:limit]


def learning_hub(limit=HUB_BATCH_SIZE):
    """Catalog summaries only — learning_program_summary_schema excludes
    modules/curriculum; instructors/provider/topics are publicly filtered."""
    from app.models.learning import LearningProgram
    from app.schemas.learning import learning_program_summary_schema
    from app.services.public_visibility import public_learning_dump

    rows = (
        LearningProgram.query.filter_by(status="published")
        .order_by(LearningProgram.featured.desc(), LearningProgram.created_at.desc())
        .limit(limit)
        .all()
    )
    schema = learning_program_summary_schema()
    return [public_learning_dump(schema.dump(p), p) for p in rows]


def people_hub(limit=HUB_BATCH_SIZE):
    from app.models.people import Person
    from app.schemas.people import PersonSchema
    from app.services.public_visibility import public_person_dump

    rows = (
        Person.query.options(selectinload(Person.organization), selectinload(Person.series))
        .filter(Person.status == "published")
        .order_by(Person.featured.desc(), Person.name)
        .limit(limit)
        .all()
    )
    schema = PersonSchema()
    return [public_person_dump(schema.dump(p), p) for p in rows]


def organizations_hub(limit=HUB_BATCH_SIZE):
    from app.models.people import Organization
    from app.schemas.people import OrganizationSchema

    rows = (
        Organization.query.filter(Organization.status == "published")
        .order_by(Organization.featured.desc(), Organization.name)
        .limit(limit)
        .all()
    )
    # people_count runs one COUNT per row and isn't shown in the hub.
    return OrganizationSchema(many=True, exclude=("people_count",)).dump(rows)


def authors_hub(limit=HUB_BATCH_SIZE):
    from app.models.people import Author
    from app.schemas.people import AuthorSchema
    from app.services.public_visibility import public_author_dump

    rows = (
        Author.query.options(selectinload(Author.topics))
        .filter(Author.status == "active")
        .order_by(Author.name)
        .limit(limit)
        .all()
    )
    schema = AuthorSchema(exclude=("article_count",))
    return [public_author_dump(schema.dump(a), a) for a in rows]


def topics_hub(limit=HUB_BATCH_SIZE * 3):
    """Topics are the primary crawl-discovery hub, and the set is small and
    curated — so a larger cap than other hubs."""
    from app.models.taxonomy import Topic
    from app.schemas.taxonomy import TopicSchema

    rows = Topic.query.filter_by(status="published").order_by(Topic.sort_order, Topic.name).limit(limit).all()
    return TopicSchema(many=True, exclude=("article_count",)).dump(rows)


def series_hub(limit=HUB_BATCH_SIZE * 2):
    from app.models.taxonomy import Series
    from app.schemas.taxonomy import SeriesSchema

    rows = Series.query.filter_by(status="published").order_by(Series.sort_order, Series.name).limit(limit).all()
    return SeriesSchema(many=True, exclude=("article_count",)).dump(rows)


def directory_hub(limit=HUB_BATCH_SIZE):
    from app.models.directory import DirectoryListing
    from app.models.people import Organization
    from app.schemas.directory import DirectoryListingPublicSchema

    rows = (
        DirectoryListing.query.join(Organization, DirectoryListing.organization_id == Organization.id)
        .options(selectinload(DirectoryListing.categories))
        .filter(DirectoryListing.status == "published", Organization.status == "published")
        .order_by(DirectoryListing.featured.desc(), DirectoryListing.published_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    return DirectoryListingPublicSchema(many=True).dump(rows)


def shop_hub(limit=HUB_BATCH_SIZE):
    from app.api.v1.products import _dump_product
    from app.models.commerce import Product

    rows = (
        Product.query.filter(Product.status.in_(["active", "unavailable"]))
        .order_by(Product.featured.desc(), Product.published_date.desc())
        .limit(limit)
        .all()
    )
    return [_dump_product(p, False) for p in rows]


def newsletter_hub(limit=HUB_BATCH_SIZE):
    from app.models.newsletter import NewsletterIssue
    from app.schemas.newsletter import NewsletterIssuePublicSchema

    rows = (
        NewsletterIssue.query.filter(NewsletterIssue.status == "sent")
        .order_by(NewsletterIssue.sent_at.desc())
        .limit(limit)
        .all()
    )
    # content is the full issue body — not needed for an archive list.
    return NewsletterIssuePublicSchema(many=True, exclude=("content",)).dump(rows)


def circle_plans_hub():
    """The anonymous CirclePlan list (status == "active"), pre-sorted the
    same way CirclePlanListResource sorts it."""
    from app.api.v1.circle import build_public_plan_payload
    from app.models.circle import CirclePlan

    rows = (
        CirclePlan.query.filter(CirclePlan.status == "active")
        .order_by(CirclePlan.featured.desc(), CirclePlan.display_order, CirclePlan.id)
        .all()
    )
    return [build_public_plan_payload(p) for p in rows]


def mentorship_programs_hub():
    """PublicProgramListResource's exact rule and order."""
    from app.api.v1.mentorship import build_public_program_payload
    from app.models.mentorship import MentorshipProgram

    rows = (
        MentorshipProgram.query.filter_by(public_visible=True)
        .filter(MentorshipProgram.status.notin_(("draft", "archived")))
        .order_by(MentorshipProgram.application_opens_at.desc().nullslast(), MentorshipProgram.created_at.desc())
        .all()
    )
    return [build_public_program_payload(p) for p in rows]


# --- homepage -------------------------------------------------------------------


def _published_articles(query, limit):
    from app.models.article import Article
    from app.schemas.article import article_summary_schema

    rows = query.filter(Article.status == "published").order_by(Article.publish_date.desc()).limit(limit).all()
    return article_summary_schema(many=True).dump(rows)


def _articles_by_slugs(slugs, limit):
    """Editor-picked Articles, in the picked order, published only (what
    FeaturedStoriesModule/HeroModule's fetchRelatedArticles returns)."""
    from app.models.article import Article
    from app.schemas.article import article_summary_schema

    slugs = [s for s in (slugs or []) if isinstance(s, str) and s][:limit]
    if not slugs:
        return []
    by_slug = {a.slug: a for a in Article.query.filter(Article.slug.in_(slugs), Article.status == "published").all()}
    return article_summary_schema(many=True).dump([by_slug[s] for s in slugs if s in by_slug])


def _item_count(module, default):
    value = (module.config or {}).get("itemCount")
    return value if isinstance(value, int) and 0 < value <= 12 else default


def homepage_sections(modules, lead_article):
    """One entry per ENABLED, configured homepage module, in builder order,
    resolved the same way that module's own React component does (see
    frontend/src/components/home/*Module.jsx). A module that resolves to
    nothing public is omitted — never rendered as an empty shell."""
    from app.models.article import Article
    from app.models.opportunity import Job, Opportunity
    from app.models.people import Person
    from app.models.resource import Resource
    from app.models.taxonomy import Series, Topic
    from app.schemas.article import article_summary_schema
    from app.schemas.people import PersonSchema
    from app.services.public_visibility import public_person_dump

    sections = []
    for module in modules:
        config = module.config or {}
        base = {"type": module.type, "heading": module.heading, "subheading": module.subheading}
        if module.type == "hero":
            secondary = _articles_by_slugs(config.get("secondaryArticleSlugs"), 4)
            if lead_article is not None:
                # HeroModule.jsx's lead branch renders only the primary CTA.
                ctas = [(module.cta_label, module.cta_url)] if module.cta_label and module.cta_url else []
                sections.append({**base, "lead": article_summary_schema().dump(lead_article), "ctas": ctas, "articles": secondary})
            elif module.heading:
                ctas = [(module.cta_label, module.cta_url), (module.secondary_cta_label, module.secondary_cta_url)]
                sections.append({**base, "ctas": [(label, url) for label, url in ctas if label and url], "articles": secondary})
        elif module.type == "featured_stories":
            articles = _articles_by_slugs(config.get("articleSlugs"), _item_count(module, 8))
            if articles:
                sections.append({**base, "articles": articles})
        elif module.type == "latest_stories":
            articles = _published_articles(Article.query, _item_count(module, 8))
            if articles:
                sections.append({**base, "articles": articles})
        elif module.type == "featured_woman":
            person = Person.query.filter_by(slug=config.get("personSlug"), status="published").first() if config.get("personSlug") else None
            if person is not None:
                sections.append({**base, "person": public_person_dump(PersonSchema().dump(person), person)})
        elif module.type in ("series_feature", "topic_collection"):
            model, key, rel = (Series, "seriesSlug", "series") if module.type == "series_feature" else (Topic, "topicSlug", "topic")
            term = model.query.filter_by(slug=config.get(key), status="published").first() if config.get(key) else None
            if term is not None:
                if rel == "series":
                    query = Article.query.filter(Article.series_id == term.id)
                else:
                    query = Article.query.filter(Article.topics.any(id=term.id))
                sections.append({
                    **base, "term": {"kind": rel, "slug": term.slug, "name": term.name,
                                     "description": getattr(term, "description", None)},
                    "articles": _published_articles(query, _item_count(module, 3)),
                })
        elif module.type in ("jobs", "opportunities", "events", "resources"):
            count = _item_count(module, 4 if module.type == "jobs" else 3)
            items = _featured_hub_items(module.type, count, Job, Opportunity, Resource)
            if items:
                sections.append({**base, "items": items})
        elif module.type in ("newsletter", "community_cta", "mentorship_cta", "editorial_callout") and module.heading:
            ctas = [(module.cta_label, module.cta_url), (module.secondary_cta_label, module.secondary_cta_url)]
            sections.append({**base, "ctas": [(label, url) for label, url in ctas if label and url]})
        # partners / sponsor_placement: dynamic commercial modules resolved
        # client-side from their own eligibility rules — not prerendered.
    return sections


def _featured_hub_items(kind, count, Job, Opportunity, Resource):
    """JobsModule/OpportunitiesModule/ResourcesModule fetch `featured: true`;
    EventsModule fetches the upcoming list."""
    if kind == "events":
        return events_hub(limit=count)
    builders = {"jobs": jobs_hub, "opportunities": opportunities_hub, "resources": resources_hub}
    items = builders[kind](limit=count * 3)
    return [item for item in items if item.get("featured")][:count]
