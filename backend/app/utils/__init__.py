# Shared, dependency-free helpers. Business logic that hits the database
# (e.g. checking slug uniqueness against a model) lives in app/services/
# instead — see app/services/slugs.py.
from app.utils.slugs import RESERVED_SLUGS, is_reserved_slug, slugify  # noqa: F401
