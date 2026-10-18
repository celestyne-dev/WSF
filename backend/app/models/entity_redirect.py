"""WSF SEO Phase 2B — "Non-Article Slug Change Redirects". Generalizes the
proven Article Redirect pattern (app/models/article.py's Redirect, written
by app/services/slugs.py's create_redirect_for_slug_change) to every other
public, slug-addressed, nested-route entity: Topic, Series, Person, Author,
Opportunity, Job, Resource, Event.

A single shared table, not eight — but NOT the Article Redirect table
either: that table's `from_slug` is globally unique, which is correct for
Article's flat /<slug> namespace but wrong here, since /jobs/example and
/events/example may legitimately coexist. Uniqueness here is scoped by
entity_type instead (see create_entity_redirect_for_slug_change in
app/services/entity_redirects.py for the write-time chain-collapse and
slug-reclamation logic that keeps this table always a single hop).

entity_type values are the same singular noun each entity's own slug
column conceptually belongs to — "topic"/"series"/"person"/"author"/
"opportunity"/"job"/"resource"/"event" — not the plural URL path segment
(app/services/spa_shell.py's _ENTITY_TYPE_BY_PREFIX maps each nested
/<prefix>/<slug> route's prefix to the matching entity_type here).
"""
from app.extensions import db

ENTITY_REDIRECT_TYPES = ("topic", "series", "person", "author", "opportunity", "job", "resource", "event")
_ENTITY_TYPE_CHECK_SQL = "entity_type IN (" + ", ".join(f"'{t}'" for t in ENTITY_REDIRECT_TYPES) + ")"


class EntityRedirect(db.Model):
    """One row per stale old slug for one of the 8 in-scope entity types —
    see this module's own docstring. Never carries protected/private data:
    only the two public slugs involved (see
    app/services/entity_redirects.py's own docstring for why only a
    publicly-visible-before-AND-after slug change ever creates one of
    these).
    """

    __tablename__ = "entity_redirects"
    __table_args__ = (
        db.CheckConstraint(_ENTITY_TYPE_CHECK_SQL, name="ck_entity_redirects_entity_type"),
        # The one real access pattern this table serves: "does THIS
        # entity type have a redirect FROM this exact slug" (see
        # app/services/spa_shell.py's _render_entity_detail fallback,
        # run only after the live entity lookup at that slug already
        # missed). Scoped by entity_type, deliberately NOT globally
        # unique on from_slug alone — /jobs/example and /events/example
        # must be free to coexist as independent redirect rows.
        db.UniqueConstraint("entity_type", "from_slug", name="uq_entity_redirects_type_from_slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(20), nullable=False)
    from_slug = db.Column(db.String(220), nullable=False)
    to_slug = db.Column(db.String(220), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
