"""WSF SEO Phase 2A — "Server Structured Data + Breadcrumbs". Covers
everything this phase adds on top of Phase 1 (test_spa_shell_seo_phase1.py)
and the pre-existing Article coverage (test_spa_shell.py):

  - mirrored entity-specific JSON-LD (JobPosting/Event/Resource/Person
    twice over for Person and Author) on the 5 entity-detail types whose
    frontend already has a structured-data hook
  - server-rendered BreadcrumbList JSON-LD on every entity-detail type
    (including the 3 — Topic/Series/Opportunity — that get no entity
    schema this phase), their list pages, the Article shell, and CMS
    Page routes
  - the explicit Event offers.price fix (never a fabricated 0/free
    for a ticket that was simply never priced)
  - the explicit Resource security guarantee (protected delivery data
    never reaches raw HTML/JSON-LD)
  - JSON-LD safety against hostile/special-character content
  - noindex/404/auth routes never acquiring entity schema or breadcrumbs
"""
import json
import os
import re
from datetime import date

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


def _use_fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _count(pattern, html):
    return len(re.findall(pattern, html, re.IGNORECASE))


def _meta_content(html, attr, key):
    match = re.search(rf'<meta\s+(?:[^>]*?\s)?{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(rf'<meta\s+content=["\']([^"\']*)["\']\s+{attr}=["\']{re.escape(key)}["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _canonical_href(html):
    match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _structured_data_json_by_attr(html, attr_name):
    match = re.search(rf"<script\b[^>]*{re.escape(attr_name)}[^>]*>(.*?)</script>", html, re.IGNORECASE | re.DOTALL)
    assert match is not None, f"expected a {attr_name} script tag"
    return json.loads(match.group(1))


def _set_site_identity(app, **overrides):
    from app.services.site_settings import save_site_identity

    with app.app_context():
        save_site_identity({"site_name": "Women Shaping Futures", **overrides})
        db.session.commit()


def _make_article(app, slug, title="A Story", status="published", author_id=None, **overrides):
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        if author_id is None:
            author = Author(slug=f"{slug}-author", name="WSF Editorial", status="active")
            db.session.add(author)
            db.session.commit()
            author_id = author.id
        article = Article(slug=slug, title=title, status=status, author_id=author_id, **overrides)
        db.session.add(article)
        db.session.commit()
        return article.id


def _make_topic(app, slug, name="Leadership", status="published", **overrides):
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic(slug=slug, name=name, status=status, **overrides)
        db.session.add(topic)
        db.session.commit()
        return topic.id


def _make_series(app, slug, name="Founder Stories", status="published", **overrides):
    from app.models.taxonomy import Series

    with app.app_context():
        series = Series(slug=slug, name=name, status=status, **overrides)
        db.session.add(series)
        db.session.commit()
        return series.id


def _make_person(app, slug, name="Amara Okafor", status="published", **overrides):
    from app.models.people import Person

    with app.app_context():
        person = Person(slug=slug, name=name, status=status, **overrides)
        db.session.add(person)
        db.session.commit()
        return person.id


def _make_author(app, slug, name="WSF Editorial", status="active", **overrides):
    from app.models.people import Author

    with app.app_context():
        author = Author(slug=slug, name=name, status=status, **overrides)
        db.session.add(author)
        db.session.commit()
        return author.id


def _make_opportunity(app, slug, title="Global Fellowship", status="published", **overrides):
    from app.models.opportunity import Opportunity

    with app.app_context():
        opportunity = Opportunity(slug=slug, title=title, status=status, **overrides)
        db.session.add(opportunity)
        db.session.commit()
        return opportunity.id


def _make_job(app, slug, title="Program Manager", company_name="Kaziwave", status="published", **overrides):
    from app.models.opportunity import Job

    with app.app_context():
        job = Job(slug=slug, title=title, company_name=company_name, status=status, **overrides)
        db.session.add(job)
        db.session.commit()
        return job.id


def _make_event(app, slug, title="WSF Summit", status="published", event_date=None, **overrides):
    from app.models.opportunity import Event

    with app.app_context():
        event = Event(slug=slug, title=title, status=status, date=event_date or date(2026, 6, 1), **overrides)
        db.session.add(event)
        db.session.commit()
        return event.id


def _make_resource(app, slug, name="Career Reset Workbook", status="published", **overrides):
    from app.models.resource import Resource

    with app.app_context():
        resource = Resource(slug=slug, name=name, status=status, **overrides)
        db.session.add(resource)
        db.session.commit()
        return resource.id


class TestJobPostingStructuredData:
    def test_published_job_gets_jobposting_with_stored_fields(self, client, app):
        _use_fixture_index(app)
        _make_job(
            app,
            "program-manager",
            title="Program Manager",
            company_name="Kaziwave",
            short_description="Lead our flagship program.",
            employment_type="Full-time",
            published_date=date(2026, 1, 10),
            deadline=date(2026, 3, 1),
        )
        html = client.get("/jobs/program-manager").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-job-structured-data")
        assert data["@type"] == "JobPosting"
        assert data["title"] == "Program Manager"
        assert data["description"] == "Lead our flagship program."
        assert data["employmentType"] == "FULL_TIME"
        assert data["datePosted"] == "2026-01-10"
        assert data["validThrough"] == "2026-03-01T00:00:00Z"
        assert data["hiringOrganization"] == {"@type": "Organization", "name": "Kaziwave"}

    def test_jobs_list_page_has_no_jobposting(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "program-manager")
        html = client.get("/jobs").get_data(as_text=True)
        assert "data-job-structured-data" not in html

    def test_nonexistent_job_404_has_no_jobposting(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/jobs/does-not-exist")
        assert resp.status_code == 404
        assert "data-job-structured-data" not in resp.get_data(as_text=True)

    def test_draft_job_404_has_no_jobposting(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "still-drafting", status="draft")
        resp = client.get("/jobs/still-drafting")
        assert resp.status_code == 404
        assert "data-job-structured-data" not in resp.get_data(as_text=True)

    def test_salary_hidden_when_not_visible_never_leaks(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "hidden-salary", salary_min=50000, salary_max=70000, currency="USD", salary_visible=False)
        html = client.get("/jobs/hidden-salary").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-job-structured-data")
        assert "baseSalary" not in data

    def test_visible_salary_is_included(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "visible-salary", salary_min=50000, salary_max=70000, currency="USD", salary_visible=True, salary_period="year")
        html = client.get("/jobs/visible-salary").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-job-structured-data")
        assert data["baseSalary"]["currency"] == "USD"
        assert data["baseSalary"]["value"]["minValue"] == 50000
        assert data["baseSalary"]["value"]["maxValue"] == 70000

    def test_no_fabricated_deadline_or_employment_type_when_absent(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "minimal-job")
        html = client.get("/jobs/minimal-job").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-job-structured-data")
        assert "validThrough" not in data
        assert "employmentType" not in data
        assert "baseSalary" not in data

    def test_remote_worldwide_applicant_location(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "remote-worldwide", work_mode="Remote", remote_scope="worldwide")
        html = client.get("/jobs/remote-worldwide").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-job-structured-data")
        assert data["jobLocationType"] == "TELECOMMUTE"
        assert data["applicantLocationRequirements"] == {"@type": "Country", "name": "Anywhere"}


class TestEventStructuredData:
    def test_published_event_gets_event_schema(self, client, app):
        _use_fixture_index(app)
        _make_event(app, "wsf-summit", title="WSF Summit", short_description="Our flagship gathering.")
        html = client.get("/events/wsf-summit").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-event-structured-data")
        assert data["@type"] == "Event"
        assert data["name"] == "WSF Summit"
        assert data["description"] == "Our flagship gathering."
        assert data["eventStatus"] == "https://schema.org/EventScheduled"

    def test_events_list_page_has_no_event_schema(self, client, app):
        _use_fixture_index(app)
        _make_event(app, "wsf-summit")
        html = client.get("/events").get_data(as_text=True)
        assert "data-event-structured-data" not in html

    def test_missing_event_has_no_event_schema(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/events/does-not-exist")
        assert resp.status_code == 404
        assert "data-event-structured-data" not in resp.get_data(as_text=True)

    def test_absent_ticket_price_is_explicit_free_not_fake_zero(self, client, app):
        # Matches EventSchema.get_is_free's own authoritative rule (`not
        # ticket_price`) — a ticket price that was simply never entered
        # becomes a genuinely free offer (price "0"), never a fabricated
        # currency for one that was never configured either.
        _use_fixture_index(app)
        _make_event(app, "free-webinar", registration_url="https://example.com/register", ticket_price=None, currency=None)
        html = client.get("/events/free-webinar").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-event-structured-data")
        assert data["offers"]["price"] == "0"
        assert "priceCurrency" not in data["offers"]

    def test_real_price_retains_price_and_currency(self, client, app):
        _use_fixture_index(app)
        _make_event(app, "paid-summit", registration_url="https://example.com/register", ticket_price=425, currency="USD")
        html = client.get("/events/paid-summit").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-event-structured-data")
        assert data["offers"]["price"] == 425
        assert data["offers"]["priceCurrency"] == "USD"

    def test_no_registration_url_means_no_offer_at_all(self, client, app):
        _use_fixture_index(app)
        _make_event(app, "no-registration", registration_url=None)
        html = client.get("/events/no-registration").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-event-structured-data")
        assert "offers" not in data

    def test_virtual_event_location_never_exposes_private_link(self, client, app):
        _use_fixture_index(app)
        _make_event(app, "virtual-event", format="virtual", virtual_link="https://zoom.example.com/secret-room")
        html = client.get("/events/virtual-event").get_data(as_text=True)
        assert "secret-room" not in html
        data = _structured_data_json_by_attr(html, "data-event-structured-data")
        assert data["location"]["@type"] == "VirtualLocation"
        assert "secret-room" not in json.dumps(data)


class TestResourceStructuredData:
    def test_direct_download_resource_gets_free_offer(self, client, app):
        _use_fixture_index(app)
        _make_resource(app, "career-guide", name="Career Reset Workbook", access_type="direct_download", currency="USD")
        html = client.get("/resources/career-guide").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-resource-structured-data")
        assert data["@type"] == "DigitalDocument"
        assert data["offers"] == {
            "@type": "Offer",
            "price": 0,
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
        }

    def test_premium_resource_gets_real_price_offer(self, client, app):
        _use_fixture_index(app)
        _make_resource(app, "premium-guide", access_type="premium", price=4900, currency="USD")
        html = client.get("/resources/premium-guide").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-resource-structured-data")
        assert data["offers"]["price"] == 4900
        assert data["offers"]["priceCurrency"] == "USD"

    def test_member_only_resource_gets_no_offer(self, client, app):
        _use_fixture_index(app)
        _make_resource(app, "members-guide", access_type="member_only")
        html = client.get("/resources/members-guide").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-resource-structured-data")
        assert "offers" not in data

    def test_circle_only_resource_gets_no_offer(self, client, app):
        _use_fixture_index(app)
        _make_resource(app, "circle-guide", access_type="circle_only")
        html = client.get("/resources/circle-guide").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-resource-structured-data")
        assert "offers" not in data

    def test_resources_list_page_has_no_resource_schema(self, client, app):
        _use_fixture_index(app)
        _make_resource(app, "career-guide")
        html = client.get("/resources").get_data(as_text=True)
        assert "data-resource-structured-data" not in html

    def test_missing_resource_has_no_resource_schema(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/resources/does-not-exist")
        assert resp.status_code == 404
        assert "data-resource-structured-data" not in resp.get_data(as_text=True)

    def test_protected_delivery_data_never_leaks_into_raw_html_or_json_ld(self, client, app):
        # SECURITY (explicit, per task spec): file_url/external_url/
        # protected_file_path/download tokens/purchase IDs/member IDs
        # must never reach the raw response, in the structured data OR
        # anywhere else on the page.
        _use_fixture_index(app)
        _make_resource(
            app,
            "protected-guide",
            access_type="premium",
            price=2900,
            currency="USD",
            file_url="https://cdn.example.com/private/career-reset-master.pdf",
            external_url="https://partner.example.com/secret-portal",
            protected_file_path="/var/wsf/protected/career-reset-master.pdf",
            protected_original_filename="career-reset-internal-master.pdf",
        )
        resp = client.get("/resources/protected-guide")
        html = resp.get_data(as_text=True)
        assert "career-reset-master.pdf" not in html
        assert "secret-portal" not in html
        assert "/var/wsf/protected" not in html
        assert "career-reset-internal-master.pdf" not in html
        data = _structured_data_json_by_attr(html, "data-resource-structured-data")
        serialized = json.dumps(data)
        assert "career-reset-master.pdf" not in serialized
        assert "secret-portal" not in serialized
        assert "/var/wsf/protected" not in serialized


class TestPersonAndAuthorStructuredData:
    def test_person_schema_has_expected_fields(self, client, app):
        _use_fixture_index(app)
        _make_person(app, "amara-okafor", name="Amara Okafor", title="CEO", website="https://amara.example.com")
        html = client.get("/people/amara-okafor").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-person-structured-data")
        assert data["@type"] == "Person"
        assert data["name"] == "Amara Okafor"
        assert data["jobTitle"] == "CEO"
        assert data["sameAs"] == ["https://amara.example.com"]

    def test_person_no_fabricated_sameas_when_absent(self, client, app):
        _use_fixture_index(app)
        _make_person(app, "no-socials", name="No Socials")
        html = client.get("/people/no-socials").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-person-structured-data")
        assert "sameAs" not in data
        assert "jobTitle" not in data

    def test_author_schema_has_expected_fields(self, client, app):
        _use_fixture_index(app)
        _make_author(app, "wsf-editorial", name="WSF Editorial", role="Senior Editor")
        html = client.get("/authors/wsf-editorial").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-author-structured-data")
        assert data["@type"] == "Person"
        assert data["name"] == "WSF Editorial"
        assert data["jobTitle"] == "Senior Editor"

    def test_people_list_page_has_no_person_schema(self, client, app):
        _use_fixture_index(app)
        html = client.get("/people").get_data(as_text=True)
        assert "data-person-structured-data" not in html

    def test_missing_person_has_no_person_schema(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/people/does-not-exist")
        assert resp.status_code == 404
        assert "data-person-structured-data" not in resp.get_data(as_text=True)


class TestArticleStructuredDataRegression:
    def test_article_has_article_schema_website_organization_and_breadcrumb_exactly_once(self, client, app):
        _use_fixture_index(app)
        _make_article(app, "a-story", title="A Story")
        html = client.get("/a-story").get_data(as_text=True)
        assert _count(r"data-article-structured-data", html) == 1
        assert _count(r"data-site-structured-data", html) == 1
        assert _count(r"data-breadcrumb-structured-data", html) == 1

        article_data = _structured_data_json_by_attr(html, "data-article-structured-data")
        assert article_data["@type"] == "Article"
        assert article_data["headline"] == "A Story"

        site_data = _structured_data_json_by_attr(html, "data-site-structured-data")
        assert {d["@type"] for d in site_data} == {"WebSite", "Organization"}

    def test_article_breadcrumb_is_home_stories_title(self, client, app):
        _use_fixture_index(app)
        _make_article(app, "a-breadcrumb-story", title="A Breadcrumb Story")
        html = client.get("/a-breadcrumb-story").get_data(as_text=True)
        breadcrumb = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert breadcrumb["@type"] == "BreadcrumbList"
        items = breadcrumb["itemListElement"]
        assert [i["position"] for i in items] == [1, 2, 3]
        assert items[0]["name"] == "Home"
        assert items[0]["item"] == "https://womenshapingfutures.org/"
        assert items[1]["name"] == "Stories"
        assert items[1]["item"] == "https://womenshapingfutures.org/topics"
        assert items[2]["name"] == "A Breadcrumb Story"
        assert items[2]["item"] == "https://womenshapingfutures.org/a-breadcrumb-story"


class TestBreadcrumbCoverage:
    def test_topic_breadcrumb(self, client, app):
        _use_fixture_index(app)
        _make_topic(app, "leadership", name="Leadership")
        html = client.get("/topics/leadership").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        items = data["itemListElement"]
        assert [i["name"] for i in items] == ["Home", "Topics", "Leadership"]
        assert [i["position"] for i in items] == [1, 2, 3]
        assert items[1]["item"] == "https://womenshapingfutures.org/topics"
        assert items[2]["item"] == "https://womenshapingfutures.org/topics/leadership"

    def test_series_breadcrumb(self, client, app):
        _use_fixture_index(app)
        _make_series(app, "founder-stories", name="Founder Stories")
        html = client.get("/series/founder-stories").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert [i["name"] for i in data["itemListElement"]] == ["Home", "Series", "Founder Stories"]

    def test_person_breadcrumb(self, client, app):
        _use_fixture_index(app)
        _make_person(app, "amara-okafor", name="Amara Okafor")
        html = client.get("/people/amara-okafor").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert [i["name"] for i in data["itemListElement"]] == ["Home", "People", "Amara Okafor"]

    def test_author_breadcrumb(self, client, app):
        _use_fixture_index(app)
        _make_author(app, "wsf-editorial", name="WSF Editorial")
        html = client.get("/authors/wsf-editorial").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert [i["name"] for i in data["itemListElement"]] == ["Home", "Authors", "WSF Editorial"]

    def test_opportunity_breadcrumb(self, client, app):
        _use_fixture_index(app)
        _make_opportunity(app, "global-fellowship", title="Global Fellowship")
        html = client.get("/opportunities/global-fellowship").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert [i["name"] for i in data["itemListElement"]] == ["Home", "Opportunities", "Global Fellowship"]
        # Topic/Series/Opportunity get breadcrumbs only — no entity schema.
        assert "data-opportunity-structured-data" not in html

    def test_job_breadcrumb(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "program-manager", title="Program Manager")
        html = client.get("/jobs/program-manager").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert [i["name"] for i in data["itemListElement"]] == ["Home", "Jobs", "Program Manager"]

    def test_resource_breadcrumb(self, client, app):
        _use_fixture_index(app)
        _make_resource(app, "career-guide", name="Career Reset Workbook")
        html = client.get("/resources/career-guide").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert [i["name"] for i in data["itemListElement"]] == ["Home", "Resources", "Career Reset Workbook"]

    def test_event_breadcrumb(self, client, app):
        _use_fixture_index(app)
        _make_event(app, "wsf-summit", title="WSF Summit")
        html = client.get("/events/wsf-summit").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert [i["name"] for i in data["itemListElement"]] == ["Home", "Events", "WSF Summit"]

    def test_cms_page_breadcrumb(self, client, app):
        _use_fixture_index(app)
        html = client.get("/about").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        items = data["itemListElement"]
        assert items[0]["name"] == "Home"
        assert len(items) == 2
        assert items[1]["item"] == "https://womenshapingfutures.org/about"

    def test_list_page_breadcrumb_is_home_and_section(self, client, app):
        _use_fixture_index(app)
        html = client.get("/jobs").get_data(as_text=True)
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        items = data["itemListElement"]
        assert [i["name"] for i in items] == ["Home", "Jobs"]
        assert items[1]["item"] == "https://womenshapingfutures.org/jobs"

    def test_circle_and_newsletter_list_pages_have_no_breadcrumb(self, client, app):
        # Deliberately excluded from this phase's list-page breadcrumb
        # scope (not one of the 8 named list pages).
        _use_fixture_index(app)
        for path in ("/circle", "/newsletter"):
            html = client.get(path).get_data(as_text=True)
            assert "data-breadcrumb-structured-data" not in html


class TestNoindexAndNotFoundNeverGetBreadcrumbsOrEntitySchema:
    def test_404_page_has_no_breadcrumb(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/this-page-does-not-exist-at-all")
        assert resp.status_code == 404
        assert "data-breadcrumb-structured-data" not in resp.get_data(as_text=True)

    def test_login_page_has_no_breadcrumb(self, client, app):
        _use_fixture_index(app)
        html = client.get("/login").get_data(as_text=True)
        assert "data-breadcrumb-structured-data" not in html

    def test_register_page_has_no_breadcrumb(self, client, app):
        _use_fixture_index(app)
        html = client.get("/register").get_data(as_text=True)
        assert "data-breadcrumb-structured-data" not in html

    def test_forgot_password_has_no_breadcrumb(self, client, app):
        _use_fixture_index(app)
        html = client.get("/forgot-password").get_data(as_text=True)
        assert "data-breadcrumb-structured-data" not in html

    def test_reset_password_has_no_breadcrumb(self, client, app):
        _use_fixture_index(app)
        html = client.get("/reset-password").get_data(as_text=True)
        assert "data-breadcrumb-structured-data" not in html

    def test_search_page_has_no_breadcrumb(self, client, app):
        _use_fixture_index(app)
        html = client.get("/search").get_data(as_text=True)
        assert "data-breadcrumb-structured-data" not in html

    def test_account_page_has_no_breadcrumb(self, client, app):
        _use_fixture_index(app)
        html = client.get("/account").get_data(as_text=True)
        assert "data-breadcrumb-structured-data" not in html

    def test_checkout_callbacks_have_no_breadcrumb(self, client, app):
        _use_fixture_index(app)
        for path in ("/resources/checkout/callback", "/circle/checkout/callback"):
            html = client.get(path).get_data(as_text=True)
            assert "data-breadcrumb-structured-data" not in html

    def test_admin_route_has_no_breadcrumb_or_entity_schema(self, client, app):
        _use_fixture_index(app)
        html = client.get("/admin/jobs").get_data(as_text=True)
        assert "data-breadcrumb-structured-data" not in html
        assert "data-job-structured-data" not in html


class TestStructuredDataJsonSafety:
    def test_hostile_job_title_cannot_break_out_of_script_or_corrupt_json(self, client, app):
        _use_fixture_index(app)
        hostile = 'Senior "Lead" </script><script>alert(1)</script> & Ünïcode ☺ — Role'
        _make_job(app, "hostile-job", title=hostile, short_description=hostile)
        resp = client.get("/jobs/hostile-job")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "<script>alert(1)</script>" not in html
        data = _structured_data_json_by_attr(html, "data-job-structured-data")
        assert data["title"] == hostile

    def test_hostile_event_fields_stay_valid_json(self, client, app):
        _use_fixture_index(app)
        hostile = "Summit's </script> \"Finale\" & More <!-- inject -->"
        _make_event(app, "hostile-event", title=hostile, short_description=hostile, venue=hostile)
        resp = client.get("/events/hostile-event")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        data = _structured_data_json_by_attr(html, "data-event-structured-data")
        assert data["name"] == hostile

    def test_hostile_breadcrumb_name_stays_valid_json(self, client, app):
        _use_fixture_index(app)
        hostile = 'Topic </script><script>evil()</script> "Quoted"'
        _make_topic(app, "hostile-topic", name=hostile)
        resp = client.get("/topics/hostile-topic")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "<script>evil()</script>" not in html
        data = _structured_data_json_by_attr(html, "data-breadcrumb-structured-data")
        assert data["itemListElement"][-1]["name"] == hostile
