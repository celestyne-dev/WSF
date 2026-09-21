from app.extensions import db
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
