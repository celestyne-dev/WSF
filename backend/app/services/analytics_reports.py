"""Server-side aggregation for the admin Analytics Dashboard — see
api/v1/analytics.py for the thin, permission-gated routes that call these
functions. Every number here is a real SQL count/group-by against
AnalyticsEvent (first-party, already-captured) and the platform's own
tables (NewsletterSubscriber, Order, Member, MentorshipApplication, ...).
Nothing is fabricated: a metric with no underlying data returns 0 or an
empty list, never an invented placeholder (see spec section 3).

Design: each report function takes a `start`/`end` date (inclusive) and
does its own bounded, server-side SQL aggregation — never fetches raw
event rows into Python to sum/group them there (spec section 52).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.extensions import db
from app.models.analytics import AnalyticsEvent
from app.models.article import Article
from app.models.commerce import Order, PartnershipInquiry, Sponsor
from app.models.community import Member
from app.models.mentorship import MentorshipApplication, MentorshipMatch
from app.models.newsletter import NewsletterSubscriber
from app.models.nominations import Nomination
from app.models.opportunity import Event, Job, Opportunity
from app.models.resource import Resource
from app.models.submissions import StorySubmission
from app.models.taxonomy import Topic

# Content-view event families, reused across Overview/Content/Careers so
# "total content views" always means the same set of events everywhere.
CONTENT_VIEW_EVENTS = (
    "article_view",
    "job_view",
    "opportunity_view",
    "event_view",
    "resource_view",
    "product_view",
)

MAX_TOP_ROWS = 20
CANDIDATE_SLUG_LIMIT = 500  # bounds the GROUP BY before joining to content tables


def date_range_bounds(start, end):
    """Inclusive `date` bounds -> a [start, end) UTC datetime range for
    filtering AnalyticsEvent.created_at. `end` is treated as inclusive of
    that whole calendar day.
    """
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    return start_dt, end_dt


def previous_period(start, end):
    """The immediately-preceding period of the same length — for
    "last 30 days vs previous 30 days" comparisons (spec section 14).
    """
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return prev_start, prev_end


def _pct_change(current, previous):
    """None when the comparison is meaningless (no previous-period data)
    — never a fabricated +100% for a zero baseline (spec section 14).
    """
    if previous in (0, None):
        return None
    return round((current - previous) / previous * 100, 1)


def _event_count(names, start, end, extra=()):
    start_dt, end_dt = date_range_bounds(start, end)
    if isinstance(names, str):
        names = (names,)
    query = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_name.in_(names),
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at < end_dt,
    )
    for clause in extra:
        query = query.filter(clause)
    return query.count()


def get_overview(start, end, compare=False):
    metrics = {
        "contentViews": _event_count(CONTENT_VIEW_EVENTS, start, end),
        "articleViews": _event_count("article_view", start, end),
        "searchesPerformed": _event_count("search_performed", start, end),
        "newsletterSignups": _newsletter_signups(start, end),
        "jobViews": _event_count("job_view", start, end),
        "opportunityViews": _event_count("opportunity_view", start, end),
        "eventViews": _event_count("event_view", start, end),
        "resourceDownloads": _event_count("resource_download_success", start, end),
    }

    comparison = None
    if compare:
        prev_start, prev_end = previous_period(start, end)
        prev_metrics = {
            "contentViews": _event_count(CONTENT_VIEW_EVENTS, prev_start, prev_end),
            "articleViews": _event_count("article_view", prev_start, prev_end),
            "searchesPerformed": _event_count("search_performed", prev_start, prev_end),
            "newsletterSignups": _newsletter_signups(prev_start, prev_end),
            "jobViews": _event_count("job_view", prev_start, prev_end),
            "opportunityViews": _event_count("opportunity_view", prev_start, prev_end),
            "eventViews": _event_count("event_view", prev_start, prev_end),
            "resourceDownloads": _event_count("resource_download_success", prev_start, prev_end),
        }
        comparison = {
            "previousStart": prev_start.isoformat(),
            "previousEnd": prev_end.isoformat(),
            "changes": {k: _pct_change(metrics[k], prev_metrics[k]) for k in metrics},
        }

    audience_by_source = _audience_by_source(start, end)

    return {"metrics": metrics, "comparison": comparison, "audienceBySource": audience_by_source}


def _newsletter_signups(start, end):
    start_dt, end_dt = date_range_bounds(start, end)
    return NewsletterSubscriber.query.filter(
        NewsletterSubscriber.subscribed_at >= start_dt, NewsletterSubscriber.subscribed_at < end_dt
    ).count()


def _audience_by_source(start, end):
    """Referral-source breakdown from the acquisition context every
    tracked event already carries (frontend/src/utils/analytics.js) —
    real captured UTM/referrer data, never an inferred/guessed source
    (spec section 41-43).
    """
    start_dt, end_dt = date_range_bounds(start, end)
    # COALESCE before GROUP BY — otherwise a NULL acquisition and a real
    # {"source": "direct"} acquisition become two separate SQL groups
    # that both display as "direct", double-counting (and duplicate-
    # keying) the same bucket in the UI.
    source_col = func.coalesce(AnalyticsEvent.acquisition.op("->>")("source"), "direct").label("source")
    rows = (
        db.session.query(source_col, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.created_at >= start_dt, AnalyticsEvent.created_at < end_dt)
        .group_by(source_col)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(10)
        .all()
    )
    return [{"source": source, "count": count} for source, count in rows]


def get_trend(start, end):
    """One clean trend series (spec section 15): total content views vs.
    Article views specifically, daily for ranges up to 60 days and weekly
    beyond that so a year-long range doesn't return hundreds of points.
    """
    start_dt, end_dt = date_range_bounds(start, end)
    granularity = "day" if (end - start).days <= 60 else "week"
    bucket = func.date_trunc(granularity, AnalyticsEvent.created_at).label("bucket")

    rows = (
        db.session.query(bucket, AnalyticsEvent.event_name, func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.event_name.in_(CONTENT_VIEW_EVENTS),
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
        )
        .group_by(bucket, AnalyticsEvent.event_name)
        .order_by(bucket)
        .all()
    )

    series = {}
    for bucket_dt, event_name, count in rows:
        key = bucket_dt.date().isoformat()
        entry = series.setdefault(key, {"date": key, "contentViews": 0, "articleViews": 0})
        entry["contentViews"] += count
        if event_name == "article_view":
            entry["articleViews"] += count

    return {"granularity": granularity, "points": [series[k] for k in sorted(series)]}


def get_content_performance(start, end, sort="views", page=1, per_page=20):
    """Top Articles by real article_view events in the selected range
    (spec section 16-17) — never a fabricated engagement score. Views are
    counted from AnalyticsEvent, not inferred from anything else.
    """
    start_dt, end_dt = date_range_bounds(start, end)
    slug_col = AnalyticsEvent.payload.op("->>")("articleSlug").label("slug")
    view_rows = (
        db.session.query(slug_col, func.count(AnalyticsEvent.id).label("views"))
        .filter(
            AnalyticsEvent.event_name == "article_view",
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
            slug_col.isnot(None),
        )
        .group_by(slug_col)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(CANDIDATE_SLUG_LIMIT)
        .all()
    )
    views_by_slug = {slug: views for slug, views in view_rows if slug}
    total_views = sum(views_by_slug.values())

    articles = (
        Article.query.filter(Article.slug.in_(views_by_slug.keys()))
        .with_entities(Article.slug, Article.title, Article.publish_date, Article.series_id, Article.id)
        .all()
    )
    topic_by_article_id = _first_topic_names([a.id for a in articles])

    rows = [
        {
            "slug": a.slug,
            "title": a.title,
            "url": f"/{a.slug}",
            "views": views_by_slug.get(a.slug, 0),
            "publishedDate": a.publish_date.isoformat() if a.publish_date else None,
            "topic": topic_by_article_id.get(a.id),
        }
        for a in articles
    ]
    # A slug with views but no matching Article row means the Article was
    # later deleted — the historical view count stays valid; the row just
    # can't link anywhere (spec section 69: never crash, never drop the
    # aggregate total).
    known_slugs = {r["slug"] for r in rows}
    for slug, views in views_by_slug.items():
        if slug not in known_slugs:
            rows.append({"slug": slug, "title": "Deleted content", "url": None, "views": views, "publishedDate": None, "topic": None})

    reverse = sort != "date_asc"
    sort_key = (lambda r: r["publishedDate"] or "") if sort in ("date", "date_asc") else (lambda r: r["views"])
    rows.sort(key=sort_key, reverse=reverse)

    start_idx = (page - 1) * per_page
    page_rows = rows[start_idx : start_idx + per_page]

    return {"totalViews": total_views, "totalArticles": len(rows), "page": page, "perPage": per_page, "results": page_rows}


def _first_topic_names(article_ids):
    if not article_ids:
        return {}
    rows = (
        db.session.query(Article.id, Topic.name)
        .join(Article.topics)
        .filter(Article.id.in_(article_ids))
        .all()
    )
    result = {}
    for article_id, topic_name in rows:
        result.setdefault(article_id, topic_name)
    return result


def get_topic_series_performance(start, end):
    """Aggregate views by CURRENT Topic/Series associations only — if an
    Article's taxonomy changed since a historical view, that view counts
    toward the Article's taxonomy today, not whatever it was at view time
    (no historical dimension snapshot exists — spec section 18 asks this
    to be documented, not solved with a warehouse).
    """
    start_dt, end_dt = date_range_bounds(start, end)
    slug_col = AnalyticsEvent.payload.op("->>")("articleSlug").label("slug")
    view_rows = (
        db.session.query(slug_col, func.count(AnalyticsEvent.id).label("views"))
        .filter(
            AnalyticsEvent.event_name == "article_view",
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
            slug_col.isnot(None),
        )
        .group_by(slug_col)
        .limit(CANDIDATE_SLUG_LIMIT)
        .all()
    )
    views_by_slug = {slug: views for slug, views in view_rows if slug}
    if not views_by_slug:
        return {"topics": [], "series": []}

    articles = Article.query.filter(Article.slug.in_(views_by_slug.keys())).all()

    topic_totals = {}
    series_totals = {}
    for a in articles:
        views = views_by_slug.get(a.slug, 0)
        for topic in a.topics:
            topic_totals[topic.name] = topic_totals.get(topic.name, 0) + views
        if a.series:
            series_totals[a.series.name] = series_totals.get(a.series.name, 0) + views

    topics = sorted(({"topic": k, "views": v} for k, v in topic_totals.items()), key=lambda r: -r["views"])[:MAX_TOP_ROWS]
    series = sorted(({"series": k, "views": v} for k, v in series_totals.items()), key=lambda r: -r["views"])[:MAX_TOP_ROWS]
    return {"topics": topics, "series": series}


def get_search_analytics(start, end):
    start_dt, end_dt = date_range_bounds(start, end)
    total_searches = _event_count("search_performed", start, end)
    result_clicks = _event_count("search_result_click", start, end)

    result_count_col = AnalyticsEvent.payload.op("->>")("resultCount")
    zero_result_searches = (
        AnalyticsEvent.query.filter(
            AnalyticsEvent.event_name == "search_performed",
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
            result_count_col == "0",
        ).count()
    )

    query_col = AnalyticsEvent.payload.op("->>")("query").label("query")
    top_queries_rows = (
        db.session.query(query_col, func.count(AnalyticsEvent.id).label("count"), func.max(AnalyticsEvent.created_at).label("lastSearched"))
        .filter(
            AnalyticsEvent.event_name == "search_performed",
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
            query_col.isnot(None),
            query_col != "",
        )
        .group_by(query_col)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(MAX_TOP_ROWS)
        .all()
    )
    top_queries = [
        {"query": q, "count": c, "lastSearched": last.isoformat() if last else None} for q, c, last in top_queries_rows
    ]

    result_type_col = AnalyticsEvent.payload.op("->>")("resultType").label("resultType")
    clicks_by_type_rows = (
        db.session.query(result_type_col, func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.event_name == "search_result_click",
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
        )
        .group_by(result_type_col)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .all()
    )
    clicks_by_result_type = [{"resultType": t or "unknown", "count": c} for t, c in clicks_by_type_rows]

    return {
        "totalSearches": total_searches,
        "zeroResultSearches": zero_result_searches,
        "resultClicks": result_clicks,
        "topQueries": top_queries,
        "clicksByResultType": clicks_by_result_type,
    }


def get_newsletter_analytics(start, end):
    start_dt, end_dt = date_range_bounds(start, end)
    new_subscribers = _newsletter_signups(start, end)
    unsubscribes = NewsletterSubscriber.query.filter(
        NewsletterSubscriber.unsubscribed_at >= start_dt, NewsletterSubscriber.unsubscribed_at < end_dt
    ).count()
    active_total = NewsletterSubscriber.query.filter_by(status="active").count()

    granularity = "day" if (end - start).days <= 60 else "week"
    bucket = func.date_trunc(granularity, NewsletterSubscriber.subscribed_at).label("bucket")
    growth_rows = (
        db.session.query(bucket, func.count(NewsletterSubscriber.id))
        .filter(NewsletterSubscriber.subscribed_at >= start_dt, NewsletterSubscriber.subscribed_at < end_dt)
        .group_by(bucket)
        .order_by(bucket)
        .all()
    )
    growth_trend = [{"date": b.date().isoformat(), "newSubscribers": c} for b, c in growth_rows]

    return {
        "newSubscribers": new_subscribers,
        "unsubscribes": unsubscribes,
        "activeTotal": active_total,
        "growthTrend": growth_trend,
        "issueViews": _event_count("newsletter_archive_view", start, end),
    }


def _top_by_view_event(event_name, model, slug_payload_key, start, end, title_col, url_prefix):
    """Shared helper for Jobs/Opportunities/Events/Resources: group a
    *_view event by its slug, join back to the real content row so a
    deleted item still reports its historical view count without
    crashing (spec section 69), and return a bounded top-N list.
    """
    start_dt, end_dt = date_range_bounds(start, end)
    slug_col = AnalyticsEvent.payload.op("->>")(slug_payload_key).label("slug")
    view_rows = (
        db.session.query(slug_col, func.count(AnalyticsEvent.id).label("views"))
        .filter(
            AnalyticsEvent.event_name == event_name,
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
            slug_col.isnot(None),
        )
        .group_by(slug_col)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(MAX_TOP_ROWS)
        .all()
    )
    total_views = sum(v for _, v in view_rows)
    slugs = [s for s, _ in view_rows if s]
    rows_by_slug = {row.slug: row for row in model.query.filter(model.slug.in_(slugs)).all()} if slugs else {}

    results = []
    for slug, views in view_rows:
        row = rows_by_slug.get(slug)
        results.append(
            {
                "slug": slug,
                "title": getattr(row, title_col.name) if row else "Deleted content",
                "url": f"{url_prefix}/{slug}" if row else None,
                "views": views,
            }
        )
    return total_views, results


def get_careers_analytics(start, end):
    """Jobs/Opportunities/Events/Resources — views are real; apply/
    registration link clicks are CTA clicks, never labeled as completed
    applications/registrations (spec section 24-27).
    """
    job_total_views, top_jobs = _top_by_view_event("job_view", Job, "jobSlug", start, end, Job.title, "/jobs")
    opp_total_views, top_opps = _top_by_view_event(
        "opportunity_view", Opportunity, "opportunitySlug", start, end, Opportunity.title, "/opportunities"
    )
    event_total_views, top_events = _top_by_view_event("event_view", Event, "eventSlug", start, end, Event.title, "/events")
    resource_total_views, top_resources = _top_by_view_event(
        "resource_view", Resource, "resourceSlug", start, end, Resource.name, "/resources"
    )

    return {
        "jobs": {
            "views": job_total_views,
            "applyClicks": _event_count("job_apply_click", start, end),
            "topJobs": top_jobs,
        },
        "opportunities": {
            "views": opp_total_views,
            "applyClicks": _event_count("opportunity_apply_click", start, end),
            "topOpportunities": top_opps,
        },
        "events": {
            "views": event_total_views,
            "registrationClicks": _event_count("event_registration_click", start, end),
            "topEvents": top_events,
        },
        "resources": {
            "views": resource_total_views,
            "downloads": _event_count("resource_download_success", start, end),
            "downloadClicks": _event_count(("resource_download_click", "resource_external_click"), start, end),
            "topResources": top_resources,
        },
    }


def get_community_programs_analytics(start, end):
    """Aggregate-only counts (spec section 31-34) — never a member/
    mentee/nominee identity, never submission/nomination text.
    """
    start_dt, end_dt = date_range_bounds(start, end)

    joins_in_range = Member.query.filter(Member.created_at >= start_dt, Member.created_at < end_dt).count()
    active_members = Member.query.filter_by(status="active").count()
    countries_represented = (
        db.session.query(func.count(func.distinct(Member.country_code))).filter(Member.country_code.isnot(None)).scalar() or 0
    )

    mentorship_apps = MentorshipApplication.query.filter(
        MentorshipApplication.submitted_at >= start_dt, MentorshipApplication.submitted_at < end_dt
    )
    mentor_applications = mentorship_apps.filter_by(role="mentor").count()
    mentee_applications = mentorship_apps.filter_by(role="mentee").count()
    active_matches = MentorshipMatch.query.filter(MentorshipMatch.status.in_(["proposed", "confirmed", "active", "paused"])).count()
    completed_matches = MentorshipMatch.query.filter(
        MentorshipMatch.status == "completed", MentorshipMatch.created_at >= start_dt, MentorshipMatch.created_at < end_dt
    ).count()

    submissions_received = StorySubmission.query.filter(
        StorySubmission.submitted_at >= start_dt, StorySubmission.submitted_at < end_dt
    ).count()
    submissions_approved = StorySubmission.query.filter(
        StorySubmission.status.in_(["approved", "converted", "published"]),
        StorySubmission.submitted_at >= start_dt,
        StorySubmission.submitted_at < end_dt,
    ).count()
    submissions_published = StorySubmission.query.filter(
        StorySubmission.status == "published",
        StorySubmission.submitted_at >= start_dt,
        StorySubmission.submitted_at < end_dt,
    ).count()

    nominations_received = Nomination.query.filter(
        Nomination.submitted_at >= start_dt, Nomination.submitted_at < end_dt
    ).count()
    nominations_shortlisted = Nomination.query.filter(
        Nomination.status.in_(["shortlisted", "approved", "in_editorial", "published"]),
        Nomination.submitted_at >= start_dt,
        Nomination.submitted_at < end_dt,
    ).count()
    nominations_converted = Nomination.query.filter(
        Nomination.status.in_(["in_editorial", "published"]),
        Nomination.submitted_at >= start_dt,
        Nomination.submitted_at < end_dt,
    ).count()

    return {
        "community": {"joins": joins_in_range, "activeMembers": active_members, "countriesRepresented": countries_represented},
        "mentorship": {
            "mentorApplications": mentor_applications,
            "menteeApplications": mentee_applications,
            "activeMatches": active_matches,
            "completedMatches": completed_matches,
        },
        "storySubmissions": {
            "received": submissions_received,
            "approved": submissions_approved,
            "published": submissions_published,
        },
        "nominations": {
            "received": nominations_received,
            "shortlisted": nominations_shortlisted,
            "converted": nominations_converted,
        },
    }


def get_commercial_analytics(start, end):
    """Sponsor/Advertise/Partnership/Orders — restricted to
    analytics.commercial by the route (spec section 37-38, 77).
    """
    start_dt, end_dt = date_range_bounds(start, end)

    entity_col = AnalyticsEvent.entity_id
    impressions_rows = dict(
        db.session.query(entity_col, func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.event_name == "sponsor_impression",
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
        )
        .group_by(entity_col)
        .all()
    )
    clicks_rows = dict(
        db.session.query(entity_col, func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.event_name == "sponsor_click",
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at < end_dt,
        )
        .group_by(entity_col)
        .all()
    )
    sponsor_ids = {int(sid) for sid in set(impressions_rows) | set(clicks_rows) if sid and sid.isdigit()}
    sponsors_by_id = {s.id: s for s in Sponsor.query.filter(Sponsor.id.in_(sponsor_ids)).all()} if sponsor_ids else {}
    sponsor_rows = []
    for sid_str in set(impressions_rows) | set(clicks_rows):
        impressions = impressions_rows.get(sid_str, 0)
        clicks = clicks_rows.get(sid_str, 0)
        sponsor = sponsors_by_id.get(int(sid_str)) if sid_str and sid_str.isdigit() else None
        ctr = round(clicks / impressions * 100, 2) if impressions else None
        sponsor_rows.append(
            {
                "sponsor": sponsor.campaign_name if sponsor else "Deleted sponsor",
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
            }
        )
    sponsor_rows.sort(key=lambda r: -r["impressions"])

    advertise = {
        "pageViews": _event_count("advertise_page_view", start, end),
        "mediaKitDownloads": _event_count("media_kit_download", start, end),
        "inquirySubmissions": _event_count("advertise_inquiry_submit", start, end),
        "offeringClicks": _event_count("offering_cta_click", start, end),
    }

    partnership_rows = (
        db.session.query(PartnershipInquiry.status, func.count(PartnershipInquiry.id))
        .filter(PartnershipInquiry.submitted_at >= start_dt, PartnershipInquiry.submitted_at < end_dt)
        .group_by(PartnershipInquiry.status)
        .all()
    )
    partnerships = {"inquiries": sum(c for _, c in partnership_rows), "byStatus": [{"status": s, "count": c} for s, c in partnership_rows]}

    # Never count cancelled/refunded/unpaid orders as completed revenue
    # (spec section 30) — mirrors Order's own authoritative status
    # semantics, never reinvented here.
    revenue_rows = (
        db.session.query(Order.currency, func.count(Order.id), func.sum(Order.total_amount))
        .filter(
            Order.order_status == "completed",
            Order.payment_status == "paid",
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
        )
        .group_by(Order.currency)
        .all()
    )
    # Multi-currency: reported separately per currency, never summed
    # together without FX conversion (spec section 29).
    orders = {"byCurrency": [{"currency": cur, "completedCount": cnt, "completedTotal": total or 0} for cur, cnt, total in revenue_rows]}

    return {"sponsors": sponsor_rows, "advertise": advertise, "partnerships": partnerships, "orders": orders}
