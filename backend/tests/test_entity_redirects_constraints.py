"""WSF SEO Phase 2B — DB-level constraints on the new entity_redirects
table (migrations/versions/b62f72a7c22e_non_article_entity_redirects.py),
proven against direct ORM inserts that bypass the
create_entity_redirect_for_slug_change() helper entirely — same
"defense in depth, independent of the application layer" pattern
already used for CirclePlan/CircleSubscription's own CHECK constraints
in test_circle.py. See test_entity_redirects.py for the helper's own
behavioral coverage (chain collapse, reclamation, etc.) and
test_sitemap.py/test_entity_redirects_routing.py for the schema's two
other requirements (sitemap exclusion, same from_slug text allowed
across different entity types) proven at their own level.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db


def test_entity_type_and_from_slug_together_must_be_unique(app):
    from app.models.entity_redirect import EntityRedirect

    with app.app_context():
        db.session.add(EntityRedirect(entity_type="resource", from_slug="old-slug", to_slug="new-slug"))
        db.session.commit()

        db.session.add(EntityRedirect(entity_type="resource", from_slug="old-slug", to_slug="another-slug"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_same_from_slug_allowed_across_different_entity_types(app):
    from app.models.entity_redirect import EntityRedirect

    with app.app_context():
        db.session.add(EntityRedirect(entity_type="job", from_slug="old-role", to_slug="new-job-role"))
        db.session.add(EntityRedirect(entity_type="event", from_slug="old-role", to_slug="new-event-role"))
        db.session.commit()

        rows = EntityRedirect.query.filter_by(from_slug="old-role").all()
        assert {row.entity_type for row in rows} == {"job", "event"}


def test_invalid_entity_type_rejected_by_db_check_constraint(app):
    from app.models.entity_redirect import EntityRedirect

    with app.app_context():
        db.session.add(EntityRedirect(entity_type="article", from_slug="old-slug", to_slug="new-slug"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


@pytest.mark.parametrize(
    "entity_type", ["topic", "series", "person", "author", "opportunity", "job", "resource", "event"]
)
def test_every_supported_entity_type_is_accepted(app, entity_type):
    from app.models.entity_redirect import EntityRedirect

    with app.app_context():
        db.session.add(EntityRedirect(entity_type=entity_type, from_slug=f"old-{entity_type}", to_slug=f"new-{entity_type}"))
        db.session.commit()
        assert EntityRedirect.query.filter_by(entity_type=entity_type, from_slug=f"old-{entity_type}").first() is not None


def test_migration_module_matches_the_model(app):
    """This test DB is built from the models via db.create_all() (see
    tests/conftest.py), not by running the Alembic chain, so the real
    migration's upgrade()/downgrade() aren't exercised by the suite —
    separately confirmed manually in the dev DB (`flask db upgrade`
    followed by `flask db heads` reporting a single head, this
    revision, with down_revision chaining from 4082ec5bec43). This test
    only guards against the migration module and the model silently
    drifting apart (same supported entity_type values, correct
    down_revision).
    """
    import importlib

    migration = importlib.import_module(
        "migrations.versions.b62f72a7c22e_non_article_entity_redirects"
    )
    assert migration.down_revision == "4082ec5bec43"
    assert hasattr(migration, "upgrade") and hasattr(migration, "downgrade")
    assert migration.ENTITY_REDIRECT_TYPES == (
        "topic", "series", "person", "author", "opportunity", "job", "resource", "event",
    )
