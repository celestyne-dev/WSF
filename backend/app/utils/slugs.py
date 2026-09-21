import re

# Reserved top-level routes on the frontend that a content slug must never
# collide with. Kept in sync with frontend/src/mock/index.js RESERVED_SLUGS
# by hand until slugs move to a DB-backed setting.
RESERVED_SLUGS = frozenset(
    {
        "admin", "api", "login", "logout", "register", "search", "people", "authors",
        "topics", "categories", "series", "resources", "events", "opportunities",
        "jobs", "organizations", "newsletter", "mentorship", "community", "learning",
        "shop", "partnerships", "advertise", "about", "contact", "privacy", "terms",
        "cookies", "submit", "nominate", "account", "dashboard", "articles", "editorial-policy",
    }
)

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(value):
    value = (value or "").strip().lower()
    value = _NON_SLUG_CHARS.sub("-", value)
    return value.strip("-")


def is_reserved_slug(slug):
    return slug in RESERVED_SLUGS
