from flask.testing import FlaskClient
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
ALTER FUNCTION wsf_block_list_text(jsonb) SET search_path = public, pg_catalog;
ALTER FUNCTION wsf_article_search_vector(text, text, text, json) SET search_path = public, pg_catalog;
"""


def _teardown_db():
    # Each test gets its own create_app("testing") call, which gives
    # Flask-SQLAlchemy a brand-new Engine (flask_sqlalchemy.extension keys
    # engines by Flask app instance). Removing the scoped session only
    # returns its connection to that engine's own pool — it does not close
    # the pool's connections or guarantee the Engine itself is disposed in
    # any bounded time, since that depends on the app object being garbage
    # collected. Across hundreds of function-scoped fixtures that lag is
    # enough to exhaust Postgres max_connections before GC catches up, so
    # dispose() is called explicitly here to close the pool deterministically.
    _db.session.remove()
    try:
        _db.drop_all()
    finally:
        _db.engine.dispose()


RAW_REGISTER_HEADER = "X-Test-Raw-Register"


class _AgeConfirmingClient(FlaskClient):
    """Step 18 made the "at least N years old" confirmation mandatory at
    signup. Existing tests register users only as setup, so this client adds
    ``age_confirmed: true`` to /auth/register bodies that don't mention it.
    Tests of the age gate itself either set ``age_confirmed`` explicitly or
    send RAW_REGISTER_HEADER to have the body passed through untouched."""

    def open(self, *args, **kwargs):
        path = args[0] if args and isinstance(args[0], str) else kwargs.get("path", "")
        headers = kwargs.get("headers") or {}
        raw = RAW_REGISTER_HEADER in headers
        body = kwargs.get("json")
        is_register = str(path).split("?")[0].rstrip("/") == "/api/v1/auth/register"
        if is_register and not raw and isinstance(body, dict) and "age_confirmed" not in body:
            kwargs["json"] = {**body, "age_confirmed": True}
        response = super().open(*args, **kwargs)
        # Batch 4 corrections: new accounts must verify their email before
        # normal use. Setup-only registrations are marked verified here (as
        # if the link had been clicked); verification tests send
        # RAW_REGISTER_HEADER to keep the account unverified.
        if is_register and not raw and response.status_code == 201 and isinstance(body, dict) and body.get("email"):
            from sqlalchemy import text as _text

            from app.extensions import db as _sa_db

            with self.application.app_context():
                with _sa_db.engine.begin() as conn:
                    conn.execute(_text("UPDATE users SET email_verified_at = now() WHERE lower(email) = :e"),
                                 {"e": body["email"].strip().lower()})
        return response


@pytest.fixture()
def app():
    application = create_app("testing")
    application.test_client_class = _AgeConfirmingClient
    with application.app_context():
        try:
            _db.create_all()
            _db.session.execute(text(_SEARCH_FUNCTIONS_SQL))
            _db.session.commit()
            seed_roles_and_permissions()
            seed_countries()
        except Exception:
            # Setup itself failed (e.g. mid-seed) — clean up whatever
            # create_all()/execute() already created before propagating,
            # rather than leaking the engine's connections on a fixture
            # that never reaches yield.
            _teardown_db()
            raise

        try:
            yield application
        finally:
            # Always runs, including when the test body raises, so a
            # failing test never skips connection cleanup.
            _teardown_db()


@pytest.fixture()
def client(app):
    return app.test_client()


def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


REFRESH_COOKIE = "wsf_refresh"
REFRESH_PATH = "/api/v1/auth/refresh"
# What the real frontend sends with every refresh-cookie request (CSRF).
CSRF_HEADERS = {"X-WSF-CSRF": "1", "Origin": "http://localhost"}


def refresh_cookie_value(client):
    cookie = client.get_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return cookie.value if cookie else None


def refresh_session(client, cookie_value=None, headers=None):
    """POST /auth/refresh like the browser does; `cookie_value` replays a
    specific session's cookie (the test client keeps only the latest)."""
    if cookie_value is not None:
        client.set_cookie(REFRESH_COOKIE, cookie_value, path=REFRESH_PATH)
    return client.post(REFRESH_PATH, headers=headers if headers is not None else CSRF_HEADERS)


def newsletter_signup(client, payload, confirm=True):
    """POST /newsletter/subscribe with the consent tick (double opt-in, Step
    14) and, unless confirm=False, click the emailed confirmation link.
    Returns the subscribe response."""
    import re
    from unittest.mock import patch

    sent = []
    with patch("app.services.email.send_email", side_effect=lambda to, subject, text, *a, **k: sent.append(text) or True):
        resp = client.post("/api/v1/newsletter/subscribe", json={"consent": True, **payload})
    if confirm and sent:
        token = re.search(r"/newsletter/confirm/(\S+)", sent[-1]).group(1)
        client.post("/api/v1/newsletter/confirm", json={"token": token})
    return resp
