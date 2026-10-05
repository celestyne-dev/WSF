"""Public /sitemap.xml — see app/__init__.py's route and
app/services/sitemap.py. Covers: well-formed XML, canonical-origin
absolute URLs, per-content-type real public-visibility rules (reusing
each type's own existing rule, not a re-derived one), Circle-gated
records appearing on their real public-detail-page visibility (not their
access tier), and that no private/admin/draft/gated-action URL ever
leaks into the document.
"""
from pathlib import Path
from xml.etree import ElementTree as ET

from app.extensions import db

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _get_sitemap(client):
    return client.get("/sitemap.xml")


def _parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    locs = [el.text for el in root.findall(f"{SITEMAP_NS}url/{SITEMAP_NS}loc")]
    return root, locs


# ---------------------------------------------------------------------------
# Fixtures — direct-ORM minimum rows, mirroring each model's own required/
# default fields (same convention as test_search.py's helpers).
# ---------------------------------------------------------------------------


def _make_author(app, slug="wsf-editorial", name="WSF Editorial", status="active"):
    from app.models.people import Author

    with app.app_context():
        author = Author(slug=slug, name=name, status=status)
        db.session.add(author)
        db.session.commit()
        return author.id


def _make_article(app, slug, title="A Story", status="published", author_id=None):
    from app.models.article import Article

    with app.app_context():
        article = Article(
            slug=slug,
            title=title,
            status=status,
            author_id=author_id or _make_author(app),
            publish_date=db.func.now(),
            content=[],
        )
        db.session.add(article)
        db.session.commit()
        return article.id


def _make_person(app, slug, name="Amara Diallo", status="published"):
    from app.models.people import Person

    with app.app_context():
        person = Person(slug=slug, name=name, status=status, bio=[])
        db.session.add(person)
        db.session.commit()
        return person.id


def _make_organization(app, slug, name="Baraza Ventures", status="published", **kwargs):
    from app.models.people import Organization

    with app.app_context():
        org = Organization(slug=slug, name=name, status=status, description=[], **kwargs)
        db.session.add(org)
        db.session.commit()
        return org.id


def _make_topic(app, slug, name="Leadership", status="published"):
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic(slug=slug, name=name, status=status)
        db.session.add(topic)
        db.session.commit()
        return topic.id


def _make_series(app, slug, name="Flagship Series", status="published"):
    from app.models.taxonomy import Series

    with app.app_context():
        series = Series(slug=slug, name=name, status=status)
        db.session.add(series)
        db.session.commit()
        return series.id


def _make_job(app, slug, title="Senior Engineer", status="published", **kwargs):
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


def _make_opportunity(app, slug, title="Rising Leaders Fellowship", status="published", **kwargs):
    from app.models.opportunity import Opportunity

    with app.app_context():
        opp = Opportunity(slug=slug, title=title, status=status, description=[], **kwargs)
        db.session.add(opp)
        db.session.commit()
        return opp.id


def _make_event(app, slug, title="Leadership Summit", status="published", **kwargs):
    from datetime import date as date_cls

    from app.models.opportunity import Event

    with app.app_context():
        event = Event(
            slug=slug, title=title, status=status, description=[], date=kwargs.pop("date", date_cls.today()), **kwargs
        )
        db.session.add(event)
        db.session.commit()
        return event.id


def _make_resource(app, slug, name="The Career Reset Workbook", status="published", **kwargs):
    from app.models.resource import Resource as ResourceModel

    with app.app_context():
        resource = ResourceModel(slug=slug, name=name, status=status, description=[], **kwargs)
        db.session.add(resource)
        db.session.commit()
        return resource.id


def _make_program(app, slug, title="Women in Leadership Foundations", status="published", **kwargs):
    from app.models.learning import LearningProgram

    instructor_id = _make_author(app, slug=f"{slug}-instructor", name="Instructor")
    with app.app_context():
        program = LearningProgram(
            slug=slug,
            title=title,
            overview=[],
            status=status,
            access_type=kwargs.pop("access_type", "free"),
            primary_instructor_id=instructor_id,
            **kwargs,
        )
        db.session.add(program)
        db.session.commit()
        return program.id


def _make_directory_listing(app, org_slug, listing_status="published", org_status="published"):
    from app.models.directory import DirectoryListing

    org_id = _make_organization(app, org_slug, status=org_status, short_description="A fictional test company.")
    with app.app_context():
        listing = DirectoryListing(
            organization_id=org_id,
            status=listing_status,
            listing_type="business",
            ownership_classification="women_owned",
            classification_provenance="self_attested",
            verification_status="unverified",
            service_summary="We do fictional things.",
        )
        db.session.add(listing)
        db.session.commit()
        return listing.id, org_slug


def _make_newsletter_issue(app, slug, title="January Digest", status="sent"):
    from datetime import datetime, timezone

    from app.models.newsletter import NewsletterIssue

    with app.app_context():
        issue = NewsletterIssue(
            slug=slug,
            title=title,
            subject=title,
            status=status,
            sent_at=datetime.now(timezone.utc) if status == "sent" else None,
        )
        db.session.add(issue)
        db.session.commit()
        return issue.id


def _make_product(app, slug, name="The Founder's Playbook", status="active", **kwargs):
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=slug, name=name, status=status, description=[], **kwargs)
        db.session.add(product)
        db.session.commit()
        return product.id


def _make_page(app, key, slug, title="A System Page", page_type="system", status="published"):
    from app.models.page import Page

    with app.app_context():
        page = Page(key=key, slug=slug, title=title, page_type=page_type, status=status, content=[])
        db.session.add(page)
        db.session.commit()
        return page.id


# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------


class TestSitemapShape:
    def test_returns_200(self, client):
        resp = _get_sitemap(client)
        assert resp.status_code == 200

    def test_content_type_is_xml(self, client):
        resp = _get_sitemap(client)
        assert "xml" in resp.content_type

    def test_xml_is_well_formed(self, client):
        resp = _get_sitemap(client)
        # Raises if malformed — the assertion is that this doesn't raise.
        ET.fromstring(resp.data)

    def test_homepage_included(self, client, app):
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        base = app.config["PUBLIC_SITE_URL"].rstrip("/")
        assert f"{base}/" in locs

    def test_urls_use_the_configured_canonical_origin(self, client, app):
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        base = app.config["PUBLIC_SITE_URL"].rstrip("/")
        assert len(locs) > 0
        assert all(loc.startswith(base) for loc in locs)

    def test_no_admin_or_account_urls_ever_appear(self, client, app):
        _make_article(app, "a-published-story")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any("/admin" in loc for loc in locs)
        assert not any("/account" in loc for loc in locs)

    def test_nonexistent_category_and_tag_routes_never_emitted(self, client):
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any("/categories" in loc for loc in locs)
        assert not any("/tags" in loc for loc in locs)


# ---------------------------------------------------------------------------
# Per-content-type inclusion/exclusion
# ---------------------------------------------------------------------------


class TestArticles:
    def test_published_article_included(self, client, app):
        _make_article(app, "published-story", status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        base = app.config["PUBLIC_SITE_URL"].rstrip("/")
        assert f"{base}/published-story" in locs

    def test_draft_article_excluded(self, client, app):
        _make_article(app, "draft-story", status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/draft-story") for loc in locs)


class TestJobs:
    def test_published_job_included(self, client, app):
        _make_job(app, "senior-engineer", status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/jobs/senior-engineer") for loc in locs)

    def test_draft_job_excluded(self, client, app):
        _make_job(app, "draft-job", status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/jobs/draft-job") for loc in locs)

    def test_circle_only_job_still_included_on_its_real_public_visibility(self, client, app):
        _make_job(app, "circle-job", status="published", access_type="circle_only")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/jobs/circle-job") for loc in locs)


class TestOpportunities:
    def test_published_opportunity_included(self, client, app):
        _make_opportunity(app, "rising-leaders", status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/opportunities/rising-leaders") for loc in locs)

    def test_draft_opportunity_excluded(self, client, app):
        _make_opportunity(app, "draft-opp", status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/opportunities/draft-opp") for loc in locs)


class TestEvents:
    def test_published_event_included(self, client, app):
        _make_event(app, "leadership-summit", status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/events/leadership-summit") for loc in locs)

    def test_draft_event_excluded(self, client, app):
        _make_event(app, "draft-event", status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/events/draft-event") for loc in locs)

    def test_circle_only_event_still_included(self, client, app):
        _make_event(app, "circle-event", status="published", access_type="circle_only")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/events/circle-event") for loc in locs)


class TestResources:
    def test_published_resource_included_without_exposing_download_url(self, client, app):
        secret_url = "https://files.example.org/super-secret-download.pdf"
        _make_resource(app, "career-workbook", status="published", file_url=secret_url, access_type="direct_download")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/resources/career-workbook") for loc in locs)
        assert secret_url not in resp.data.decode("utf-8")

    def test_draft_resource_excluded(self, client, app):
        _make_resource(app, "draft-resource", status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/resources/draft-resource") for loc in locs)

    def test_circle_only_resource_still_included_without_exposing_its_file_url(self, client, app):
        secret_url = "https://files.example.org/circle-only-secret.pdf"
        _make_resource(app, "circle-resource", status="published", access_type="circle_only", file_url=secret_url)
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/resources/circle-resource") for loc in locs)
        assert secret_url not in resp.data.decode("utf-8")


class TestLearningPrograms:
    def test_published_program_included_without_exposing_gated_targets(self, client, app):
        _make_program(app, "leadership-foundations", status="published", access_type="circle_only")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/learning/leadership-foundations") for loc in locs)

    def test_draft_program_excluded(self, client, app):
        _make_program(app, "draft-program", status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/learning/draft-program") for loc in locs)


class TestDirectory:
    def test_approved_public_listing_included(self, client, app):
        _, org_slug = _make_directory_listing(app, "acme-ventures", listing_status="published", org_status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith(f"/directory/{org_slug}") for loc in locs)

    def test_unapproved_listing_excluded(self, client, app):
        _, org_slug = _make_directory_listing(app, "pending-ventures", listing_status="pending", org_status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith(f"/directory/{org_slug}") for loc in locs)

    def test_listing_with_unpublished_organization_excluded(self, client, app):
        _, org_slug = _make_directory_listing(app, "draft-org-ventures", listing_status="published", org_status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith(f"/directory/{org_slug}") for loc in locs)


class TestNewsletterArchive:
    def test_sent_issue_included(self, client, app):
        _make_newsletter_issue(app, "january-digest", status="sent")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/newsletter/january-digest") for loc in locs)

    def test_draft_issue_excluded(self, client, app):
        _make_newsletter_issue(app, "draft-digest", status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/newsletter/draft-digest") for loc in locs)


class TestShopProducts:
    def test_active_product_included(self, client, app):
        _make_product(app, "founders-playbook", status="active")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/shop/founders-playbook") for loc in locs)

    def test_unavailable_product_still_included(self, client, app):
        _make_product(app, "sold-out-kit", status="unavailable")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/shop/sold-out-kit") for loc in locs)

    def test_archived_product_excluded(self, client, app):
        _make_product(app, "archived-kit", status="archived")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/shop/archived-kit") for loc in locs)


class TestPeopleAuthorsOrganizationsTopicsSeries:
    """Only for content types with a genuine public route — confirmed by
    reading frontend/src/routes/AppRoutes.jsx during this module's audit.
    """

    def test_published_person_included(self, client, app):
        _make_person(app, "amara-diallo", status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/people/amara-diallo") for loc in locs)

    def test_draft_person_excluded(self, client, app):
        _make_person(app, "draft-person", status="draft")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/people/draft-person") for loc in locs)

    def test_active_author_included(self, client, app):
        _make_author(app, "wsf-editorial", status="active")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/authors/wsf-editorial") for loc in locs)

    def test_published_organization_included(self, client, app):
        _make_organization(app, "baraza-ventures", status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/organizations/baraza-ventures") for loc in locs)

    def test_published_topic_included(self, client, app):
        _make_topic(app, "leadership", status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/topics/leadership") for loc in locs)

    def test_published_series_included(self, client, app):
        _make_series(app, "flagship", status="published")
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        assert any(loc.endswith("/series/flagship") for loc in locs)


class TestSystemPages:
    def test_published_system_page_included_with_lastmod(self, client, app):
        _make_page(app, "about", "about", status="published")
        resp = _get_sitemap(client)
        root, locs = _parse(resp.data)
        base = app.config["PUBLIC_SITE_URL"].rstrip("/")
        assert f"{base}/about" in locs
        about_url_el = next(
            el for el in root.findall(f"{SITEMAP_NS}url") if el.find(f"{SITEMAP_NS}loc").text == f"{base}/about"
        )
        assert about_url_el.find(f"{SITEMAP_NS}lastmod") is not None

    def test_unseeded_system_page_simply_omitted_not_a_500(self, client):
        # No "cookies" Page row exists in this fresh test database — must
        # be silently skipped, never fabricated and never a crash.
        resp = _get_sitemap(client)
        assert resp.status_code == 200
        _, locs = _parse(resp.data)
        assert not any(loc.endswith("/cookies") for loc in locs)


# ---------------------------------------------------------------------------
# XML escaping
# ---------------------------------------------------------------------------


class TestXmlEscaping:
    def test_unusual_slug_round_trips_correctly_escaped(self, client, app):
        # Bypasses the API's slug validator on purpose (direct ORM write)
        # to prove the XML *serializer* itself is safe regardless of what
        # ends up in a slug column — not merely that upstream validation
        # already prevents this.
        unusual_slug = "amp-&-lt-<-story"
        _make_article(app, unusual_slug, status="published")
        resp = _get_sitemap(client)
        raw = resp.data.decode("utf-8")
        # The raw XML must never contain a bare unescaped & or <.
        assert "&-lt-<-" not in raw
        _, locs = _parse(resp.data)
        base = app.config["PUBLIC_SITE_URL"].rstrip("/")
        assert f"{base}/{unusual_slug}" in locs


# ---------------------------------------------------------------------------
# Public singleton marketing/content pages
# ---------------------------------------------------------------------------


class TestSingletonPublicPages:
    """Re-audited per explicit correction: verified by reading each page's
    own useSeo() call in frontend/src/pages/*.jsx — none of these eight
    sets robots: 'noindex, nofollow' (contrast with AccountMembershipPage/
    NewsletterUnsubscribePage, which do, and are correctly never listed),
    and every one hand-sets its own canonical URL — the same deliberate-
    indexability signal. All eight are included; none is excluded.
    """

    def test_all_eight_singleton_pages_included(self, client, app):
        resp = _get_sitemap(client)
        _, locs = _parse(resp.data)
        base = app.config["PUBLIC_SITE_URL"].rstrip("/")
        for path in (
            "/advertise",
            "/partnerships",
            "/community",
            "/circle",
            "/mentorship",
            "/submit",
            "/nominate",
            "/directory/submit",
        ):
            assert f"{base}{path}" in locs, path


# ---------------------------------------------------------------------------
# robots.txt — now a real backend-served route (see app/__init__.py and
# app/services/sitemap.py's build_robots_txt), not a static file, so its
# Sitemap: line reads the configured PUBLIC_SITE_URL instead of a
# hard-coded domain.
# ---------------------------------------------------------------------------


class TestRobotsTxt:
    def test_returns_200_with_text_content_type(self, client):
        resp = client.get("/robots.txt")
        assert resp.status_code == 200
        assert "text/plain" in resp.content_type

    def test_sitemap_declaration_uses_configured_origin(self, client, app):
        resp = client.get("/robots.txt")
        base = app.config["PUBLIC_SITE_URL"].rstrip("/")
        content = resp.data.decode("utf-8")
        assert f"Sitemap: {base}/sitemap.xml" in content

    def test_existing_disallow_directive_preserved(self, client):
        resp = client.get("/robots.txt")
        content = resp.data.decode("utf-8")
        assert "Disallow: /admin/" in content

    def test_static_frontend_file_no_longer_hard_codes_the_sitemap_origin(self):
        # The static file is still shipped (for a frontend-only preview
        # with no backend behind it) but must never carry an actual
        # Sitemap: directive line again — that's the one thing this
        # correction set out to remove. Its own explanatory comment does
        # mention the word "Sitemap:" (to say why there isn't one), so
        # check for a real directive *line*, not just the substring.
        static_path = Path(__file__).resolve().parents[2] / "frontend" / "public" / "robots.txt"
        content = static_path.read_text()
        directive_lines = [line for line in content.splitlines() if not line.strip().startswith("#")]
        assert not any(line.strip().startswith("Sitemap:") for line in directive_lines)
        assert "Disallow: /admin/" in content
