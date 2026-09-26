import pytest
from sqlalchemy import text

from app import create_app
from app.extensions import db as _db
from app.services.geography import seed_countries
from app.services.rbac import seed_roles_and_permissions

# `db.create_all()` only creates tables from the SQLAlchemy models — it
# skips the two custom Postgres functions that
# migrations/versions/d4f8b1e6a930_search_full_text.py adds directly via
# raw SQL (search's Article full-text vector). Recreated here so search
# tests exercise the same function real deployments get after
# `flask db upgrade`. Keep this in sync with that migration's function
# bodies; the GIN index itself is a pure performance optimization and
# doesn't need to exist for tests to be correct.
_SEARCH_FUNCTIONS_SQL = """
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


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        _db.session.execute(text(_SEARCH_FUNCTIONS_SQL))
        _db.session.commit()
        seed_roles_and_permissions()
        seed_countries()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}
