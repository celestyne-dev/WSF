"""The ONE ownership rule for the flat public namespace: /<slug>.

Articles and general Pages both publish at /<slug>, and an Article
Redirect answers there too (spa_shell.resolve_spa_response checks, in
order: published Article, Article Redirect, general Page). So a flat slug
has at most one owner:

  reserved  a system route (app/utils/slugs.py RESERVED_SLUGS: /lifetime,
            /learning, /about, ...). Never usable.
  article   any Article, whatever its status (a draft may publish later).
  page      any Page (general or system), whatever its status.
  redirect  an Article Redirect (an old Article URL that now 301s).

Policy
  * Generated slugs (from a title) step to -2, -3, ... past every owner,
    so they never collide and never hijack an old Article URL.
  * Explicit slugs are refused with a clear 409 `slug_taken` (or 400
    `reserved_slug`) when another owner holds them, with one deliberate
    exception: an Article may reclaim an Article Redirect slug. That uses
    the existing redirect lifecycle: the Redirect row is removed
    (`reclaim_redirect_slug`, or create_redirect_for_slug_change on a
    rename), so the slug is never owned twice.
  * A Page can never claim a Redirect slug: the Redirect would win and the
    Page could never be reached.

Only the flat namespace. Nested entities (/people/<slug>, /authors/<slug>,
/learning/<slug>, ...) keep their own per-model uniqueness.
"""
from app.extensions import db
from app.utils.responses import ApiError
from app.utils.slugs import is_reserved_slug, slugify

_OWNER_WORDS = {
    "article": "an article",
    "page": "a page",
    "redirect": "an old article URL that now redirects",
}


def flat_public_slug_owner(slug, *, article_id=None, page_id=None):
    """"reserved" | "article" | "page" | "redirect" | None. The record being
    edited (article_id / page_id) never counts as its own owner."""
    from app.models.article import Article, Redirect
    from app.models.page import Page

    if not slug or is_reserved_slug(slug):
        return "reserved"
    query = Article.query.filter(Article.slug == slug)
    if article_id is not None:
        query = query.filter(Article.id != article_id)
    if db.session.query(query.exists()).scalar():
        return "article"
    query = Page.query.filter(Page.slug == slug)
    if page_id is not None:
        query = query.filter(Page.id != page_id)
    if db.session.query(query.exists()).scalar():
        return "page"
    if db.session.query(Redirect.query.filter(Redirect.from_slug == slug).exists()).scalar():
        return "redirect"
    return None


def generate_flat_slug(base_value, *, article_id=None, page_id=None):
    """A free flat slug from a title: -2, -3, ... past any owner."""
    base = slugify(base_value) or "item"
    candidate, suffix = base, 2
    while flat_public_slug_owner(candidate, article_id=article_id, page_id=page_id) is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def validate_flat_slug(raw_slug, *, kind, article_id=None, page_id=None):
    """An explicit slug for an Article (kind="article") or Page
    (kind="page"). Returns the normalized slug or raises ApiError."""
    candidate = slugify(raw_slug)
    if not candidate:
        raise ApiError("Slug cannot be empty.", 400, code="invalid_slug")
    owner = flat_public_slug_owner(candidate, article_id=article_id, page_id=page_id)
    if owner == "reserved":
        raise ApiError(f'"{candidate}" is a reserved system route and cannot be used as a slug.', 400, code="reserved_slug")
    if owner == "redirect" and kind == "article":
        return candidate  # deliberate reclaim; the caller retires the Redirect
    if owner is not None:
        raise ApiError(f'"/{candidate}" is already used by {_OWNER_WORDS[owner]}. Choose a different slug.', 409, code="slug_taken")
    return candidate


def reclaim_redirect_slug(slug):
    """An Article now lives at `slug`: retire any Redirect from it so the
    slug has exactly one owner."""
    from app.models.article import Redirect

    Redirect.query.filter_by(from_slug=slug).delete()
