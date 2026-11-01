"""AI Search / GEO Phase 3B3 — crawler-readable public hubs & listing
pages (app/services/public_hubs.py + prerender.render_hub_prerender /
render_homepage_prerender), proven on raw HTML only (no JS).
"""
import os
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
SITE = "https://womenshapingfutures.org"


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _raw(client, path):
    resp = client.get(path)
    assert resp.status_code == 200, path
    return resp.get_data(as_text=True)


def _root(html):
    match = re.search(r'<div id="root">(.*?)</div>\s*<script type="module"', html, re.DOTALL)
    return match.group(1) if match else ""


def _add(app, *objs):
    with app.app_context():
        db.session.add_all(objs)
        db.session.commit()
        return [o.id for o in objs]


def _assert_hub(html, marker, title, canonical):
    root = _root(html)
    assert root.startswith(f'<main data-wsf-prerender="{marker}"'), marker
    assert html.count("data-wsf-prerender=") == 1
    assert len(re.findall(r"<h1\b", root)) == 1
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", root, re.DOTALL)
    assert h1 and re.sub(r"<[^>]+>", "", h1.group(1)) == title
    assert re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']' + re.escape(canonical), html)
    assert len(re.findall(r"<script\b[^>]*data-site-structured-data", html)) == 1
    lowered = root.lower()
    for hidden in (" hidden", "display:none", "visibility:hidden", 'aria-hidden="true"', "<noscript"):
        assert hidden not in lowered
    return root


def _absent(text, *needles):
    for needle in needles:
        assert needle not in text, needle


def _org(app, slug, status):
    from app.models.people import Organization

    return _add(app, Organization(slug=slug, name=slug.replace("-", " ").title(), status=status, description=[]))[0]


# --- empty states: every hub renders its header and no fake items -------------------------


HUBS = [
    ("/jobs", "jobs-index", "Jobs"),
    ("/opportunities", "opportunities-index", "Opportunities"),
    ("/events", "events-index", "Events"),
    ("/resources", "resources-index", "Guides, Workbooks &amp; Toolkits Built for Your Next Move"),
    ("/learning", "learning-index", "Courses, Masterclasses &amp; Learning Programs"),
    ("/people", "people-index", "The People Directory"),
    ("/organizations", "organizations-index", "Organizations"),
    ("/authors", "authors-index", "Our Authors &amp; Editors"),
    ("/topics", "topics-index", "Browse by Topic"),
    ("/series", "series-index", "Editorial Series"),
    ("/directory", "directory-index", "Business &amp; Professional Directory"),
    ("/shop", "shop-index", "WSF Shop"),
    ("/newsletter", "newsletter-index", "WSF Weekly"),
    ("/circle", "circle", "A closer circle for women shaping their futures"),
    ("/mentorship", "mentorship", "WSF Mentorship"),
]


@pytest.mark.parametrize("path,marker,title", HUBS)
def test_every_hub_renders_header_and_empty_state(client, path, marker, title):
    root = _assert_hub(_raw(client, path), marker, title, f"{SITE}{path}")
    assert "<article>" not in root  # no fake items in an empty collection


# --- populated hubs + non-public linked entities ------------------------------------------------


def test_jobs_and_opportunities_hubs(client, app):
    from app.models.opportunity import Job, Opportunity

    draft = _org(app, "secret-hub-draft-org", "draft")
    _add(app,
         Job(slug="hub-role", title="Hub Role", company_name="Kaziwave", status="published", location="Nairobi",
             short_description="Lead programs.", organization_id=draft, access_type="circle_only",
             application_url="https://secret-apply.example.com/x", salary_min=777777, salary_visible=False),
         Job(slug="draft-role", title="Secret Draft Role", company_name="X", status="draft"),
         Opportunity(slug="hub-grant", title="Hub Grant", status="published", organization_name="Fallback Fund",
                     organization_id=draft, short_description="A grant.", access_type="circle_only",
                     application_url="https://secret-grant.example.com/x"))
    root = _assert_hub(_raw(client, "/jobs"), "jobs-index", "Jobs", f"{SITE}/jobs")
    assert 'href="/jobs/hub-role"' in root and "Kaziwave" in root and "Lead programs." in root
    _absent(root, "Secret Draft Role", "Secret Hub Draft Org", "secret-hub-draft-org", "secret-apply", "777")
    root = _assert_hub(_raw(client, "/opportunities"), "opportunities-index", "Opportunities", f"{SITE}/opportunities")
    assert 'href="/opportunities/hub-grant"' in root and "Fallback Fund" in root
    _absent(root, "Secret Hub Draft Org", "secret-grant")


def test_events_hub_hides_draft_linked_entities(client, app):
    from app.models.opportunity import Event, EventSpeaker
    from app.models.people import Person

    draft_org = _org(app, "secret-organizer-org", "draft")
    person_id = _add(app, Person(slug="secret-speaker", name="Secret Speaker Person", status="draft"))[0]
    event_id = _add(app, Event(slug="hub-summit", title="Hub Summit", status="published", date=date.today() + timedelta(days=9),
                               organizer_id=draft_org, organizer_name="Fallback Organizer", short_description="Annual summit.",
                               virtual_link="https://zoom.example.com/SECRET"))[0]
    _add(app, EventSpeaker(event_id=event_id, person_id=person_id, position=0))
    root = _assert_hub(_raw(client, "/events"), "events-index", "Events", f"{SITE}/events")
    assert 'href="/events/hub-summit"' in root and "Fallback Organizer" in root
    _absent(root, "Secret Organizer Org", "secret-organizer-org", "Secret Speaker Person", "zoom.example.com")


def test_resources_and_learning_hubs_security(client, app):
    from app.models.learning import LearningLesson, LearningModule, LearningProgram
    from app.models.people import Author
    from app.models.resource import Resource
    from app.models.taxonomy import Topic

    draft_org = _org(app, "secret-res-sponsor", "draft")
    with app.app_context():
        inactive = Author(slug="secret-inactive-author", name="Secret Inactive Author", status="archived")
        topic = Topic(slug="secret-res-topic", name="Secret Resource Topic", status="draft")
        db.session.add_all([inactive, topic])
        db.session.flush()
        resource = Resource(slug="hub-kit", name="Hub Kit", status="published", type="Toolkit", access_type="premium",
                            price=1500, currency="KES", short_description="A kit.", author_id=inactive.id, sponsor_id=draft_org,
                            file_url="https://files.example.com/SECRET-FILE.pdf", protected_file_path="/srv/SECRET-PATH.pdf")
        resource.topics = [topic]
        program = LearningProgram(slug="hub-course", title="Hub Course", status="published", access_type="free", overview=[],
                                  short_description="A course.", duration_value=4, duration_unit="weeks")
        db.session.add_all([resource, program])
        db.session.flush()
        module = LearningModule(learning_program_id=program.id, title="SECRET-MODULE", sort_order=0)
        db.session.add(module)
        db.session.flush()
        db.session.add(LearningLesson(module_id=module.id, title="SECRET-LESSON", lesson_type="text",
                                      content=[{"type": "paragraph", "text": "SECRET-LESSON-BODY"}], sort_order=0))
        db.session.commit()

    root = _assert_hub(_raw(client, "/resources"), "resources-index", "Guides, Workbooks &amp; Toolkits Built for Your Next Move", f"{SITE}/resources")
    assert 'href="/resources/hub-kit"' in root and "Premium" in root and "KES 1,500" in root
    _absent(root, "Secret Inactive Author", "secret-res-sponsor", "Secret Resource Topic", "SECRET-FILE", "SECRET-PATH")
    root = _assert_hub(_raw(client, "/learning"), "learning-index", "Courses, Masterclasses &amp; Learning Programs", f"{SITE}/learning")
    assert 'href="/learning/hub-course"' in root and "4 weeks" in root
    _absent(_raw(client, "/learning"), "SECRET-MODULE", "SECRET-LESSON", "SECRET-LESSON-BODY")


def test_people_orgs_authors_topics_series_hubs(client, app):
    from app.models.people import Author, Organization, Person
    from app.models.taxonomy import Series, Topic

    with app.app_context():
        draft_topic = Topic(slug="secret-author-topic", name="Secret Author Topic", status="draft")
        pub_topic = Topic(slug="leadership", name="Leadership", status="published", description="Leading well.")
        draft_org = Organization(slug="secret-person-org", name="Secret Person Org", status="draft", description=[])
        db.session.add_all([draft_topic, pub_topic, draft_org])
        db.session.flush()
        author = Author(slug="hub-author", name="Hub Author", status="active", role="Editor")
        author.topics = [draft_topic, pub_topic]
        db.session.add_all([
            author, Author(slug="secret-old-author", name="Secret Old Author", status="archived"),
            Person(slug="hub-person", name="Hub Person", status="published", title="Founder", organization_id=draft_org.id, short_bio="Builds things."),
            Person(slug="secret-draft-person", name="Secret Draft Person", status="draft"),
            Organization(slug="hub-org", name="Hub Org", status="published", description=[], short_description="We build."),
            Series(slug="hub-series", name="Hub Series", status="published", subtitle="A subtitle"),
            Series(slug="secret-draft-series", name="Secret Draft Series", status="draft"),
        ])
        db.session.commit()

    root = _assert_hub(_raw(client, "/people"), "people-index", "The People Directory", f"{SITE}/people")
    assert 'href="/people/hub-person"' in root and "Founder" in root
    _absent(root, "Secret Draft Person", "Secret Person Org")
    root = _assert_hub(_raw(client, "/organizations"), "organizations-index", "Organizations", f"{SITE}/organizations")
    assert 'href="/organizations/hub-org"' in root
    _absent(root, "Secret Person Org")
    root = _assert_hub(_raw(client, "/authors"), "authors-index", "Our Authors &amp; Editors", f"{SITE}/authors")
    assert 'href="/authors/hub-author"' in root
    _absent(_raw(client, "/authors"), "Secret Old Author", "Secret Author Topic")
    root = _assert_hub(_raw(client, "/topics"), "topics-index", "Browse by Topic", f"{SITE}/topics")
    assert 'href="/topics/leadership"' in root and "Leading well." in root
    _absent(root, "Secret Author Topic")
    root = _assert_hub(_raw(client, "/series"), "series-index", "Editorial Series", f"{SITE}/series")
    assert 'href="/series/hub-series"' in root
    _absent(root, "Secret Draft Series")


def test_directory_shop_newsletter_hubs(client, app):
    from app.models.commerce import Product
    from app.models.directory import DirectoryCategory, DirectoryListing
    from app.models.newsletter import NewsletterIssue, NewsletterSubscriber
    from app.models.people import Organization
    from app.models.resource import Resource

    with app.app_context():
        org = Organization(slug="amani-studio", name="Amani Studio", status="published", description=[])
        cats = [DirectoryCategory(slug="design", name="Design", status="published"),
                DirectoryCategory(slug="secret-dir-category", name="Secret Dir Category", status="draft")]
        resource = Resource(slug="secret-product-resource", name="Secret Product Resource", status="draft")
        db.session.add_all([org, *cats, resource])
        db.session.flush()
        listing = DirectoryListing(organization_id=org.id, status="published", listing_type="business", ownership_classification="women_owned",
                                   classification_provenance="self_attested", verification_status="unverified", service_summary="Brand design.",
                                   verification_notes="SECRET-VERIFICATION-NOTE")
        listing.categories = cats
        db.session.add_all([
            listing,
            Product(slug="hub-workbook", name="Hub Workbook", status="active", description=[], price=1200, currency="KES", resource_id=resource.id),
            Product(slug="secret-draft-product", name="Secret Draft Product", status="draft", description=[]),
            NewsletterIssue(slug="jan", title="INTERNAL-TITLE", subject="January Digest", status="sent", issue_number=3,
                            sent_at=datetime(2026, 1, 15, tzinfo=timezone.utc), preheader="This week.", provider_campaign_id="SECRET-CAMPAIGN",
                            content=[{"type": "paragraph", "text": "ISSUE-BODY"}]),
            NewsletterIssue(slug="future", title="T", subject="Secret Future Subject", status="scheduled", content=[]),
            NewsletterSubscriber(email="secret-subscriber@example.com", first_name="Subfirst", status="active", unsubscribe_token="SECRET-UNSUB-TOKEN"),
        ])
        db.session.commit()

    root = _assert_hub(_raw(client, "/directory"), "directory-index", "Business &amp; Professional Directory", f"{SITE}/directory")
    assert 'href="/directory/amani-studio"' in root and "Design" in root and "Women-owned" in root
    _absent(root, "Secret Dir Category", "SECRET-VERIFICATION-NOTE")
    root = _assert_hub(_raw(client, "/shop"), "shop-index", "WSF Shop", f"{SITE}/shop")
    assert 'href="/shop/hub-workbook"' in root and "KES 1,200.00" in root
    _absent(_raw(client, "/shop"), "Secret Product Resource", "secret-product-resource", "Secret Draft Product")
    html = _raw(client, "/newsletter")
    root = _assert_hub(html, "newsletter-index", "WSF Weekly", f"{SITE}/newsletter")
    assert 'href="/newsletter/jan"' in root and "WSF Weekly #3" in root and "This week." in root
    _absent(html, "Secret Future Subject", "secret-subscriber@example.com", "Subfirst", "SECRET-UNSUB-TOKEN", "SECRET-CAMPAIGN",
            "INTERNAL-TITLE", "ISSUE-BODY")


def test_circle_and_mentorship_public_copy(client, app):
    from app.models.circle import CirclePlan
    from app.models.mentorship import MentorshipProgram
    from app.models.taxonomy import Topic

    with app.app_context():
        plan = CirclePlan(slug="monthly", name="Monthly Circle", status="active", billing_interval="monthly", price=1000, currency="KES",
                          checkout_url="https://checkout.example.com/SECRET-CHECKOUT", benefits=["Member events"])
        draft_plan = CirclePlan(slug="secret-plan", name="Secret Draft Plan", status="draft", billing_interval="monthly", price=1, currency="KES")
        draft_topic = Topic(slug="secret-mentor-topic", name="Secret Mentor Topic", status="draft")
        program = MentorshipProgram(slug="wsf-mentors", name="WSF Mentors Program", status="applications_open", public_visible=True,
                                    short_description="Six months of mentorship.")
        program.topics = [draft_topic]
        hidden = MentorshipProgram(slug="hidden", name="Secret Hidden Program", status="applications_open", public_visible=False)
        db.session.add_all([plan, draft_plan, program, hidden])
        db.session.commit()

    root = _assert_hub(_raw(client, "/circle"), "circle", "A closer circle for women shaping their futures", f"{SITE}/circle")
    assert "Why WSF Circle" in root and "Monthly Circle" in root and "KES 1,000 / month" in root and "Member events" in root
    _absent(root, "SECRET-CHECKOUT", "Secret Draft Plan")
    root = _assert_hub(_raw(client, "/mentorship"), "mentorship", "WSF Mentorship", f"{SITE}/mentorship")
    assert "Find a mentor" in root and "WSF Mentors Program" in root and "Six months of mentorship." in root
    _absent(root, "Secret Hidden Program", "Secret Mentor Topic")
    # The public Mentorship API filters the unpublished Topic too.
    assert "Secret Mentor Topic" not in client.get("/api/v1/mentorship/programs/public").get_data(as_text=True)


# --- homepage ------------------------------------------------------------------------------------


def _article(app, slug, title, status="published"):
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="home-author").first() or Author(slug="home-author", name="Home Author", status="active")
        db.session.add(author)
        db.session.flush()
        db.session.add(Article(slug=slug, title=title, status=status, author_id=author.id, excerpt=f"{title} excerpt.",
                               content=[], publish_date=datetime(2026, 2, 1, tzinfo=timezone.utc)))
        db.session.commit()


def test_homepage_renders_configured_modules_only(client, app):
    from app.models.cms import HomepageModule
    from app.models.people import Person

    _article(app, "lead-story", "Lead Story Title")
    _article(app, "picked-story", "Picked Story")
    _article(app, "secret-draft-story", "Secret Draft Story", status="draft")
    _add(app, Person(slug="featured-woman", name="Featured Woman Name", status="published", short_bio="An inspiring leader."))
    _add(app,
         HomepageModule(type="hero", enabled=True, sort_order=0, config={"leadArticleSlug": "lead-story"}),
         HomepageModule(type="featured_stories", enabled=True, sort_order=1, heading="Editors Picks Heading",
                        config={"articleSlugs": ["picked-story", "secret-draft-story"]}),
         HomepageModule(type="featured_woman", enabled=True, sort_order=2, heading="Woman To Know", config={"personSlug": "featured-woman"}),
         HomepageModule(type="jobs", enabled=False, sort_order=3, heading="Disabled Jobs Module Heading", config={}),
         HomepageModule(type="community_cta", enabled=True, sort_order=4, heading="Join The Community",
                        cta_label="Join now", cta_url="/community"))
    html = _raw(client, "/")
    root = _assert_hub(html, "home", "Lead Story Title", f"{SITE}/")
    assert 'href="/lead-story"' in root and "Lead Story Title excerpt." in root
    assert "Editors Picks Heading" in root and 'href="/picked-story"' in root
    assert "Woman To Know" in root and 'href="/people/featured-woman"' in root
    assert "Join The Community" in root and 'href="/community"' in root
    _absent(root, "Secret Draft Story", "Disabled Jobs Module Heading")
    # The existing homepage bootstrap is still there exactly once.
    assert html.count('data-wsf-bootstrap="homepage"') == 1


def test_homepage_without_modules_uses_site_name_h1(client):
    _assert_hub(_raw(client, "/"), "home", "Women Shaping Futures", f"{SITE}/")


def test_hub_with_query_string_keeps_base_canonical(client, app):
    html = _raw(client, "/jobs?page=4&q=anything")
    assert re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']' + re.escape(f"{SITE}/jobs") + '["\']', html)
    assert "anything" not in _root(html)


# --- homepage hero parity + CTA safety (pre-deploy correction) -------------------------------------


def _hero(app, **kwargs):
    from app.models.cms import HomepageModule

    _add(app, HomepageModule(type="hero", enabled=True, sort_order=0, **kwargs))


def _h1_html(root):
    return re.search(r"<h1[^>]*>(.*?)</h1>", root, re.DOTALL).group(1)


def test_lead_hero_without_override_uses_article_title_linked(client, app):
    _article(app, "original-story", "Original Story")
    _hero(app, config={"leadArticleSlug": "original-story"})
    root = _assert_hub(_raw(client, "/"), "home", "Original Story", f"{SITE}/")
    assert 'href="/original-story"' in _h1_html(root)
    assert "Read the story" not in root


def test_lead_hero_heading_override_wins_and_keeps_article_link(client, app):
    _article(app, "original-story", "Original Story")
    _hero(app, heading="Women Leading Change", config={"leadArticleSlug": "original-story"})
    root = _assert_hub(_raw(client, "/"), "home", "Women Leading Change", f"{SITE}/")
    assert 'href="/original-story"' in _h1_html(root)
    assert "Original Story excerpt." in root
    assert "Original Story<" not in root  # the original title is not the visible headline
    assert "Read the story" not in root


def test_lead_hero_renders_primary_cta_only(client, app):
    _article(app, "original-story", "Original Story")
    _hero(app, config={"leadArticleSlug": "original-story"},
          cta_label="Explore the series", cta_url="/series/leaders",
          secondary_cta_label="Secondary Lead CTA", secondary_cta_url="/jobs")
    root = _root(_raw(client, "/"))
    assert 'href="/series/leaders"' in root and "Explore the series" in root
    _absent(root, "Secondary Lead CTA", 'href="/jobs"')


def test_manual_hero_keeps_primary_and_secondary_ctas(client, app):
    _hero(app, heading="Manual Hero Heading", subheading="Manual sub.",
          cta_label="Find jobs", cta_url="/jobs",
          secondary_cta_label="Read the guide", secondary_cta_url="https://example.org/guide")
    root = _assert_hub(_raw(client, "/"), "home", "Manual Hero Heading", f"{SITE}/")
    assert 'href="/jobs"' in root and "Find jobs" in root
    assert 'href="https://example.org/guide"' in root and "Read the guide" in root


PRIVATE_CTA_URLS = [
    "/admin/foo", "/account", "/account/profile", "/api/v1/x", "/login", "/register", "/forgot-password",
    "/reset-password/token", "/change-password", "/newsletter/unsubscribe/token", "/resources/checkout",
    "/circle/checkout?plan=monthly", "/search?q=x", "/media/private.pdf", "/assets/file.js",
    "/ADMIN", "/login#top", "/account/", "javascript:alert(1)", "data:text/html,x", "//evil.example",
]


def test_private_and_unsafe_cta_paths_never_prerendered(client, app):
    from app.models.cms import HomepageModule

    _hero(app, heading="Manual Hero Heading", cta_label="Private Primary", cta_url="/account",
          secondary_cta_label="Private Secondary", secondary_cta_url="/circle/checkout?plan=monthly")
    _add(app, *[HomepageModule(type="community_cta", enabled=True, sort_order=i + 1, heading=f"Block {i}",
                               subheading=f"Block sub {i}.", cta_label=f"Private CTA {i}", cta_url=url) for i, url in enumerate(PRIVATE_CTA_URLS)])
    root = _root(_raw(client, "/"))
    assert "Block 0" in root and f"Block sub {len(PRIVATE_CTA_URLS) - 1}." in root  # blocks render; links withheld
    _absent(root, "Private Primary", "Private Secondary", "javascript:", "data:text", "evil.example")
    for i, url in enumerate(PRIVATE_CTA_URLS):
        assert f"Private CTA {i}<" not in root, url
    assert not re.search(r'href="/(admin|account|api|login|register|forgot-password|reset-password|change-password|'
                         r'newsletter/unsubscribe|resources/checkout|circle/checkout|search|media|assets)\b', root, re.I)


def test_cta_boundary_paths_and_external_https_allowed(client, app):
    from app.models.cms import HomepageModule

    _add(app,
         HomepageModule(type="community_cta", enabled=True, sort_order=1, heading="Boundary A",
                        cta_label="Accountability", cta_url="/accountability",
                        secondary_cta_label="Searching", secondary_cta_url="/searching"),
         HomepageModule(type="editorial_callout", enabled=True, sort_order=2, heading="External",
                        cta_label="Partner site", cta_url="https://partner.example.org/page?x=1"),
         HomepageModule(type="newsletter", enabled=True, sort_order=3, heading="Newsletter Block",
                        cta_label="Newsletter archive", cta_url="/newsletter"))
    root = _root(_raw(client, "/"))
    assert 'href="/accountability"' in root and 'href="/searching"' in root
    assert 'href="https://partner.example.org/page?x=1"' in root
    assert 'href="/newsletter"' in root
