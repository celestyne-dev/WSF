"""Site-wide Search & Discovery tests — see app/services/search.py and
app/api/v1/search.py. Covers query normalization/validation, per-type
public-eligibility enforcement (the privacy boundary is the point of this
whole feature), relevance ordering, pagination, filters, canonical URLs,
human-readable labels, and SQL/XSS input safety.
"""
from datetime import date, timedelta

from app.extensions import db


def _get(client, **params):
    return client.get("/api/v1/search", query_string=params)


# ---------------------------------------------------------------------------
# Fixtures — build the minimum real rows each content type's search needs,
# reusing each model's own required/default fields.
# ---------------------------------------------------------------------------


def _make_author(app, slug="wsf-editorial", name="WSF Editorial", status="active"):
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug=slug).first()
        if author is None:
            author = Author(slug=slug, name=name, status=status)
            db.session.add(author)
            db.session.commit()
        return author.id


def _make_article(app, slug, title, status="published", excerpt=None, content=None, author_id=None):
    from app.models.article import Article

    with app.app_context():
        article = Article(
            slug=slug,
            title=title,
            excerpt=excerpt,
            status=status,
            author_id=author_id or _make_author(app),
            publish_date=db.func.now(),
            content=content or [],
        )
        db.session.add(article)
        db.session.commit()
        return article.id


def _make_person(app, slug, name, status="published", **kwargs):
    from app.models.people import Person

    with app.app_context():
        person = Person(slug=slug, name=name, status=status, bio=[], **kwargs)
        db.session.add(person)
        db.session.commit()
        return person.id


def _make_organization(app, slug, name, status="published", **kwargs):
    from app.models.people import Organization

    with app.app_context():
        org = Organization(slug=slug, name=name, status=status, description=[], **kwargs)
        db.session.add(org)
        db.session.commit()
        return org.id


def _make_topic(app, slug, name, status="published"):
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic(slug=slug, name=name, status=status)
        db.session.add(topic)
        db.session.commit()
        return topic.id


def _make_job(app, slug, title, status="published", **kwargs):
    from app.models.opportunity import Job

    with app.app_context():
        job = Job(
            slug=slug,
            title=title,
            company_name=kwargs.pop("company_name", "Acme Corp"),
            status=status,
            description=[],
            responsibilities=[],
            requirements=[],
            qualifications=[],
            skills=[],
            benefits=[],
            **kwargs,
        )
        db.session.add(job)
        db.session.commit()
        return job.id


def _make_opportunity(app, slug, title, status="published", **kwargs):
    from app.models.opportunity import Opportunity

    with app.app_context():
        opp = Opportunity(slug=slug, title=title, status=status, description=[], **kwargs)
        db.session.add(opp)
        db.session.commit()
        return opp.id


def _make_event(app, slug, title, status="published", event_date=None, **kwargs):
    from app.models.opportunity import Event

    with app.app_context():
        event = Event(
            slug=slug, title=title, status=status, description=[], date=event_date or date.today(), **kwargs
        )
        db.session.add(event)
        db.session.commit()
        return event.id


def _make_resource(app, slug, name, status="published", **kwargs):
    from app.models.resource import Resource

    with app.app_context():
        resource = Resource(slug=slug, name=name, status=status, description=[], **kwargs)
        db.session.add(resource)
        db.session.commit()
        return resource.id


def _make_product(app, slug, name, status="active", **kwargs):
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=slug, name=name, status=status, description=[], **kwargs)
        db.session.add(product)
        db.session.commit()
        return product.id


def _make_page(app, key, slug, title, page_type="system", status="published"):
    from app.models.page import Page

    with app.app_context():
        page = Page(key=key, slug=slug, title=title, page_type=page_type, status=status, content=[])
        db.session.add(page)
        db.session.commit()
        return page.id


# ---------------------------------------------------------------------------
# Query normalization & validation
# ---------------------------------------------------------------------------


class TestQueryValidation:
    def test_empty_query_returns_no_results_not_an_error(self, client):
        resp = _get(client)
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["results"] == []
        assert body["pagination"]["total"] == 0

    def test_single_character_query_rejected_with_useful_error(self, client):
        resp = _get(client, q="a")
        assert resp.status_code == 422
        body = resp.get_json()
        assert body["success"] is False
        assert "least" in body["error"]["message"].lower()

    def test_overlong_query_rejected(self, client):
        resp = _get(client, q="x" * 500)
        assert resp.status_code == 422

    def test_whitespace_is_normalized_and_trimmed(self, client, app):
        _make_article(app, "leadership-piece", "Leading With Purpose")
        resp = _get(client, q="  leading   with  ")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["query"] == "leading with"

    def test_invalid_type_rejected_with_clear_message(self, client):
        resp = _get(client, q="leadership", type="not-a-real-type")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Per-type eligibility — the privacy boundary. Draft/private/expired
# content must never appear, regardless of how well it matches.
# ---------------------------------------------------------------------------


class TestEligibility:
    def test_draft_article_excluded(self, client, app):
        _make_article(app, "draft-story", "Unmistakable Draft Zephyrhawk", status="draft")
        resp = _get(client, q="Zephyrhawk")
        assert resp.get_json()["data"]["results"] == []

    def test_archived_article_excluded(self, client, app):
        _make_article(app, "archived-story", "Unmistakable Archived Zephyrhawk", status="archived")
        resp = _get(client, q="Zephyrhawk")
        assert resp.get_json()["data"]["results"] == []

    def test_published_article_included(self, client, app):
        _make_article(app, "published-story", "Unmistakable Published Zephyrhawk")
        resp = _get(client, q="Zephyrhawk")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["resultTypeKey"] == "articles"

    def test_draft_person_excluded_privacy_boundary(self, client, app):
        _make_person(app, "private-person", "Unmistakable Private Wexfordly", status="draft")
        resp = _get(client, q="Wexfordly")
        assert resp.get_json()["data"]["results"] == []

    def test_published_person_included(self, client, app):
        _make_person(app, "public-person", "Unmistakable Public Wexfordly")
        resp = _get(client, q="Wexfordly")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["resultTypeKey"] == "people"

    def test_expired_job_excluded(self, client, app):
        _make_job(
            app,
            "expired-job",
            "Unmistakable Expired Quortlebix Role",
            expiry_date=date.today() - timedelta(days=1),
        )
        resp = _get(client, q="Quortlebix")
        assert resp.get_json()["data"]["results"] == []

    def test_active_job_included(self, client, app):
        _make_job(app, "active-job", "Unmistakable Active Quortlebix Role")
        resp = _get(client, q="Quortlebix")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["resultTypeKey"] == "jobs"

    def test_closed_opportunity_excluded(self, client, app):
        _make_opportunity(app, "closed-opp", "Unmistakable Closed Fenwickborn Grant", status="closed")
        resp = _get(client, q="Fenwickborn")
        assert resp.get_json()["data"]["results"] == []

    def test_expired_opportunity_excluded(self, client, app):
        _make_opportunity(
            app,
            "expired-opp",
            "Unmistakable Expired Fenwickborn Grant",
            expiry_date=date.today() - timedelta(days=1),
        )
        resp = _get(client, q="Fenwickborn")
        assert resp.get_json()["data"]["results"] == []

    def test_draft_event_excluded(self, client, app):
        _make_event(app, "draft-event", "Unmistakable Draft Yarrowfield Summit", status="draft")
        resp = _get(client, q="Yarrowfield")
        assert resp.get_json()["data"]["results"] == []

    def test_cancelled_event_still_visible(self, client, app):
        # Cancelled events stay publicly visible (clearly marked) — mirrors
        # EventListResource's own public filter, not invented for search.
        _make_event(app, "cancelled-event", "Unmistakable Cancelled Yarrowfield Summit", status="cancelled")
        resp = _get(client, q="Yarrowfield")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1

    def test_draft_resource_excluded(self, client, app):
        _make_resource(app, "draft-resource", "Unmistakable Draft Nettlebrook Guide", status="draft")
        resp = _get(client, q="Nettlebrook")
        assert resp.get_json()["data"]["results"] == []

    def test_draft_product_excluded(self, client, app):
        _make_product(app, "draft-product", "Unmistakable Draft Hollowmere Kit", status="draft")
        resp = _get(client, q="Hollowmere")
        assert resp.get_json()["data"]["results"] == []

    def test_unavailable_product_still_visible(self, client, app):
        _make_product(app, "oos-product", "Unmistakable Sold Out Hollowmere Kit", status="unavailable")
        resp = _get(client, q="Hollowmere")
        assert len(resp.get_json()["data"]["results"]) == 1

    def test_general_page_excluded_no_public_route(self, client, app):
        _make_page(app, "some-general-page", "some-general-page", "Unmistakable Briarcliff Page", page_type="general")
        resp = _get(client, q="Briarcliff")
        assert resp.get_json()["data"]["results"] == []

    def test_system_page_included(self, client, app):
        _make_page(app, "about", "about", "Unmistakable Briarcliff About")
        resp = _get(client, q="Briarcliff")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["resultTypeKey"] == "pages"

    def test_community_members_are_never_searchable(self, client, app):
        # Community CMS members are explicitly out of scope for Search —
        # they have no public People page and must never leak as "People".
        from app.models.community import Member

        with app.app_context():
            member = Member(
                first_name="Unmistakable",
                last_name="Thistlewood",
                email="thistlewood@example.com",
                status="active",
            )
            db.session.add(member)
            db.session.commit()
        resp = _get(client, q="Thistlewood")
        assert resp.get_json()["data"]["results"] == []


# ---------------------------------------------------------------------------
# Relevance / ranking
# ---------------------------------------------------------------------------


class TestRelevance:
    def test_exact_title_match_ranks_above_partial_match(self, client, app):
        _make_article(app, "exact-vantagepoint", "Vantagepoint")
        _make_article(app, "partial-vantagepoint", "The Vantagepoint of Leaders Everywhere")
        resp = _get(client, q="Vantagepoint")
        results = resp.get_json()["data"]["results"]
        titles = [r["title"] for r in results]
        assert titles.index("Vantagepoint") < titles.index("The Vantagepoint of Leaders Everywhere")

    def test_article_urls_are_flat_not_nested(self, client, app):
        _make_article(app, "flat-url-marigoldcrest", "Marigoldcrest Feature")
        resp = _get(client, q="Marigoldcrest")
        results = resp.get_json()["data"]["results"]
        assert results[0]["url"] == "/flat-url-marigoldcrest"
        assert "/articles/" not in results[0]["url"]

    def test_result_type_labels_are_human_readable(self, client, app):
        _make_article(app, "labeled-story", "Unmistakable Labeled Pemberwick")
        resp = _get(client, q="Pemberwick")
        result = resp.get_json()["data"]["results"][0]
        assert result["resultType"] == "Story"
        assert "article" not in result["resultType"].lower()


# ---------------------------------------------------------------------------
# Content-type balance / filters
# ---------------------------------------------------------------------------


class TestTypeFilterAndBalance:
    def test_type_filter_restricts_to_one_content_type(self, client, app):
        _make_article(app, "cross-type-a", "Unmistakable Crosswind Feature")
        _make_job(app, "cross-type-b", "Unmistakable Crosswind Role")
        resp = _get(client, q="Crosswind", type="jobs")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["resultTypeKey"] == "jobs"

    def test_all_type_returns_multiple_content_types(self, client, app):
        _make_article(app, "balance-a", "Unmistakable Foxglovewick Feature")
        _make_job(app, "balance-b", "Unmistakable Foxglovewick Role")
        resp = _get(client, q="Foxglovewick", type="all")
        results = resp.get_json()["data"]["results"]
        keys = {r["resultTypeKey"] for r in results}
        assert {"articles", "jobs"}.issubset(keys)

    def test_topic_filter_restricts_articles(self, client, app):
        from app.models.article import Article

        topic_id = _make_topic(app, "topic-alpha", "Topic Alpha")
        _make_article(app, "topic-match", "Unmistakable Thornquist Piece")
        with app.app_context():
            from app.models.taxonomy import Topic

            article = Article.query.filter_by(slug="topic-match").first()
            topic = db.session.get(Topic, topic_id)
            article.topics.append(topic)
            db.session.commit()
        resp = _get(client, q="Thornquist", topic="topic-alpha")
        assert len(resp.get_json()["data"]["results"]) == 1
        resp2 = _get(client, q="Thornquist", topic="nonexistent-topic")
        assert resp2.get_json()["data"]["results"] == []

    def test_country_filter_restricts_people(self, client, app):
        _make_person(app, "country-us", "Unmistakable Braemoor US", country_code="US")
        _make_person(app, "country-ke", "Unmistakable Braemoor KE", country_code="KE")
        resp = _get(client, q="Braemoor", country="US")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["title"] == "Unmistakable Braemoor US"

    def test_remote_filter_restricts_jobs(self, client, app):
        _make_job(app, "remote-job", "Unmistakable Wrenfield Remote Role", work_mode="Remote")
        _make_job(app, "onsite-job", "Unmistakable Wrenfield Onsite Role", work_mode="On-site")
        resp = _get(client, q="Wrenfield", remote="true")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["meta"]["remote"] is True

    def test_invalid_country_filter_yields_no_crash_no_results(self, client, app):
        _make_person(app, "invalid-country-target", "Unmistakable Larkspurton", country_code="US")
        resp = _get(client, q="Larkspurton", country="ZZ")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["results"] == []


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    def test_pagination_bounds_per_page(self, client, app):
        for i in range(5):
            _make_job(app, f"paginated-job-{i}", f"Unmistakable Paginated Snowcrest Role {i}")
        resp = _get(client, q="Snowcrest", per_page=2)
        body = resp.get_json()["data"]
        assert len(body["results"]) == 2
        assert body["pagination"]["total"] == 5
        assert body["pagination"]["totalPages"] == 3

    def test_second_page_returns_different_results(self, client, app):
        for i in range(3):
            _make_job(app, f"page2-job-{i}", f"Unmistakable Pagewise Emberglen Role {i}")
        page1 = _get(client, q="Emberglen", per_page=2, page=1).get_json()["data"]["results"]
        page2 = _get(client, q="Emberglen", per_page=2, page=2).get_json()["data"]["results"]
        assert {r["title"] for r in page1}.isdisjoint({r["title"] for r in page2})

    def test_per_page_is_capped_at_max(self, client):
        resp = _get(client, q="anything", per_page=9999)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Input safety
# ---------------------------------------------------------------------------


class TestInputSafety:
    def test_script_payload_is_safe_and_matches_nothing(self, client, app):
        _make_article(app, "safe-story", "A Perfectly Normal Story")
        resp = _get(client, q="<script>alert(1)</script>")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["results"] == []

    def test_sql_metacharacters_are_safe(self, client):
        resp = _get(client, q="'; DROP TABLE articles; --")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["results"] == []

    def test_result_excerpts_never_contain_raw_html_tags(self, client, app):
        _make_article(
            app,
            "html-in-body",
            "Unmistakable Ravenswood Story",
            excerpt="<b>Bold</b> claim about <script>alert(1)</script> leadership",
        )
        resp = _get(client, q="Ravenswood")
        excerpt = resp.get_json()["data"]["results"][0]["excerpt"]
        assert "<script" not in excerpt
        assert "<b>" not in excerpt


# ---------------------------------------------------------------------------
# Zero-results / empty behavior
# ---------------------------------------------------------------------------


class TestEmptyAndZeroResults:
    def test_zero_results_returns_empty_list_not_fabricated_matches(self, client, app):
        _make_article(app, "unrelated", "Completely Unrelated Topic")
        resp = _get(client, q="Nonexistentqueryterm999")
        body = resp.get_json()["data"]
        assert body["results"] == []
        assert body["pagination"]["total"] == 0

    def test_empty_query_never_returns_trending_or_fabricated_content(self, client, app):
        _make_article(app, "should-not-appear", "Should Not Appear In Empty Search")
        resp = _get(client)
        assert resp.get_json()["data"]["results"] == []
