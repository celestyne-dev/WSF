# Women Shaping Futures — Backend

Flask + PostgreSQL API for the Women Shaping Futures platform. Built
progressively behind the same mock-API-shaped contract the frontend already
consumes (`frontend/src/api/*.js`), so each phase can swap one namespace
from mock data to a real endpoint without touching the rest of the app.

Stack: Flask, Flask-RESTful, Flask-SQLAlchemy, SQLAlchemy, PostgreSQL,
Flask-Migrate/Alembic, Flask-JWT-Extended, bcrypt, Marshmallow, Flask-CORS,
Pillow. Media is written straight to the filesystem (Hostinger VPS in
production) and served by Nginx — never Cloudinary or any third-party CDN.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt   # requirements.txt + pytest

createuser wsf --pwprompt --createdb   # or use an existing role
createdb -O wsf wsf_dev
createdb -O wsf wsf_test               # used only by the test suite

cp .env.example .env                   # then fill in DATABASE_URL, JWT_SECRET_KEY, etc.

export FLASK_APP=run.py
flask db upgrade                       # apply migrations
flask seed-roles                       # roles + permissions (RBAC) — re-run after editing ROLE_PERMISSIONS
flask seed-geography                   # Country reference table
flask create-superadmin --email you@example.com --password "change-me-now"

python run.py                          # http://localhost:5000
```

## Everyday commands

```bash
flask db migrate -m "add whatever"     # after changing a model in app/models/
flask db upgrade                       # apply pending migrations
pytest                                 # runs against wsf_test, creates/drops tables per test
```

> **Known Alembic quirk**: `media.uploaded_by_id` and `users.avatar_media_id`
> form a circular FK, broken with `use_alter=True` on the `media` side
> (see `app/models/media.py`). Alembic's autogenerate periodically
> misdetects that constraint as newly added — a migration whose *only*
> change is `create_foreign_key('fk_media_uploaded_by_id', ...)` (or the
> matching `drop_constraint` with no create) is that phantom diff, not a
> real change. Delete the migration rather than applying it; `flask db
> upgrade` would otherwise fail with "constraint already exists".

## Layout

```
app/
  __init__.py       Application factory — registers extensions, blueprints, error/JWT handlers
  extensions.py     db, migrate, jwt, cors, ma singletons
  api/v1/           One module per versioned namespace (Blueprint + Flask-RESTful Api)
  auth/             Password hashing, JWT callbacks, permission_required/roles_required decorators
  models/           SQLAlchemy models, one module per domain area
  schemas/          Marshmallow schemas (request validation + response serialization)
  services/         Business logic: RBAC seeding, slugs, geography, media pipeline, audit log
  utils/            Dependency-free helpers: response envelope, pagination, filtering, slugs
tests/              pytest suite (Flask test client, real Postgres via wsf_test)
migrations/         Alembic migration history (flask db migrate/upgrade)
```

## Conventions carried through every phase

- **Response envelope** (`app/utils/responses.py`): every endpoint returns
  `{"success": true, "data": ..., "meta": {...}?}` or
  `{"success": false, "error": {"message", "code", "details"?}}`. Views
  return plain `(dict, status)` tuples — never `jsonify()` — because
  Flask-RESTful's `Api` re-runs the *entire app's* exception handling
  through its own JSON representer, and re-serializing an already-built
  `Response` object there raises `TypeError: Object of type Response is
  not JSON serializable`. Plain dicts survive both paths.
- **RBAC**: permissions are strings like `"articles.publish"`, attached to
  roles (`app/services/rbac.py`), attached to users. Protect a view with
  `@permission_required("articles.publish")` or `@roles_required("editor")`
  from `app/auth/decorators.py`.
- **Global geography, not a hard-coded list**: every location-bearing model
  stores an ISO 3166-1 alpha-2 `country_code` (or the `GLOBAL`/`REMOTE`
  pseudo-codes) as a foreign key into `countries` (`app/models/geography.py`).
  Adding a country is a data change — `flask seed-geography` — never a code
  change. `app/utils/filtering.py` gives every listing endpoint the same
  `?country=US` / `?region=Africa` query handling for free.
  This mirrors `frontend/src/mock/geography.js` exactly; Phase 8 points that
  file at `GET /api/v1/public/countries` instead of its local array.
- **Slugs**: flat public article URLs (`/{slug}`) must never collide with a
  reserved route. `app/utils/slugs.py` holds `RESERVED_SLUGS` (kept in sync
  with `frontend/src/mock/index.js`); `app/services/slugs.py` generates a
  unique slug against a model, skipping reserved words and appending `-2`,
  `-3`, ... on collision.
- **Media**: `app/services/media.py` validates MIME type/extension/size,
  writes the original under a UUID filename, and uses Pillow to generate
  thumbnail/card/medium/large/hero WebP variants — all under `MEDIA_ROOT`
  (an absolute path outside the source tree). Every model that carries an
  image stores a `Media` foreign key, never a bare path string, so
  `Media.delete()` can refuse to remove a file still referenced elsewhere.
- **Audit log**: `app/services/audit.py` appends an `AuditLog` row for
  auth/admin actions — append-only, never edited via the API.
- **Article slug changes**: `PUT /api/v1/articles/{slug}` with a new
  `slug` calls `create_redirect_for_slug_change` (`app/services/slugs.py`),
  which repoints any redirect chain to a single hop and writes a
  `Redirect` row. `GET /api/v1/articles/{old-slug}` then returns a real
  HTTP 301 with `Location: /api/v1/articles/{new-slug}` plus a
  `{"redirect": "..."}` JSON body, since there's no server-rendered HTML
  for a browser to follow — the SPA's `ArticlePage` (Phase 8) should check
  for a 301 and `navigate(..., {replace: true})` to the flat URL. An
  explicit `slug` in a create/update payload is validated strictly
  (`validate_explicit_slug` — 409 if taken, 400 if reserved); a slug
  derived automatically from the title instead auto-suffixes on collision
  (`generate_unique_slug`).
- **Revisions**: every article create/update/publish appends a full JSON
  snapshot to `article_revisions` (`ArticleRevision`) — no separate diffing
  engine, just "what did this look like at each save."
- **Media reference guard**: `Media.is_referenced()` (`app/models/media.py`)
  checks every FK that currently points at `media.id` before a delete is
  allowed. Any new content type that adds a Media FK (Event cover, Job
  logo, Product image, ...) must add its own check there — the checklist
  is in that method's docstring, not enforced by the type system.
- **CMS builder endpoints save the whole arrangement, not diffs**:
  `PUT /api/v1/admin/homepage` and `PUT /api/v1/admin/navigation` each
  replace their entire table(s) from the payload
  (`app/services/cms.py`) rather than tracking per-item add/remove/reorder
  — simpler and matches how a drag-and-drop builder naturally works
  (edit the whole list client-side, save it all at once). `SiteSetting` is
  a flexible key/value table instead — `PUT /api/v1/admin/settings` merges
  keys rather than replacing the table, since settings are looked up
  individually, not rendered as an ordered list.
- **Jobs/Opportunities/Events/Resources**: all four reuse the Phase 1
  geography filtering (`?country=`/`?region=`) and the Phase 2 slug
  services. `Opportunity.countries_eligible` is a many-to-many onto
  `Country` (not a JSON array of codes) so `?region=` can filter with a
  real join rather than scanning application-side. Amounts are always
  `{integer, ISO currency code}` pairs (`salary_min`/`salary_max`/
  `currency` on Job, `ticket_price`/`currency` on Event, `price`/
  `currency` on Resource) — never a bare number, and never defaulted to
  any one currency.
- **Response casing**: dump schemas currently serialize in the model's
  native snake_case (e.g. `publish_date`, `hero_media`); the input schemas
  already accept the frontend's camelCase (`publishDate`, `heroMediaId`)
  via Marshmallow `data_key`. Phase 8 (wiring the frontend to real
  endpoints) should decide once whether to camelCase every dump schema or
  translate in the frontend's `api/*.js` layer — don't do it ad hoc per
  endpoint before then.
