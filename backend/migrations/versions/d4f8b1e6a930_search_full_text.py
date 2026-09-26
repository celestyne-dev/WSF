"""search: article full-text vector + targeted status indexes

Site-wide search (see app/services/search.py) needs two things the schema
didn't have yet:

1. Real full-text search over Article body content. Article.content is a
   JSON block list (paragraphs/headings/quotes/lists/images), not plain
   text, so a naive `ILIKE` can't reach it without deserializing every row
   on every request. This migration adds an IMMUTABLE SQL function,
   `wsf_block_list_text(jsonb)`, that extracts the plain-text fragments
   out of that block list (stripping any inline HTML the block editor
   allows), and a second function, `wsf_article_search_vector(...)`, that
   combines title (weight A) + subtitle/excerpt (weight B) + that
   extracted body text (weight C) into one weighted `tsvector`. A
   functional GIN index on that expression means Postgres keeps it
   current automatically on every INSERT/UPDATE — no trigger, no stored/
   duplicated body column, no manual reindex step (see services/search.py
   and spec section 69).

2. `status` on the content types search filters by (Article/Person/Job/
   Opportunity/Event/Resource) gets a plain btree index — every search
   request filters on it, and it wasn't indexed before now.

Purely additive: no existing column is altered, no data is rewritten, and
CREATE FUNCTION/INDEX runs fine on a standard Hostinger-style PostgreSQL
instance with no extensions required (to_tsvector/websearch_to_tsquery are
core PostgreSQL, not `pg_trgm` or another extension).

Revision ID: d4f8b1e6a930
Revises: c8e1a4d7f209
Create Date: 2026-09-26 12:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd4f8b1e6a930'
down_revision = 'c8e1a4d7f209'
branch_labels = None
depends_on = None


_BLOCK_TEXT_FN = """
CREATE OR REPLACE FUNCTION wsf_block_list_text(blocks jsonb)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
  SELECT COALESCE(string_agg(regexp_replace(fragment, '<[^>]*>', ' ', 'g'), ' '), '')
  FROM (
    SELECT (kv).value #>> '{}' AS fragment
    FROM jsonb_array_elements(COALESCE(blocks, '[]'::jsonb)) AS block,
         LATERAL jsonb_each(block) AS kv
    WHERE jsonb_typeof((kv).value) = 'string' AND (kv).key <> 'type'
    UNION ALL
    SELECT item #>> '{}' AS fragment
    FROM jsonb_array_elements(COALESCE(blocks, '[]'::jsonb)) AS block,
         LATERAL jsonb_each(block) AS kv,
         LATERAL jsonb_array_elements((kv).value) AS item
    WHERE jsonb_typeof((kv).value) = 'array' AND jsonb_typeof(item) = 'string'
  ) AS fragments;
$$;
"""

_ARTICLE_VECTOR_FN = """
CREATE OR REPLACE FUNCTION wsf_article_search_vector(title text, subtitle text, excerpt text, content json)
RETURNS tsvector
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
  SELECT
    setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(subtitle, '') || ' ' || COALESCE(excerpt, '')), 'B') ||
    setweight(to_tsvector('english', wsf_block_list_text(content::jsonb)), 'C');
$$;
"""


def upgrade():
    op.execute(_BLOCK_TEXT_FN)
    op.execute(_ARTICLE_VECTOR_FN)
    op.execute(
        "CREATE INDEX ix_articles_search_vector ON articles "
        "USING GIN (wsf_article_search_vector(title, subtitle, excerpt, content))"
    )

    op.execute("CREATE INDEX ix_articles_status ON articles (status)")
    op.execute("CREATE INDEX ix_people_status ON people (status)")
    op.execute("CREATE INDEX ix_jobs_status ON jobs (status)")
    op.execute("CREATE INDEX ix_opportunities_status ON opportunities (status)")
    op.execute("CREATE INDEX ix_events_status ON events (status)")
    op.execute("CREATE INDEX ix_resources_status ON resources (status)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_resources_status")
    op.execute("DROP INDEX IF EXISTS ix_events_status")
    op.execute("DROP INDEX IF EXISTS ix_opportunities_status")
    op.execute("DROP INDEX IF EXISTS ix_jobs_status")
    op.execute("DROP INDEX IF EXISTS ix_people_status")
    op.execute("DROP INDEX IF EXISTS ix_articles_status")

    op.execute("DROP INDEX IF EXISTS ix_articles_search_vector")
    op.execute("DROP FUNCTION IF EXISTS wsf_article_search_vector(text, text, text, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS wsf_block_list_text(jsonb)")
