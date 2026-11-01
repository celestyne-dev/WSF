"""AI Search / GEO Phase 3B1 — visible, semantic public content inside
#root for Job/Opportunity/Event/Resource/Learning/Organization detail
pages (app/services/prerender.py), proven on raw HTML only (no JS).
"""
import json
import os
import re
from datetime import date, timedelta

import pytest

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
SITE = "https://womenshapingfutures.org"


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _html(client, path):
    resp = client.get(path)
    return resp.status_code, resp.get_data(as_text=True)


def _root(html):
    match = re.search(r'<div id="root">(.*?)</div>\s*<script type="module"', html, re.DOTALL)
    return match.group(1) if match else ""


def _count_script(html, attr):
    return len(re.findall(rf"<script\b[^>]*{re.escape(attr)}", html))


def _canonical(html):
    match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html)
    return match.group(1) if match else None


def _add(app, obj):
    with app.app_context():
        db.session.add(obj)
        db.session.commit()
        return obj.id


def _body(text):
    return [{"type": "paragraph", "text": text}]


def _assert_valid_detail(html, kind, title, body_text, canonical, entity_attr=None):
    root = _root(html)
    assert root.startswith(f'<main data-wsf-prerender="{kind}"')
    assert html.count("data-wsf-prerender=") == 1
    assert len(re.findall(r"<h1\b", root)) == 1
    assert re.search(rf"<h1[^>]*>{re.escape(title)}</h1>", root)
    assert body_text in root
    assert _canonical(html) == canonical
    assert _count_script(html, "data-breadcrumb-structured-data") == 1
    assert _count_script(html, "data-site-structured-data") == 1
    if entity_attr:
        assert _count_script(html, entity_attr) == 1
    lowered = root.lower()
    for hidden in (" hidden", "display:none", "visibility:hidden", 'aria-hidden="true"'):
        assert hidden not in lowered
    assert "<noscript" not in html.lower()
    return root


# --- Jobs -----------------------------------------------------------------------


def test_job_prerender(client, app):
    from app.models.opportunity import Job

    _add(app, Job(
        slug="program-manager", title="Program Manager", company_name="Kaziwave", status="published",
        location="Nairobi", work_mode="Hybrid", employment_type="Full-time",
        short_description="Lead our programs team.", description=_body("JOB-BODY-TEXT"),
        responsibilities=["Own the roadmap"], requirements=["5 years experience"], skills=["Facilitation"],
        salary_min=100000, salary_max=150000, currency="KES", salary_period="year", salary_visible=True,
        deadline=date.today() + timedelta(days=30), application_url="https://kaziwave.example.com/apply",
    ))
    status, html = _html(client, "/jobs/program-manager")
    assert status == 200
    root = _assert_valid_detail(html, "job", "Program Manager", "JOB-BODY-TEXT", f"{SITE}/jobs/program-manager", "data-job-structured-data")
    for text in ("Kaziwave", "Nairobi", "Hybrid", "Full-time", "Lead our programs team.", "Own the roadmap",
                 "5 years experience", "Facilitation", "KES 100,000 – 150,000 per year"):
        assert text in root, text
    assert re.search(r"<h2[^>]*>Responsibilities</h2>", root)
    # Public, open job: the public builder attaches the apply link, so it shows.
    assert 'href="https://kaziwave.example.com/apply"' in root


def test_job_private_application_channel_and_hidden_salary_never_leak(client, app):
    from app.models.opportunity import Job

    _add(app, Job(
        slug="circle-role", title="Circle Role", company_name="Kaziwave", status="published", access_type="circle_only",
        description=_body("Circle job body."), application_url="https://secret.example.com/apply",
        application_email="secret-hiring@example.com", application_instructions="SECRET-INSTRUCTIONS",
        salary_min=999999, salary_visible=False,
    ))
    _, html = _html(client, "/jobs/circle-role")
    for secret in ("secret.example.com", "secret-hiring@example.com", "SECRET-INSTRUCTIONS", "999,999", "999999"):
        assert secret not in html, secret


def test_expired_and_future_jobs_get_no_prerender(client, app):
    from app.models.opportunity import Job

    _add(app, Job(slug="expired-job", title="Expired Job Title", company_name="X", status="expired", description=_body("EXPIRED-BODY")))
    _add(app, Job(slug="future-job", title="Future Job Title", company_name="X", status="scheduled",
                  published_date=date.today() + timedelta(days=5), description=_body("FUTURE-BODY")))
    for path, secrets in (("/jobs/expired-job", ("Expired Job Title", "EXPIRED-BODY")), ("/jobs/future-job", ("Future Job Title", "FUTURE-BODY"))):
        status, html = _html(client, path)
        assert status == 404
        assert "data-wsf-prerender" not in html
        for secret in secrets:
            assert secret not in html


# --- Opportunities -------------------------------------------------------------------


def test_opportunity_prerender(client, app):
    from app.models.opportunity import Opportunity

    _add(app, Opportunity(
        slug="global-fellowship", title="Global Fellowship", status="published", type="Fellowship",
        organization_name="Global Fund", short_description="A year-long fellowship.",
        description=_body("OPPORTUNITY-BODY-TEXT"), eligibility="Women in tech under 35.",
        deadline=date.today() + timedelta(days=20), application_url="https://fund.example.org/apply",
    ))
    status, html = _html(client, "/opportunities/global-fellowship")
    assert status == 200
    root = _assert_valid_detail(html, "opportunity", "Global Fellowship", "OPPORTUNITY-BODY-TEXT", f"{SITE}/opportunities/global-fellowship")
    assert "Global Fund" in root and "Fellowship" in root and "Women in tech under 35." in root
    assert re.search(r"<h2[^>]*>Eligibility</h2>", root)


def test_circle_only_opportunity_never_shows_application_target(client, app):
    from app.models.opportunity import Opportunity

    _add(app, Opportunity(slug="circle-grant", title="Circle Grant", status="published", access_type="circle_only",
                          description=_body("Grant body."), application_url="https://hidden-grant.example.org/apply",
                          application_instructions="HIDDEN-GRANT-STEPS"))
    _, html = _html(client, "/opportunities/circle-grant")
    assert "hidden-grant.example.org" not in html and "HIDDEN-GRANT-STEPS" not in html


# --- Events ---------------------------------------------------------------------------


def test_event_prerender_and_registrations_never_leak(client, app):
    from app.models.event_registration import EventRegistration
    from app.models.opportunity import Event, EventSpeaker
    from app.models.user import User

    event_id = _add(app, Event(
        slug="wsf-summit", title="WSF Summit", status="published", date=date.today() + timedelta(days=40),
        format="in-person", venue="KICC", city="Nairobi", timezone="Africa/Nairobi", organizer_name="WSF",
        short_description="Our annual summit.", description=_body("EVENT-BODY-TEXT"),
        agenda=[{"time": "09:00", "title": "Opening keynote"}], registration_url="https://tickets.example.org/wsf",
        virtual_link="https://zoom.example.com/SECRET-MEETING",
    ))
    with app.app_context():
        db.session.add(EventSpeaker(event_id=event_id, name="Amara Okafor", title="CEO", organization_name="Kaziwave"))
        attendee = User(email="attendee-private@example.com", first_name="Private", last_name="Attendeename",
                        country_code="US", password_hash="x")
        db.session.add(attendee)
        db.session.flush()
        db.session.add(EventRegistration(event_id=event_id, user_id=attendee.id))
        db.session.commit()

    status, html = _html(client, "/events/wsf-summit")
    assert status == 200
    root = _assert_valid_detail(html, "event", "WSF Summit", "EVENT-BODY-TEXT", f"{SITE}/events/wsf-summit", "data-event-structured-data")
    for text in ("Hosted by WSF", "KICC", "Nairobi", "Opening keynote", "Amara Okafor", "Our annual summit."):
        assert text in root, text
    assert "<address" in root
    assert 'href="https://tickets.example.org/wsf"' in root
    for secret in ("attendee-private@example.com", "Attendeename", "SECRET-MEETING", "zoom.example.com"):
        assert secret not in html, secret


def test_draft_event_404_no_leak(client, app):
    from app.models.opportunity import Event

    _add(app, Event(slug="draft-event", title="Draft Event Title", status="draft", date=date(2026, 6, 1), description=_body("DRAFT-EVENT-BODY")))
    status, html = _html(client, "/events/draft-event")
    assert status == 404
    assert "Draft Event Title" not in html and "DRAFT-EVENT-BODY" not in html and "data-wsf-prerender" not in html


# --- Resources (security critical) --------------------------------------------------------


def test_resource_prerender_never_exposes_protected_delivery_data(client, app):
    from app.models.resource import Resource, ResourcePurchase
    from app.models.user import User

    resource_id = _add(app, Resource(
        slug="pay-negotiation-kit", name="Pay Negotiation Kit", status="published", type="Toolkit",
        access_type="premium", price=1500, currency="KES", short_description="Scripts for your next raise.",
        description=_body("RESOURCE-BODY-TEXT"), author_name="WSF Editorial",
        file_url="https://files.example.com/SECRET-FILE-URL.pdf", external_url="https://external.example.com/SECRET-EXTERNAL",
        protected_file_path="/srv/protected/SECRET-PROTECTED-PATH.pdf",
    ))
    with app.app_context():
        buyer = User(email="buyer-private@example.com", first_name="Buyer", last_name="Privatename", country_code="US", password_hash="x")
        db.session.add(buyer)
        db.session.flush()
        db.session.add(ResourcePurchase(user_id=buyer.id, resource_id=resource_id, payment_reference="PAY-REF-SECRET-123", status="active"))
        db.session.commit()

    status, html = _html(client, "/resources/pay-negotiation-kit")
    assert status == 200
    root = _assert_valid_detail(html, "resource", "Pay Negotiation Kit", "RESOURCE-BODY-TEXT",
                                f"{SITE}/resources/pay-negotiation-kit", "data-resource-structured-data")
    assert "Scripts for your next raise." in root and "Premium" in root and "KES 1,500" in root
    for secret in ("SECRET-FILE-URL", "files.example.com", "SECRET-EXTERNAL", "SECRET-PROTECTED-PATH", "/srv/protected",
                   "PAY-REF-SECRET-123", "buyer-private@example.com", "Privatename", "viewerAccessSource"):
        assert secret not in root, secret
    for secret in ("SECRET-FILE-URL", "SECRET-EXTERNAL", "SECRET-PROTECTED-PATH", "PAY-REF-SECRET-123", "buyer-private@example.com"):
        assert secret not in html, secret


# --- Learning (security critical) ------------------------------------------------------------


def _instructor(app):
    from app.models.people import Author

    return _add(app, Author(slug="geo3-instructor", name="Dr. Wanjiru", status="active"))


@pytest.mark.parametrize("access_type", ["free", "circle_only"])
def test_learning_prerender_never_contains_modules_or_lessons(client, app, access_type):
    from app.models.learning import LearningLesson, LearningModule, LearningProgram

    instructor_id = _instructor(app)
    with app.app_context():
        program = LearningProgram(
            slug="leading-with-purpose", title="Leading With Purpose", status="published", access_type=access_type,
            primary_instructor_id=instructor_id, short_description="A six-week leadership course.",
            overview=_body("LEARNING-OVERVIEW-TEXT"), learning_outcomes=["Run better meetings"],
            prerequisites=["None"], duration_value=6, duration_unit="weeks", difficulty_level="beginner",
        )
        db.session.add(program)
        db.session.flush()
        module = LearningModule(learning_program_id=program.id, title="SECRET-MODULE-TITLE", sort_order=0)
        db.session.add(module)
        db.session.flush()
        db.session.add(LearningLesson(
            module_id=module.id, title="SECRET-LESSON-TITLE", lesson_type="text",
            content=_body("SECRET-LESSON-BODY"), summary="SECRET-LESSON-SUMMARY", sort_order=0,
            external_url="https://video.example.org/SECRET-LESSON-VIDEO",
        ))
        db.session.commit()

    status, html = _html(client, "/learning/leading-with-purpose")
    assert status == 200
    root = _assert_valid_detail(html, "learning", "Leading With Purpose", "LEARNING-OVERVIEW-TEXT", f"{SITE}/learning/leading-with-purpose")
    for text in ("A six-week leadership course.", "Run better meetings", "Dr. Wanjiru", "6 weeks", "Beginner"):
        assert text in root, text
    assert re.search(r"<h2[^>]*>What you&#x27;ll learn</h2>", root)
    for secret in ("SECRET-MODULE-TITLE", "SECRET-LESSON-TITLE", "SECRET-LESSON-BODY", "SECRET-LESSON-SUMMARY", "SECRET-LESSON-VIDEO"):
        assert secret not in html, secret


# --- Organizations ---------------------------------------------------------------------------


def test_organization_prerender(client, app):
    from app.models.people import Organization

    _add(app, Organization(slug="kaziwave", name="Kaziwave Labs", status="published", short_description="A fintech lab.",
                           description=_body("ORGANIZATION-BODY-TEXT"), industry="Fintech", location="Nairobi",
                           founded_year=2019, website="https://kaziwave.example.com", org_type="company"))
    status, html = _html(client, "/organizations/kaziwave")
    assert status == 200
    root = _assert_valid_detail(html, "organization", "Kaziwave Labs", "ORGANIZATION-BODY-TEXT", f"{SITE}/organizations/kaziwave", "data-org-structured-data")
    for text in ("A fintech lab.", "Fintech", "Nairobi", "2019", "Company"):
        assert text in root, text
    assert 'href="https://kaziwave.example.com"' in root


def test_archived_organization_404_no_leak(client, app):
    from app.models.people import Organization

    _add(app, Organization(slug="old-org", name="Old Org Name", status="archived", description=_body("OLD-ORG-BODY")))
    status, html = _html(client, "/organizations/old-org")
    assert status == 404
    assert "Old Org Name" not in html and "OLD-ORG-BODY" not in html and "data-wsf-prerender" not in html


# --- shared escaping / redirects / untouched families -----------------------------------------------


def test_hostile_text_is_escaped(client, app):
    from app.models.opportunity import Opportunity

    _add(app, Opportunity(
        slug="hostile", title="<script>alert(1)</script>Grant", status="published",
        organization_name="<img src=x onerror=alert(1)>", eligibility="<b onclick=alert(1)>bold</b>",
        description=[{"type": "paragraph", "text": '</p><script>alert(2)</script><a href="javascript:alert(3)">x</a>'}],
        application_url="javascript:alert(4)",
    ))
    _, html = _html(client, "/opportunities/hostile")
    root = _root(html)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;Grant" in root
    assert "&lt;img src=x onerror=alert(1)&gt;" in root
    assert "<script" not in root and "<img" not in root
    # Escaped text like "&lt;b onclick=...&gt;" is inert; no live tag may carry a handler.
    assert not re.search(r"<[a-z][^>]*\son[a-z]+\s*=", root, re.IGNORECASE)
    assert not re.search(r"""href\s*=\s*["']?javascript:""", root, re.IGNORECASE)


def test_redirected_old_slug_is_a_301_without_body(client, app):
    from app.models.entity_redirect import EntityRedirect
    from app.models.opportunity import Job

    _add(app, Job(slug="new-role", title="New Role", company_name="X", status="published", description=_body("NEW-ROLE-BODY")))
    _add(app, EntityRedirect(entity_type="job", from_slug="old-role", to_slug="new-role"))
    resp = client.get("/jobs/old-role")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/jobs/new-role")
    assert "NEW-ROLE-BODY" not in resp.get_data(as_text=True)
    assert "data-wsf-prerender" not in resp.get_data(as_text=True)


def test_other_detail_families_keep_empty_root(client, app):
    from app.models.taxonomy import Topic

    _add(app, Topic(slug="money", name="Money", status="published"))
    _, html = _html(client, "/topics/money")
    assert "data-wsf-prerender" not in html
