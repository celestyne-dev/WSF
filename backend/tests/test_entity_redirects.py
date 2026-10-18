"""WSF SEO Phase 2B — unit tests for the generalized non-Article entity
redirect model (app/models/entity_redirect.py) and its write helper
(app/services/entity_redirects.py's create_entity_redirect_for_slug_change).
Pure model/service-level coverage of the write algorithm itself — public
route resolution (the 301 fallback in spa_shell.py) and real update-
endpoint integration (the public-visibility-before-and-after gate) are
covered separately, in test_entity_redirects_routing.py and each entity's
own test_*.py respectively.
"""
from app.extensions import db
from app.models.entity_redirect import EntityRedirect
from app.services.entity_redirects import create_entity_redirect_for_slug_change


def _redirect(entity_type, from_slug):
    return EntityRedirect.query.filter_by(entity_type=entity_type, from_slug=from_slug).first()


def _count(entity_type, from_slug=None):
    query = EntityRedirect.query.filter_by(entity_type=entity_type)
    if from_slug is not None:
        query = query.filter_by(from_slug=from_slug)
    return query.count()


class TestCreateEntityRedirectForSlugChange:
    def test_first_redirect_creation(self, app):
        with app.app_context():
            create_entity_redirect_for_slug_change("job", "old-role", "new-role")
            db.session.commit()
            row = _redirect("job", "old-role")
            assert row is not None
            assert row.to_slug == "new-role"

    def test_noop_when_slug_unchanged(self, app):
        with app.app_context():
            create_entity_redirect_for_slug_change("job", "same-slug", "same-slug")
            db.session.commit()
            assert _count("job", "same-slug") == 0

    def test_one_hop_chain_collapse(self, app):
        # alpha -> beta, then beta -> gamma must leave exactly
        # alpha -> gamma and beta -> gamma — never alpha -> beta -> gamma.
        with app.app_context():
            create_entity_redirect_for_slug_change("resource", "alpha", "beta")
            db.session.commit()
            create_entity_redirect_for_slug_change("resource", "beta", "gamma")
            db.session.commit()

            alpha = _redirect("resource", "alpha")
            beta = _redirect("resource", "beta")
            assert alpha.to_slug == "gamma"
            assert beta.to_slug == "gamma"
            assert _count("resource") == 2

    def test_stale_from_slug_removed_on_slug_reclamation(self, app):
        # career-guide -> career-guide-v2 (the resource moved away from
        # career-guide). Later, a resource reclaims career-guide as its
        # live slug again — the stale redirect FROM career-guide must be
        # dropped so the live route always wins, never redirect-looped.
        with app.app_context():
            create_entity_redirect_for_slug_change("resource", "career-guide", "career-guide-v2")
            db.session.commit()
            create_entity_redirect_for_slug_change("resource", "career-guide-v2", "career-guide")
            db.session.commit()

            assert _redirect("resource", "career-guide") is None
            reclaimed_history = _redirect("resource", "career-guide-v2")
            assert reclaimed_history is not None
            assert reclaimed_history.to_slug == "career-guide"

    def test_same_slug_text_allowed_across_different_entity_types(self, app):
        with app.app_context():
            create_entity_redirect_for_slug_change("job", "old-role", "new-job-role")
            create_entity_redirect_for_slug_change("event", "old-role", "new-event-role")
            db.session.commit()

            job_row = _redirect("job", "old-role")
            event_row = _redirect("event", "old-role")
            assert job_row is not None and job_row.to_slug == "new-job-role"
            assert event_row is not None and event_row.to_slug == "new-event-role"

    def test_repeated_call_on_same_from_slug_updates_existing_row(self, app):
        # Exercises the direct from_slug match (not the bulk
        # to_slug-repoint chain-collapse path) — calling again with the
        # SAME old_slug must update that one row in place, never insert
        # a second row for the same (entity_type, from_slug).
        with app.app_context():
            create_entity_redirect_for_slug_change("series", "s-old", "s-mid")
            db.session.commit()
            first_id = _redirect("series", "s-old").id

            create_entity_redirect_for_slug_change("series", "s-old", "s-final")
            db.session.commit()

            row = _redirect("series", "s-old")
            assert row.id == first_id
            assert row.to_slug == "s-final"
            assert _count("series", "s-old") == 1

    def test_same_type_isolation_on_slug_reclamation(self, app):
        # A Job redirect FROM "shared-slug" must survive an unrelated
        # Event reclaiming "shared-slug" as ITS new live slug — the
        # reclamation delete is scoped by entity_type.
        with app.app_context():
            create_entity_redirect_for_slug_change("job", "shared-slug", "job-new")
            db.session.commit()
            create_entity_redirect_for_slug_change("event", "event-old", "shared-slug")
            db.session.commit()

            job_row = _redirect("job", "shared-slug")
            assert job_row is not None
            assert job_row.to_slug == "job-new"

    def test_same_type_isolation_on_chain_collapse(self, app):
        # A Job redirect x -> y must never be repointed by an unrelated
        # Event change that happens to target the same slug text y.
        with app.app_context():
            create_entity_redirect_for_slug_change("job", "x", "y")
            db.session.commit()
            create_entity_redirect_for_slug_change("event", "y", "z")
            db.session.commit()

            job_row = _redirect("job", "x")
            assert job_row.to_slug == "y"

    def test_does_not_commit_internally(self, app):
        # A rollback right after calling the helper (with no commit in
        # between) must undo the pending write — proof the helper only
        # flushes into the caller's existing transaction rather than
        # committing on its own.
        with app.app_context():
            create_entity_redirect_for_slug_change("author", "old-author", "new-author")
            db.session.rollback()
            assert _redirect("author", "old-author") is None
