from app.extensions import db
from app.utils.responses import ApiError
from app.utils.slugs import is_reserved_slug, slugify


def generate_unique_slug(model, base_value, current_id=None, field="slug"):
    """Slugify `base_value` and make it unique for `model.field`, skipping
    reserved routes (see app/utils/slugs.py) and appending -2, -3, ...  on
    collision. Used by every content type with a public flat/nested URL
    (Article, Person, Author, Series, Resource, Event, Opportunity, Job).
    """
    base = slugify(base_value) or "item"
    candidate = base
    suffix = 2
    column = getattr(model, field)

    while True:
        if is_reserved_slug(candidate):
            candidate = f"{base}-{suffix}"
            suffix += 1
            continue

        query = model.query.filter(column == candidate)
        if current_id is not None:
            query = query.filter(model.id != current_id)
        if not db.session.query(query.exists()).scalar():
            return candidate

        candidate = f"{base}-{suffix}"
        suffix += 1


def validate_explicit_slug(model, raw_slug, current_id=None, field="slug"):
    """A human explicitly asked for this exact slug — unlike
    generate_unique_slug, don't silently pick a different one on collision;
    tell them it's taken.
    """
    candidate = slugify(raw_slug)
    if not candidate:
        raise ApiError("Slug cannot be empty.", 400, code="invalid_slug")
    if is_reserved_slug(candidate):
        raise ApiError(
            f'"{candidate}" is a reserved system route and cannot be used as a slug.', 400, code="reserved_slug"
        )

    column = getattr(model, field)
    query = model.query.filter(column == candidate)
    if current_id is not None:
        query = query.filter(model.id != current_id)
    if db.session.query(query.exists()).scalar():
        raise ApiError("This slug is already in use.", 409, code="slug_taken")

    return candidate


def create_redirect_for_slug_change(article, old_slug, new_slug):
    """Point the article's old flat URL at its new one. Any redirect that
    already targeted `old_slug` is repointed straight at `new_slug` so a
    lookup is never more than one hop, and a stale redirect *from*
    `new_slug` (if that slug used to belong to something else) is dropped
    now that it's live again.
    """
    from app.models.article import Redirect

    if old_slug == new_slug:
        return

    Redirect.query.filter_by(to_slug=old_slug).update({"to_slug": new_slug})
    Redirect.query.filter_by(from_slug=new_slug).delete()

    existing = Redirect.query.filter_by(from_slug=old_slug).first()
    if existing:
        existing.to_slug = new_slug
        existing.article_id = article.id
    else:
        db.session.add(Redirect(from_slug=old_slug, to_slug=new_slug, article_id=article.id))
