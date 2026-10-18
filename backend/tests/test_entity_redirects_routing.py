"""WSF SEO Phase 2B — public-route behavior for the 8 non-Article nested
detail routes (/topics, /series, /people, /authors, /opportunities,
/jobs, /resources, /events), driven entirely through the raw Flask SPA
catch-all (app/services/spa_shell.py's resolve_spa_response), the same
way tests/test_spa_shell.py already covers the flat Article route.

Covers, per entity type: a stale slug 301s to the current one with the
correct relative Location, the current slug still 200s, the stale slug
never 200s, a second rename collapses to a one-hop redirect from every
prior slug, the live entity always wins over redirect history even when
a stale row happens to share its slug text, and a slug nobody ever used
404s. See test_entity_redirects.py for the lower-level
create_entity_redirect_for_slug_change() unit coverage this exercises
through the actual route instead.
"""
import datetime

import pytest

from app.extensions import db


def _make_topic(app, slug, status="published", name="A Topic"):
    from app.models.taxonomy import Topic

    with app.app_context():
        row = Topic(slug=slug, name=name, status=status)
        db.session.add(row)
        db.session.commit()
        return row.id


def _make_series(app, slug, status="published", name="A Series"):
    from app.models.taxonomy import Series

    with app.app_context():
        row = Series(slug=slug, name=name, status=status)
        db.session.add(row)
        db.session.commit()
        return row.id


def _make_person(app, slug, status="published", name="A Person"):
    from app.models.people import Person

    with app.app_context():
        row = Person(slug=slug, name=name, status=status, bio=[])
        db.session.add(row)
        db.session.commit()
        return row.id


def _make_author(app, slug, status="active", name="An Author"):
    from app.models.people import Author

    with app.app_context():
        row = Author(slug=slug, name=name, status=status)
        db.session.add(row)
        db.session.commit()
        return row.id


def _make_opportunity(app, slug, status="published", title="An Opportunity"):
    from app.models.opportunity import Opportunity

    with app.app_context():
        row = Opportunity(slug=slug, title=title, status=status, description=[])
        db.session.add(row)
        db.session.commit()
        return row.id


def _make_job(app, slug, status="published", title="A Job"):
    from app.models.opportunity import Job

    with app.app_context():
        row = Job(slug=slug, title=title, status=status, company_name="A Company", description=[])
        db.session.add(row)
        db.session.commit()
        return row.id


def _make_resource(app, slug, status="published", name="A Resource"):
    from app.models.resource import Resource

    with app.app_context():
        row = Resource(slug=slug, name=name, status=status, description=[])
        db.session.add(row)
        db.session.commit()
        return row.id


def _make_event(app, slug, status="published", title="An Event"):
    from app.models.opportunity import Event

    with app.app_context():
        row = Event(slug=slug, title=title, status=status, description=[], date=datetime.date.today())
        db.session.add(row)
        db.session.commit()
        return row.id


def _make_entity_redirect(app, entity_type, from_slug, to_slug):
    from app.models.entity_redirect import EntityRedirect

    with app.app_context():
        row = EntityRedirect(entity_type=entity_type, from_slug=from_slug, to_slug=to_slug)
        db.session.add(row)
        db.session.commit()
        return row.id


# (url_prefix, entity_type, factory)
ENTITY_ROUTES = [
    ("topics", "topic", _make_topic),
    ("series", "series", _make_series),
    ("people", "person", _make_person),
    ("authors", "author", _make_author),
    ("opportunities", "opportunity", _make_opportunity),
    ("jobs", "job", _make_job),
    ("resources", "resource", _make_resource),
    ("events", "event", _make_event),
]


class TestEntityRedirectRouting:
    @pytest.mark.parametrize("prefix,entity_type,make", ENTITY_ROUTES)
    def test_current_slug_resolves_200(self, client, app, prefix, entity_type, make):
        make(app, "current-slug")
        resp = client.get(f"/{prefix}/current-slug")
        assert resp.status_code == 200

    @pytest.mark.parametrize("prefix,entity_type,make", ENTITY_ROUTES)
    def test_unknown_slug_404s(self, client, app, prefix, entity_type, make):
        resp = client.get(f"/{prefix}/never-existed")
        assert resp.status_code == 404

    @pytest.mark.parametrize("prefix,entity_type,make", ENTITY_ROUTES)
    def test_stale_slug_redirects_301_to_current(self, client, app, prefix, entity_type, make):
        make(app, "beta")
        _make_entity_redirect(app, entity_type, "alpha", "beta")

        resp = client.get(f"/{prefix}/alpha")
        assert resp.status_code == 301
        assert resp.headers["Location"] == f"/{prefix}/beta"

        # The stale slug must never also 200 — it only ever redirects.
        assert client.get(f"/{prefix}/alpha").status_code == 301

    @pytest.mark.parametrize("prefix,entity_type,make", ENTITY_ROUTES)
    def test_one_hop_chain_collapse_through_route(self, client, app, prefix, entity_type, make):
        make(app, "gamma")
        # Simulates alpha->beta->gamma already collapsed at write time
        # (see test_entity_redirects.py's own chain-collapse coverage) —
        # both original slugs must redirect straight to the final one,
        # never through an intermediate hop.
        _make_entity_redirect(app, entity_type, "alpha", "gamma")
        _make_entity_redirect(app, entity_type, "beta", "gamma")

        resp_alpha = client.get(f"/{prefix}/alpha")
        assert resp_alpha.status_code == 301
        assert resp_alpha.headers["Location"] == f"/{prefix}/gamma"

        resp_beta = client.get(f"/{prefix}/beta")
        assert resp_beta.status_code == 301
        assert resp_beta.headers["Location"] == f"/{prefix}/gamma"

    @pytest.mark.parametrize("prefix,entity_type,make", ENTITY_ROUTES)
    def test_live_entity_wins_over_same_slug_redirect_row(self, client, app, prefix, entity_type, make):
        # A pathological/stale EntityRedirect row whose from_slug matches
        # a CURRENTLY LIVE entity's slug must never be followed — the
        # live entity lookup always runs first and, on a hit, the
        # redirect fallback below it is never even consulted.
        make(app, "reclaimed")
        _make_entity_redirect(app, entity_type, "reclaimed", "somewhere-else")

        resp = client.get(f"/{prefix}/reclaimed")
        assert resp.status_code == 200

    def test_cross_type_isolation_identical_slug_text(self, client, app):
        _make_job(app, "new-job-role")
        _make_event(app, "new-event-role")
        _make_entity_redirect(app, "job", "old-role", "new-job-role")
        _make_entity_redirect(app, "event", "old-role", "new-event-role")

        job_resp = client.get("/jobs/old-role")
        assert job_resp.status_code == 301
        assert job_resp.headers["Location"] == "/jobs/new-job-role"

        event_resp = client.get("/events/old-role")
        assert event_resp.status_code == 301
        assert event_resp.headers["Location"] == "/events/new-event-role"
