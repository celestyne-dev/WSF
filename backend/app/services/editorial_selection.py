"""Page-level Article selection: FIRST PLACEMENT WINS.

An Article may appear only once on a rendered page. Every Article-producing
section of a page (homepage modules in builder order, the recommendation
blocks on an Article page, the modules of a Topic hub) asks ONE
EditorialSelection for its Articles, in page order. Whatever an earlier
section took is excluded from every later one, at query time: later sections
never fetch and then hide duplicates, and dynamic sections backfill from the
next eligible candidates (one bounded query each).

The server resolves a page once; the result is what the server first paint
renders, what the page bootstrap / public API carries and what React renders.
The browser never re-selects.

This module holds selection rules only, never presentation.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import selectinload

from app.models.article import Article

# Upper bound on candidates any one ranked selection may examine.
RANKED_POOL = 60
# Filtered selection (an eligibility rule that needs Python, e.g. "has a
# public expert") reads candidates in batches of this size, and never more
# than MAX_FILTER_SCAN of them per section.
FILTER_BATCH = 20
MAX_FILTER_SCAN = 200


def public_articles():
    """Publicly readable Articles (the public list endpoint's own rule:
    status "published"; scheduled ones go live via publish-due-content),
    with what a card needs loaded in batches (no N+1)."""
    return Article.query.options(
        selectinload(Article.author), selectinload(Article.topics), selectinload(Article.tags),
        selectinload(Article.series), selectinload(Article.category), selectinload(Article.hero_media),
    ).filter(Article.status == "published")


def newest_first(query):
    return query.order_by(Article.publish_date.desc().nullslast(), Article.id.desc())


class EditorialSelection:
    """One per rendered page. `placements` records (section label, ids) in
    page order, for tests and Studio diagnostics."""

    def __init__(self, reserved_ids=()):
        self.used = set()
        self.placements = []
        if reserved_ids:
            self.reserve_ids(reserved_ids, "reserved")

    # --- reservations -----------------------------------------------------------------
    def reserve_ids(self, ids, label):
        new = [i for i in ids if i is not None and i not in self.used]
        self.used.update(new)
        if new:
            self.placements.append((label, list(new)))
        return new

    def reserve(self, articles, label):
        self.reserve_ids([a.id for a in articles], label)
        return articles

    def is_used(self, article_id):
        return article_id in self.used

    # --- selection ---------------------------------------------------------------------
    def pick_manual(self, slugs, limit, label, eligible=None, query=None):
        """Editor-picked slugs in the editor's order: unpublished, missing,
        already-placed or (with `eligible`) ineligible Articles are skipped,
        never replaced by a repeat. Eligibility is decided before anything
        is reserved."""
        slugs = [s for s in (slugs or []) if isinstance(s, str) and s]
        if not slugs or limit <= 0:
            return []
        rows = (query if query is not None else public_articles()).filter(Article.slug.in_(slugs)).all()
        by_slug = {row.slug: row for row in rows}
        picked = []
        for slug in slugs:
            row = by_slug.get(slug)
            if row is None or row.id in self.used or row in picked:
                continue
            if eligible is not None and not eligible(row):
                continue
            picked.append(row)
            if len(picked) >= limit:
                break
        return self.reserve(picked, label)

    def pick_query(self, query, limit, label):
        """The first `limit` rows of an ordered query that are not placed
        yet. The exclusion is part of the SQL, so a section that needs 8
        gets 8 whenever 8 eligible Articles exist."""
        if limit <= 0:
            return []
        if self.used:
            query = query.filter(Article.id.notin_(self.used))
        return self.reserve(query.limit(limit).all(), label)

    def pick_query_where(self, query, eligible, limit, label, batch=FILTER_BATCH, max_scan=MAX_FILTER_SCAN):
        """Like pick_query, for a rule SQL cannot express by itself: read the
        ordered, not-yet-placed candidates in bounded batches, keep those
        `eligible` accepts (checked BEFORE reserving), until `limit` are
        found or `max_scan` candidates were examined."""
        if limit <= 0:
            return []
        if self.used:
            query = query.filter(Article.id.notin_(self.used))
        picked, offset = [], 0
        while len(picked) < limit and offset < max_scan:
            rows = query.offset(offset).limit(batch).all()
            if not rows:
                break
            offset += len(rows)
            for row in rows:
                if eligible(row):
                    picked.append(row)
                    if len(picked) >= limit:
                        break
        return self.reserve(picked, label)

    def pick_ranked(self, query, score, limit, label, pool=RANKED_POOL):
        """Deterministic relevance: examine at most `pool` unplaced
        candidates, order by (score desc, newest first, id), take `limit`.
        No randomness, so every render of the same data agrees."""
        if limit <= 0:
            return []
        if self.used:
            query = query.filter(Article.id.notin_(self.used))
        candidates = newest_first(query).limit(pool).all()
        scored = [(score(a), a) for a in candidates]
        scored = [(s, a) for s, a in scored if s > 0]
        scored.sort(key=lambda pair: (-pair[0], -_timestamp(pair[1].publish_date), -pair[1].id))
        return self.reserve([a for _, a in scored[:limit]], label)

    def pick_manual_then_query(self, slugs, query, limit, label):
        """Editor picks first; when the section's own rule allows a
        backfill, the remaining slots come from `query` (still excluding
        everything placed)."""
        picked = self.pick_manual(slugs, limit, label)
        if len(picked) < limit and query is not None:
            picked = picked + self.pick_query(query, limit - len(picked), label)
        return picked


def _timestamp(value):
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def now_utc():
    return datetime.now(timezone.utc)


def article_cards(articles):
    """The public card payload (the public list's summary shape)."""
    from app.schemas.article import PublicArticleSchema, article_summary_schema

    schema = PublicArticleSchema(many=True, exclude=tuple(article_summary_schema().exclude) + ("author.article_count",))
    return schema.dump(articles)
