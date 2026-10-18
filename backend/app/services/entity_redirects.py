from app.extensions import db


def create_entity_redirect_for_slug_change(entity_type, old_slug, new_slug):
    """Generalizes app/services/slugs.py's create_redirect_for_slug_change
    for the 8 non-Article entity types that live at a nested /<prefix>/
    <slug> route instead of Article's flat /<slug> — see
    app/models/entity_redirect.py's own docstring for why that's a
    separate table scoped by entity_type, not a reuse of Article's
    globally-unique-from_slug Redirect table. Same exact algorithm,
    parameterized:

      - a no-op when old_slug == new_slug (nothing to redirect)
      - any existing redirect of this SAME entity_type that already
        pointed AT old_slug is repointed straight at new_slug, so a
        lookup is never more than one hop (A -> B, then B -> C, collapses
        to A -> C and B -> C, never A -> B -> C)
      - a stale redirect FROM new_slug (of this same entity_type), if
        new_slug used to belong to something else, is dropped now that
        it's live again — the live entity always wins over redirect
        history
      - the old_slug -> new_slug row itself is created, or updated in
        place if one already existed

    Deliberately takes no entity object/FK (see this phase's "no
    polymorphic foreign keys, no entity_id unless clearly needed"
    constraint) — just three strings. The caller decides WHETHER a
    redirect is warranted (see each api/v1/<type>.py update endpoint:
    only when the slug actually changed and the entity was publicly
    visible both before and after the save, using that entity's own
    existing authoritative visibility rule) and is responsible for its
    own db.session.commit() — this function only flushes pending ORM
    changes into the caller's existing transaction, never commits
    independently, so a slug update and its redirect always land or
    roll back together.
    """
    from app.models.entity_redirect import EntityRedirect

    if old_slug == new_slug:
        return

    EntityRedirect.query.filter_by(entity_type=entity_type, to_slug=old_slug).update({"to_slug": new_slug})
    EntityRedirect.query.filter_by(entity_type=entity_type, from_slug=new_slug).delete()

    existing = EntityRedirect.query.filter_by(entity_type=entity_type, from_slug=old_slug).first()
    if existing:
        existing.to_slug = new_slug
    else:
        db.session.add(EntityRedirect(entity_type=entity_type, from_slug=old_slug, to_slug=new_slug))
