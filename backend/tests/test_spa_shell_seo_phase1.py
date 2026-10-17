"""WSF SEO Core Readiness — Phase 1: generalizing spa_shell.py's
server-rendered metadata beyond Article (see that module's own docstring
for the full route-class breakdown). test_spa_shell.py keeps the
Article-specific regression-guard coverage (that file's own tests were
updated only where this phase deliberately changed behavior — an
unknown/draft/archived single-segment slug now 404s instead of silently
returning the generic shell). This file covers everything newly
server-rendered: the homepage, the 8 entity-detail types, list/landing
pages, CMS Page routes, auth/account noindex routes, and the route-class
boundaries (an out-of-scope-this-phase entity type's detail route, a
checkout-callback passthrough, a deep /admin/* path, a genuinely unknown
multi-segment path) that make the new 404 behavior safe.
"""
import os
import re
from datetime import date

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


def _use_fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _meta_content(html, attr, key):
    match = re.search(rf'<meta\s+(?:[^>]*?\s)?{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(rf'<meta\s+content=["\']([^"\']*)["\']\s+{attr}=["\']{re.escape(key)}["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _canonical_href(html):
    match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _structured_data_json(html, attr_name="data-site-structured-data"):
    import json

    match = re.search(rf"<script\b[^>]*{re.escape(attr_name)}[^>]*>(.*?)</script>", html, re.IGNORECASE | re.DOTALL)
    assert match is not None, f"expected a {attr_name} script tag"
    return json.loads(match.group(1))


def _set_site_identity(app, **overrides):
    from app.services.site_settings import save_site_identity

    with app.app_context():
        save_site_identity({"site_name": "Women Shaping Futures", **overrides})
        db.session.commit()


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


def _make_page(app, key, title="About Women Shaping Futures", status="published", **overrides):
    from app.models.page import Page

    with app.app_context():
        page = Page(key=key, slug=key, title=title, status=status, **overrides)
        db.session.add(page)
        db.session.commit()
        return page.id


class TestHomepageServerSEO:
    def test_homepage_has_full_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _set_site_identity(app)

        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        assert "<title>Women Shaping Futures — Stories, Opportunity &amp; Growth for Women Worldwide</title>" in html
        assert _meta_content(html, "name", "description")
        assert _canonical_href(html) == "https://womenshapingfutures.org/"
        assert _meta_content(html, "name", "robots") == "index, follow"
        assert _meta_content(html, "property", "og:type") == "website"
        assert _meta_content(html, "property", "og:site_name") == "Women Shaping Futures"
        assert _meta_content(html, "name", "twitter:card") == "summary_large_image"

        data = _structured_data_json(html)
        types = {d["@type"] for d in data}
        assert types == {"WebSite", "Organization"}
        for d in data:
            assert d["name"] == "Women Shaping Futures"
            assert d["url"] == "https://womenshapingfutures.org"


class TestEntityDetailServerSEO:
    def test_topic_resolves_to_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _make_topic(app, "leadership", name="Leadership", description="Stories about leading.")

        resp = client.get("/topics/leadership")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>Leadership | Women Shaping Futures</title>" in html
        assert _meta_content(html, "name", "description") == "Stories about leading."
        assert _canonical_href(html) == "https://womenshapingfutures.org/topics/leadership"
        assert _meta_content(html, "name", "robots") == "index, follow"
        _structured_data_json(html)  # site-wide WebSite+Organization present

    def test_topic_seo_override_is_honored(self, client, app):
        # The exact CMS SEO bug this phase fixes (see
        # frontend/src/pages/TopicDetailPage.jsx) — now honored both
        # server- and client-side.
        _use_fixture_index(app)
        _make_topic(app, "money", name="Money", seo={"title": "Custom Topic Title", "canonical": "https://womenshapingfutures.org/topics/money-custom"})

        resp = client.get("/topics/money")
        html = resp.get_data(as_text=True)
        assert "<title>Custom Topic Title</title>" in html
        assert _canonical_href(html) == "https://womenshapingfutures.org/topics/money-custom"

    def test_nonexistent_topic_returns_404_with_noindex(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/topics/does-not-exist")
        assert resp.status_code == 404
        html = resp.get_data(as_text=True)
        assert _meta_content(html, "name", "robots") == "noindex, follow"
        assert "<title>Page Not Found | Women Shaping Futures</title>" in html

    def test_draft_topic_is_never_leaked_and_404s(self, client, app):
        _use_fixture_index(app)
        _make_topic(app, "secret-topic", name="Secret Topic Title", status="draft")

        resp = client.get("/topics/secret-topic")
        assert resp.status_code == 404
        assert "Secret Topic Title" not in resp.get_data(as_text=True)

    def test_series_resolves_to_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _make_series(app, "founder-stories", name="Founder Stories", description="Women who built something.")

        resp = client.get("/series/founder-stories")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>Founder Stories | Women Shaping Futures</title>" in html
        assert _canonical_href(html) == "https://womenshapingfutures.org/series/founder-stories"

    def test_nonexistent_series_returns_404(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/series/does-not-exist")
        assert resp.status_code == 404

    def test_person_resolves_to_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _make_person(app, "amara-okafor", name="Amara Okafor", short_bio="A leader in fintech.")

        resp = client.get("/people/amara-okafor")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>Amara Okafor | Women Shaping Futures</title>" in html
        assert _meta_content(html, "name", "description") == "A leader in fintech."

    def test_draft_person_404s(self, client, app):
        _use_fixture_index(app)
        _make_person(app, "draft-person", name="Not Yet Public", status="draft")

        resp = client.get("/people/draft-person")
        assert resp.status_code == 404
        assert "Not Yet Public" not in resp.get_data(as_text=True)

    def test_author_resolves_to_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _make_author(app, "wsf-editorial", name="WSF Editorial", short_bio="The WSF editorial team.")

        resp = client.get("/authors/wsf-editorial")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>WSF Editorial | Women Shaping Futures</title>" in html

    def test_author_with_default_draft_status_404s(self, client, app):
        # Author.status defaults to "draft" — only "active" is publicly
        # visible (a different vocabulary than every other entity here).
        _use_fixture_index(app)
        _make_author(app, "inactive-author", name="Not Active Yet", status="draft")

        resp = client.get("/authors/inactive-author")
        assert resp.status_code == 404

    def test_opportunity_resolves_to_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _make_opportunity(app, "global-fellowship", title="Global Fellowship", short_description="A year-long fellowship.")

        resp = client.get("/opportunities/global-fellowship")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>Global Fellowship | Women Shaping Futures Opportunities</title>" in html
        assert _meta_content(html, "name", "description") == "A year-long fellowship."

    def test_nonexistent_opportunity_returns_404(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/opportunities/does-not-exist")
        assert resp.status_code == 404

    def test_job_resolves_to_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "program-manager", title="Program Manager", company_name="Kaziwave", short_description="Lead our programs team.")

        resp = client.get("/jobs/program-manager")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>Program Manager at Kaziwave | Women Shaping Futures Jobs</title>" in html
        assert _meta_content(html, "name", "robots") == "index, follow"

    def test_job_past_deadline_gets_noindex_follow(self, client, app):
        _use_fixture_index(app)
        _make_job(app, "closed-role", title="Closed Role", company_name="Kaziwave", deadline=date(2000, 1, 1))

        resp = client.get("/jobs/closed-role")
        assert resp.status_code == 200
        assert _meta_content(resp.get_data(as_text=True), "name", "robots") == "noindex, follow"

    def test_nonexistent_job_returns_404(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/jobs/does-not-exist")
        assert resp.status_code == 404

    def test_event_resolves_to_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _make_event(app, "wsf-summit", title="WSF Summit", short_description="Our flagship annual event.")

        resp = client.get("/events/wsf-summit")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>WSF Summit | Women Shaping Futures Events</title>" in html

    def test_nonexistent_event_returns_404(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/events/does-not-exist")
        assert resp.status_code == 404

    def test_resource_resolves_to_server_rendered_metadata(self, client, app):
        _use_fixture_index(app)
        _make_resource(app, "career-reset", name="Career Reset Workbook", short_description="Plan your next move.")

        resp = client.get("/resources/career-reset")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>Career Reset Workbook | Women Shaping Futures Resources</title>" in html
        # A Premium/Circle-gated resource's own marketing page stays
        # indexable — no computed robots override exists for this type.
        assert _meta_content(html, "name", "robots") == "index, follow"

    def test_gated_resource_marketing_page_still_indexable(self, client, app):
        _use_fixture_index(app)
        _make_resource(app, "circle-only-guide", name="Circle-Only Guide", access_type="circle_only")

        resp = client.get("/resources/circle-only-guide")
        assert resp.status_code == 200
        assert _meta_content(resp.get_data(as_text=True), "name", "robots") == "index, follow"

    def test_resource_protected_fields_never_appear_in_html(self, client, app):
        _use_fixture_index(app)
        _make_resource(
            app,
            "protected-resource",
            name="Protected Resource",
            file_url="/media/protected/secret.pdf",
            external_url="https://external.example.com/secret",
            protected_file_path="protected/secret-token-abc123.pdf",
        )

        resp = client.get("/resources/protected-resource")
        html = resp.get_data(as_text=True)
        assert "secret.pdf" not in html
        assert "external.example.com" not in html
        assert "secret-token-abc123" not in html

    def test_nonexistent_resource_returns_404(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/resources/does-not-exist")
        assert resp.status_code == 404


class TestListPagesServerSEO:
    _CASES = [
        ("topics", "Stories by Topic | Women Shaping Futures"),
        ("series", "Editorial Series | Women Shaping Futures"),
        ("people", "People Directory | Women Shaping Futures"),
        ("authors", "Authors | Women Shaping Futures"),
        ("opportunities", "Opportunities | Women Shaping Futures"),
        ("jobs", "Jobs for Women | Women Shaping Futures"),
        ("events", "Events | Women Shaping Futures"),
        ("resources", "Resource Library | Women Shaping Futures"),
        ("circle", "WSF Circle | Women Shaping Futures"),
        ("newsletter", "WSF Weekly Newsletter | Women Shaping Futures"),
    ]

    def test_every_list_page_has_unique_server_rendered_title_and_canonical(self, client, app):
        _use_fixture_index(app)
        seen_titles = set()
        for path, expected_title in self._CASES:
            resp = client.get(f"/{path}")
            assert resp.status_code == 200, path
            html = resp.get_data(as_text=True)
            assert f"<title>{expected_title}</title>" in html, path
            assert _canonical_href(html) == f"https://womenshapingfutures.org/{path}", path
            assert _meta_content(html, "name", "robots") == "index, follow", path
            _structured_data_json(html)  # site-wide JSON-LD present
            seen_titles.add(expected_title)
        # Never the same generic title/description across every list page.
        assert len(seen_titles) == len(self._CASES)


class TestSystemPageServerSEO:
    def test_about_page_honors_seo_and_hero_fallbacks(self, client, app):
        _use_fixture_index(app)
        _make_page(app, "about", title="About WSF", subtitle="Our mission.", page_type="system")

        resp = client.get("/about")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "<title>About WSF</title>" in html
        assert _meta_content(html, "name", "description") == "Our mission."
        assert _canonical_href(html) == "https://womenshapingfutures.org/about"

    def test_about_page_seo_override_wins(self, client, app):
        _use_fixture_index(app)
        _make_page(app, "about", title="About WSF", subtitle="Our mission.", seo={"title": "Custom About Title"}, page_type="system")

        resp = client.get("/about")
        assert "<title>Custom About Title</title>" in resp.get_data(as_text=True)

    def test_unseeded_system_page_falls_back_to_site_default_not_404(self, client, app):
        _use_fixture_index(app)
        _set_site_identity(app, seo_default_title="Women Shaping Futures Default")

        resp = client.get("/privacy")
        assert resp.status_code == 200
        assert "<title>Women Shaping Futures Default</title>" in resp.get_data(as_text=True)

    def test_contact_page_has_no_internal_title_fallback(self, client, app):
        # ContactPage.jsx has no page.title/subtitle fallback of its own
        # — a blank seo.title/description falls straight to the global
        # default, not to page.title.
        _use_fixture_index(app)
        _set_site_identity(app, seo_default_title="Site Default Title")
        _make_page(app, "contact", title="Internal Contact Title", page_type="system")

        resp = client.get("/contact")
        assert "<title>Site Default Title</title>" in resp.get_data(as_text=True)


class TestAuthAndAccountRawNoindex:
    _CASES = [
        ("search", "noindex, follow"),
        ("login", "noindex, follow"),
        ("register", "noindex, follow"),
        ("forgot-password", "noindex, nofollow"),
        ("change-password", "noindex, nofollow"),
        ("reset-password", "noindex, nofollow"),
        ("account", "noindex, nofollow"),
        ("account/profile", "noindex, nofollow"),
        ("account/saved", "noindex, nofollow"),
        ("account/events", "noindex, nofollow"),
        ("account/learning", "noindex, nofollow"),
        ("account/community", "noindex, nofollow"),
        ("account/membership", "noindex, nofollow"),
        ("account/security", "noindex, nofollow"),
    ]

    def test_every_auth_and_account_route_carries_raw_noindex(self, client, app):
        _use_fixture_index(app)
        for path, expected_robots in self._CASES:
            resp = client.get(f"/{path}")
            assert resp.status_code == 200, path
            html = resp.get_data(as_text=True)
            assert _meta_content(html, "name", "robots") == expected_robots, path


class TestRouteClassBoundaries:
    def test_unenhanced_entity_prefix_detail_route_stays_generic_200(self, client, app):
        # organizations/<slug> is a real, working SPA route this phase
        # doesn't enhance — must never be wrongly 404'd just because no
        # entity-visibility rule was vetted for it yet.
        _use_fixture_index(app)
        resp = client.get("/organizations/some-org")
        assert resp.status_code == 200
        assert "<title>Women Shaping Futures</title>" in resp.get_data(as_text=True)

    def test_newsletter_issue_detail_route_stays_generic_200(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/newsletter/some-issue-slug")
        assert resp.status_code == 200

    def test_newsletter_unsubscribe_token_route_stays_generic_200(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/newsletter/unsubscribe/some-token")
        assert resp.status_code == 200

    def test_resources_checkout_callback_stays_200_and_functional(self, client, app):
        # Still a real, fully functional SPA route — never 404'd — now
        # with its own safe, raw noindex metadata (see
        # TestCheckoutCallbackRawNoindex for the full coverage).
        _use_fixture_index(app)
        resp = client.get("/resources/checkout/callback")
        assert resp.status_code == 200

    def test_circle_checkout_callback_stays_200_and_functional(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/circle/checkout/callback")
        assert resp.status_code == 200

    def test_deep_admin_route_stays_generic_200(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/admin/jobs/5")
        assert resp.status_code == 200

    def test_genuinely_unknown_multi_segment_path_returns_404(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/this/path/does/not/exist")
        assert resp.status_code == 404
        html = resp.get_data(as_text=True)
        assert _meta_content(html, "name", "robots") == "noindex, follow"
        assert "<title>Page Not Found | Women Shaping Futures</title>" in html

    def test_unknown_two_segment_path_with_unrecognized_prefix_returns_404(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/totally-made-up-prefix/some-slug")
        assert resp.status_code == 404


class TestCheckoutCallbackRawNoindex:
    """Payment-callback landing pages (/resources/checkout/callback,
    /circle/checkout/callback) stay real, fully functional, unchanged-
    in-payment-behavior SPA routes — but their raw server HTML must
    never be indexable, never carry a page-specific title that could be
    mistaken for real content, and — critically — can never leak a
    query-string payment/transaction reference, since Paystack always
    appends ?reference=...&trxref=... to these exact URLs on redirect
    back. Flask's <path:subpath> converter the backend route is built on
    only ever captures the PATH portion of a URL, never the query
    string (see app/__init__.py's spa_shell_fallback(subpath)) — so no
    query parameter can reach spa_shell.py's title/canonical/metadata
    logic even in principle, regardless of what's appended to the real
    browser URL.
    """

    def test_resources_checkout_callback_is_200_with_raw_noindex(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/resources/checkout/callback")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert _meta_content(html, "name", "robots") == "noindex, nofollow"
        assert "<title>Resource Payment | Women Shaping Futures</title>" in html

    def test_circle_checkout_callback_is_200_with_raw_noindex(self, client, app):
        _use_fixture_index(app)
        resp = client.get("/circle/checkout/callback")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert _meta_content(html, "name", "robots") == "noindex, nofollow"
        assert "<title>WSF Circle Payment | Women Shaping Futures</title>" in html

    def test_resources_checkout_callback_never_leaks_query_params_or_payment_references(self, client, app):
        # A real Paystack redirect looks like this — reference/trxref
        # must never appear anywhere in the raw response.
        _use_fixture_index(app)
        resp = client.get(
            "/resources/checkout/callback?reference=wsf_res_abc123&trxref=wsf_res_abc123&status=success"
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "wsf_res_abc123" not in html
        assert "reference" not in html
        assert "trxref" not in html
        assert _canonical_href(html) == "https://womenshapingfutures.org/resources/checkout/callback"
        assert _meta_content(html, "name", "robots") == "noindex, nofollow"

    def test_circle_checkout_callback_never_leaks_query_params_or_payment_references(self, client, app):
        _use_fixture_index(app)
        resp = client.get(
            "/circle/checkout/callback?reference=wsf_circle_xyz789&trxref=wsf_circle_xyz789&status=success"
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "wsf_circle_xyz789" not in html
        assert "reference" not in html
        assert "trxref" not in html
        assert _canonical_href(html) == "https://womenshapingfutures.org/circle/checkout/callback"
        assert _meta_content(html, "name", "robots") == "noindex, nofollow"

    def test_checkout_callbacks_carry_no_description_or_sitewide_structured_data(self, client, app):
        # These are not indexable content — no description, no
        # WebSite/Organization JSON-LD (matches every other noindex
        # utility route this phase covers).
        _use_fixture_index(app)
        for path in ("/resources/checkout/callback", "/circle/checkout/callback"):
            html = client.get(path).get_data(as_text=True)
            assert _meta_content(html, "name", "description") is None
            assert "data-site-structured-data" not in html
