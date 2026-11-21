"""Jobs and Opportunities date lifecycle (app/services/listing_lifecycle.py):
one rule for every public surface, closed listings leave live discovery by
date (no cron needed), detail URLs stay reachable as closed, and the
maintenance step keeps stored statuses accurate idempotently."""
import json
import os
import re
import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import auth_headers
from tests.test_job_circle_access import _give_active_circle

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
TODAY = date.today()
D = lambda n: TODAY + timedelta(days=n)  # noqa: E731
MEMBER = {"email": "lifecycle-member@example.com", "password": "supersecret1", "first_name": "C", "last_name": "M"}


@pytest.fixture(autouse=True)
def _index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _job(app, slug, **kw):
    from app.extensions import db
    from app.models.opportunity import Job

    fields = dict(title=slug.replace("-", " ").title(), status="published", access_type="public", company_name="Acme",
                  application_url="https://example.com/apply", description=[{"type": "paragraph", "text": "Role."}],
                  published_date=D(-3))
    fields.update(kw)
    with app.app_context():
        job = Job(slug=slug, **fields)
        db.session.add(job)
        db.session.commit()
        return job.id


def _opp(app, slug, **kw):
    from app.extensions import db
    from app.models.opportunity import Opportunity

    fields = dict(title=slug.replace("-", " ").title(), status="published", access_type="public", organization_name="Org",
                  application_url="https://example.com/apply", description=[{"type": "paragraph", "text": "Call."}], type="Grant",
                  published_date=D(-3))
    fields.update(kw)
    with app.app_context():
        opp = Opportunity(slug=slug, **fields)
        db.session.add(opp)
        db.session.commit()
        return opp.id


def _slugs(client, url):
    return [i["slug"] for i in client.get(url).get_json()["data"]]


# --- Jobs ----------------------------------------------------------------------------------

def _jobs_fixture(app):
    _job(app, "job-open", deadline=D(20))
    _job(app, "job-today", deadline=TODAY)
    _job(app, "job-yesterday", deadline=D(-1))
    _job(app, "job-expiry-yesterday", expiry_date=D(-1))
    _job(app, "job-legacy")  # no deadline, no expiry
    _job(app, "job-future", status="scheduled", published_date=D(5), deadline=D(30))
    _job(app, "job-scheduled-due", status="scheduled", published_date=D(-1), deadline=D(9))


def test_job_live_listing(client, app):
    _jobs_fixture(app)
    live = set(_slugs(client, "/api/v1/jobs?scope=public&pageSize=50"))
    assert live == {"job-open", "job-today", "job-legacy", "job-scheduled-due"}


def test_job_listing_same_for_editors_with_public_scope(client, app):
    from tests.test_footer_cms import _register_with_role

    _jobs_fixture(app)
    token = _register_with_role(client, app, {"email": "jl-admin@example.com", "password": "supersecret1",
                                              "first_name": "A", "last_name": "B"}, "admin")
    public = set(_slugs(client, "/api/v1/jobs?scope=public&pageSize=50"))
    as_editor = {i["slug"] for i in client.get("/api/v1/jobs?scope=public&pageSize=50", headers=auth_headers(token)).get_json()["data"]}
    assert as_editor == public
    studio = client.get("/api/v1/jobs?pageSize=50", headers=auth_headers(token)).get_json()["data"]
    states = {i["slug"]: i["effective_state"] for i in studio}
    assert states["job-yesterday"] == "deadline_passed" and states["job-future"] == "scheduled"
    assert states["job-today"] == "closing_soon" and states["job-legacy"] == "open"
    expired_filter = {i["slug"] for i in client.get("/api/v1/jobs?state=expired&pageSize=50", headers=auth_headers(token)).get_json()["data"]}
    assert expired_filter == {"job-yesterday", "job-expiry-yesterday"}


def test_job_payload_dates_and_closing(client, app):
    _job(app, "job-nine", deadline=D(9), expiry_date=D(30))
    _job(app, "job-soon", deadline=D(3))
    items = {i["slug"]: i for i in client.get("/api/v1/jobs?scope=public").get_json()["data"]}
    assert items["job-nine"]["closes_on"] == D(9).isoformat()
    assert items["job-nine"]["closing"] == {"closesOn": D(9).isoformat(), "daysLeft": 9, "closingSoon": False}
    assert items["job-soon"]["closing"]["closingSoon"] is True
    soon = _slugs(client, "/api/v1/jobs?scope=public&closingSoon=true")
    assert soon == ["job-soon"]
    # The frontend API client sends snake_case (closing_soon, salary_min).
    _job(app, "job-paid", deadline=D(20), salary_min=1000, salary_max=2000, currency="USD", salary_visible=True)
    assert "job-paid" not in _slugs(client, "/api/v1/jobs?scope=public&salary_min=5000")
    assert "job-paid" in _slugs(client, "/api/v1/jobs?scope=public&salary_min=1500")
    assert _slugs(client, "/api/v1/jobs?scope=public&closing_soon=true") == ["job-soon"]


def test_closed_job_detail_is_reachable_but_closed(client, app):
    _job(app, "job-done", deadline=D(-1))
    data = client.get("/api/v1/jobs/job-done").get_json()["data"]
    assert data["is_closed"] is True and data["closing"] is None
    assert "application_url" not in data and "application_email" not in data
    html = client.get("/jobs/job-done").get_data(as_text=True)
    assert 'content="noindex, follow"' in html
    assert "data-job-structured-data" not in html  # never an open JobPosting


def test_closed_job_access_denied_even_for_circle_member(client, app):
    _job(app, "job-circle-done", deadline=D(-1), access_type="circle_only")
    client.post("/api/v1/auth/register", json=MEMBER)
    _give_active_circle(app, MEMBER["email"])
    token = client.post("/api/v1/auth/login", json={"email": MEMBER["email"], "password": MEMBER["password"]}).get_json()["data"]["access_token"]
    resp = client.post("/api/v1/jobs/job-circle-done/access", headers=auth_headers(token))
    assert resp.status_code in (404, 409)
    assert "example.com/apply" not in resp.get_data(as_text=True)


def test_open_job_structured_data_valid_through_is_the_close_date(client, app):
    _job(app, "job-sd", deadline=D(9), expiry_date=D(5))
    html = client.get("/jobs/job-sd").get_data(as_text=True)
    ld = json.loads(re.search(r'data-job-structured-data="true">(.*?)</script>', html, re.S).group(1))
    assert ld["validThrough"] == D(5).isoformat() and ld["datePosted"] == D(-3).isoformat()


def test_closed_jobs_absent_from_homepage_hubs_search_sitemap(client, app):
    from app.services.homepage_collections import resolve_collection
    from app.services.public_hubs import jobs_hub
    from app.services.search import _search_jobs

    _jobs_fixture(app)
    _opps_fixture(app)
    with app.app_context():
        hub = {j["slug"] for j in jobs_hub(limit=20)}
        assert "job-yesterday" not in hub and "job-expiry-yesterday" not in hub and "job-open" in hub
        found = {r["url"] for r in _search_jobs("job", {})}
        assert "/jobs/job-yesterday" not in found and "/jobs/job-open" in found
        from types import SimpleNamespace

        for manual, slugs in ((False, []), (True, ["job-open", "job-yesterday", "job-expiry-yesterday"])):
            module = SimpleNamespace(config={"entityType": "jobs", "itemCount": 12, "slugs": slugs},
                                     selection_mode="manual" if manual else "automatic")
            got = {i["slug"] for i in resolve_collection(module)["items"]}
            assert "job-yesterday" not in got and "job-expiry-yesterday" not in got and "job-open" in got
            module = SimpleNamespace(config={"entityType": "opportunities", "itemCount": 12, "slugs": []}, selection_mode="automatic")
            assert {"opp-yesterday", "opp-future"}.isdisjoint({i["slug"] for i in resolve_collection(module)["items"]})
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/jobs/job-open<" in sitemap and "/jobs/job-yesterday<" not in sitemap


def test_job_date_validation(client, app):
    from tests.test_footer_cms import _register_with_role
    from tests.test_job_circle_access import _base_payload

    token = _register_with_role(client, app, {"email": "jv-admin@example.com", "password": "supersecret1",
                                              "first_name": "A", "last_name": "B"}, "admin")
    bad = client.post("/api/v1/jobs", json=_base_payload(publishedDate=D(5).isoformat(), deadline=D(1).isoformat()), headers=auth_headers(token))
    assert bad.status_code == 422
    bad = client.post("/api/v1/jobs", json=_base_payload(deadline=D(10).isoformat(), expiryDate=D(5).isoformat()), headers=auth_headers(token))
    assert bad.status_code == 422
    ok = client.post("/api/v1/jobs", json=_base_payload(), headers=auth_headers(token))  # no deadline: legacy-style allowed
    assert ok.status_code == 201, ok.get_json()


# --- Opportunities -------------------------------------------------------------------------

def _opps_fixture(app):
    _opp(app, "opp-open", deadline=D(30), type="Grant")
    _opp(app, "opp-opens-today", opening_date=TODAY, deadline=D(30), type="Scholarship")
    _opp(app, "opp-today", deadline=TODAY, type="Fellowship")
    _opp(app, "opp-future", opening_date=D(10), deadline=D(40), type="Fellowship")
    _opp(app, "opp-yesterday", deadline=D(-1))
    _opp(app, "opp-expired", expiry_date=D(-1))
    _opp(app, "opp-legacy")
    _opp(app, "opp-closed-status", status="closed", deadline=D(30))


def test_opportunity_default_list_is_open_only(client, app):
    _opps_fixture(app)
    assert set(_slugs(client, "/api/v1/opportunities?scope=public&pageSize=50")) == {
        "opp-open", "opp-opens-today", "opp-today", "opp-legacy"}
    assert _slugs(client, "/api/v1/opportunities?scope=public&state=upcoming") == ["opp-future"]
    assert set(_slugs(client, "/api/v1/opportunities?scope=public&closing_soon=true")) == {"opp-today"}


def test_opportunity_types_preserved(client, app):
    _opps_fixture(app)
    assert _slugs(client, "/api/v1/opportunities?scope=public&type=Scholarship") == ["opp-opens-today"]
    assert _slugs(client, "/api/v1/opportunities?scope=public&type=Fellowship") == ["opp-today"]
    assert set(_slugs(client, "/api/v1/opportunities?scope=public&type=Grant")) == {"opp-open", "opp-legacy"}


def test_opportunity_states_and_details(client, app):
    _opps_fixture(app)
    future = client.get("/api/v1/opportunities/opp-future").get_json()["data"]
    assert future["state"] == "upcoming" and "application_url" not in future
    resp = client.post("/api/v1/opportunities/opp-future/access")
    assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "application_not_open"
    closed = client.get("/api/v1/opportunities/opp-yesterday").get_json()["data"]
    assert closed["state"] == "closed" and closed["is_closed"] is True and "application_url" not in closed
    assert client.get("/api/v1/opportunities/opp-closed-status").status_code == 200  # stored closed keeps its URL
    assert client.post("/api/v1/opportunities/opp-yesterday/access").status_code == 409
    html = client.get("/opportunities/opp-yesterday").get_data(as_text=True)
    assert 'content="noindex, follow"' in html and "Applications closed" in html


def test_closed_circle_opportunity_never_leaks_destination(client, app):
    _opp(app, "opp-circle-done", deadline=D(-1), access_type="circle_only", application_url="https://secret.example/apply")
    client.post("/api/v1/auth/register", json=MEMBER)
    _give_active_circle(app, MEMBER["email"])
    token = client.post("/api/v1/auth/login", json={"email": MEMBER["email"], "password": MEMBER["password"]}).get_json()["data"]["access_token"]
    assert "secret.example" not in client.get("/api/v1/opportunities/opp-circle-done", headers=auth_headers(token)).get_data(as_text=True)
    resp = client.post("/api/v1/opportunities/opp-circle-done/access", headers=auth_headers(token))
    assert resp.status_code == 409 and "secret.example" not in resp.get_data(as_text=True)


def test_closed_opportunities_absent_from_hubs_search_sitemap(client, app):
    from app.services.public_hubs import opportunities_hub
    from app.services.search import _search_opportunities

    _opps_fixture(app)
    with app.app_context():
        hub = {o["slug"] for o in opportunities_hub(limit=20)}
        assert hub == {"opp-open", "opp-opens-today", "opp-today", "opp-legacy"}
        found = {r["url"] for r in _search_opportunities("opp", {})}
        assert "/opportunities/opp-yesterday" not in found and "/opportunities/opp-future" not in found
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/opportunities/opp-open<" in sitemap and "/opportunities/opp-future<" in sitemap
    assert "/opportunities/opp-yesterday<" not in sitemap


def test_opportunity_date_validation(client, app):
    from tests.test_footer_cms import _register_with_role

    token = _register_with_role(client, app, {"email": "ov-admin@example.com", "password": "supersecret1",
                                              "first_name": "A", "last_name": "B"}, "admin")
    base = {"title": "Validation Grant", "organizationName": "Org", "type": "Grant", "status": "draft"}
    assert client.post("/api/v1/opportunities", json={**base, "openingDate": D(5).isoformat(), "deadline": D(1).isoformat()},
                       headers=auth_headers(token)).status_code == 422
    assert client.post("/api/v1/opportunities", json={**base, "deadline": D(9).isoformat(), "expiryDate": D(2).isoformat()},
                       headers=auth_headers(token)).status_code == 422
    assert client.post("/api/v1/opportunities", json={**base, "openingDate": D(9).isoformat(), "expiryDate": D(2).isoformat()},
                       headers=auth_headers(token)).status_code == 422
    assert client.post("/api/v1/opportunities", json=base, headers=auth_headers(token)).status_code == 201


# --- Maintenance -----------------------------------------------------------------------------

def test_expire_closed_listings_is_idempotent(app):
    from app.extensions import db
    from app.models.opportunity import Job, Opportunity
    from app.services.listing_maintenance import expire_closed_listings

    _jobs_fixture(app)
    _opps_fixture(app)
    _job(app, "job-draft-past", status="draft", deadline=D(-5))
    with app.app_context():
        first = expire_closed_listings()
        assert len(first["jobs"]) == 2 and len(first["opportunities"]) == 2
        statuses = {j.slug: j.status for j in Job.query.all()}
        assert statuses["job-yesterday"] == "expired" and statuses["job-expiry-yesterday"] == "expired"
        assert statuses["job-today"] == "published" and statuses["job-legacy"] == "published"
        assert statuses["job-draft-past"] == "draft"  # never touches drafts
        opp_statuses = {o.slug: o.status for o in Opportunity.query.all()}
        assert opp_statuses["opp-yesterday"] == "closed" and opp_statuses["opp-expired"] == "closed"
        assert opp_statuses["opp-legacy"] == "published" and opp_statuses["opp-future"] == "published"
        assert expire_closed_listings() == {"jobs": [], "opportunities": []}
        assert db.session.query(Job).count() == 8  # nothing deleted
    # Expired detail stays reachable as closed.
    assert app.test_client().get("/api/v1/jobs/job-yesterday").get_json()["data"]["is_closed"] is True


def test_maintenance_commands(app):
    _job(app, "job-cmd", deadline=D(-2))
    runner = app.test_cli_runner()
    out = runner.invoke(args=["publish-due-content"]).output
    assert "Expired 1 job(s); closed 0 opportunity(ies)." in out
    assert "Expired 0 job(s)" in runner.invoke(args=["expire-closed-listings"]).output


def test_lifecycle_unit_rules():
    from types import SimpleNamespace as J

    from app.services.listing_lifecycle import closing_info, job_is_live, opportunity_state

    assert job_is_live(J(status="published", published_date=D(-1), deadline=TODAY, expiry_date=None))
    assert not job_is_live(J(status="published", published_date=D(-1), deadline=D(-1), expiry_date=None))
    assert not job_is_live(J(status="expired", published_date=D(-9), deadline=D(9), expiry_date=None))
    assert job_is_live(J(status="published", published_date=None, deadline=None, expiry_date=None))
    assert opportunity_state(J(status="published", opening_date=TODAY, deadline=None, expiry_date=None)) == "open"
    assert opportunity_state(J(status="published", opening_date=D(1), deadline=None, expiry_date=None)) == "upcoming"
    assert opportunity_state(J(status="closed", opening_date=None, deadline=D(9), expiry_date=None)) == "closed"
    assert closing_info(TODAY)["daysLeft"] == 0 and closing_info(TODAY)["closingSoon"] is True
    assert closing_info(D(8))["closingSoon"] is False


# --- Publication-history boundary (a closed record must have been public) -------------------

def _make_status(app, model, slug, status):
    from app.extensions import db
    from app.models.opportunity import Job, Opportunity

    with app.app_context():
        row = (Job if model == "job" else Opportunity).query.filter_by(slug=slug).first()
        row.status = status
        db.session.commit()


def _public(client, path):
    return client.get(f"/api/v1/{path}").status_code, client.get(f"/{path}").status_code


def test_job_publication_history_boundary(client, app):
    # published -> expired: historical closed detail stays reachable, no destination.
    _job(app, "hist-job", deadline=D(10), application_email="hr@example.com")
    _make_status(app, "job", "hist-job", "expired")
    assert _public(client, "jobs/hist-job") == (200, 200)
    data = client.get("/api/v1/jobs/hist-job").get_json()["data"]
    assert data["is_closed"] is True and "application_url" not in data and "application_email" not in data
    assert client.post("/api/v1/jobs/hist-job/access").status_code == 409
    # draft -> expired with no published_date: never public.
    _job(app, "never-job", status="draft", published_date=None)
    _make_status(app, "job", "never-job", "expired")
    assert _public(client, "jobs/never-job") == (404, 404)
    assert client.post("/api/v1/jobs/never-job/access").status_code == 404
    # expired with a future publication date: never public.
    _job(app, "future-exp-job", status="expired", published_date=D(5))
    assert _public(client, "jobs/future-exp-job") == (404, 404)
    # archived: private even with history.
    _job(app, "arch-job", status="archived")
    assert _public(client, "jobs/arch-job") == (404, 404)


def test_opportunity_publication_history_boundary(client, app):
    _opp(app, "hist-opp", deadline=D(10), application_url="https://secret.example/apply")
    _make_status(app, "opp", "hist-opp", "closed")
    assert _public(client, "opportunities/hist-opp") == (200, 200)
    data = client.get("/api/v1/opportunities/hist-opp").get_json()["data"]
    assert data["state"] == "closed" and "application_url" not in data
    resp = client.post("/api/v1/opportunities/hist-opp/access")
    assert resp.status_code == 409 and "secret.example" not in resp.get_data(as_text=True)
    # draft -> closed with no published_date does NOT publish it.
    _opp(app, "never-opp", status="draft", published_date=None)
    _make_status(app, "opp", "never-opp", "closed")
    assert _public(client, "opportunities/never-opp") == (404, 404)
    assert client.post("/api/v1/opportunities/never-opp/access").status_code == 404
    _opp(app, "future-closed-opp", status="closed", published_date=D(5))
    assert _public(client, "opportunities/future-closed-opp") == (404, 404)
    _opp(app, "arch-opp", status="archived")
    assert _public(client, "opportunities/arch-opp") == (404, 404)
    assert client.post("/api/v1/opportunities/arch-opp/access").status_code == 404


def test_publication_history_unit_rule():
    from types import SimpleNamespace as R

    from app.services.listing_lifecycle import job_is_reachable, opportunity_is_reachable

    assert job_is_reachable(R(status="expired", published_date=D(-1)))
    assert not job_is_reachable(R(status="expired", published_date=None))
    assert not job_is_reachable(R(status="expired", published_date=D(1)))
    assert job_is_reachable(R(status="published", published_date=None))  # legacy published rows stay public
    assert not job_is_reachable(R(status="archived", published_date=D(-9)))
    assert opportunity_is_reachable(R(status="closed", published_date=TODAY))
    assert not opportunity_is_reachable(R(status="closed", published_date=None))
    assert not opportunity_is_reachable(R(status="draft", published_date=D(-9)))
