# Deployment Guide — Women Shaping Futures

Target architecture: a single Hostinger VPS running

```
Nginx
  ├── serves the React/Vite production build (static files)
  ├── proxies /api/  ->  Gunicorn  ->  Flask  ->  PostgreSQL
  └── serves /media/ directly from disk
```

No Docker, no Kubernetes, no Redis, no Celery, no CDN, no managed email
service. Scheduled publishing runs via a plain cron entry or systemd timer
calling an existing Flask CLI command — not a message broker.

This document describes how to deploy safely. **It does not deploy
anything itself** — every command below is something an operator runs
manually on the real VPS, in their own shell, after reviewing it.

---

## 1. Architecture recap

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React + Vite, built to static files | Served by Nginx from `frontend/dist` |
| API | Flask, served by Gunicorn (WSGI) | Bound to `127.0.0.1:8000`, never exposed directly |
| Database | PostgreSQL | One instance; separate `_dev`/`_test`/production databases |
| Media | Local VPS filesystem | Uploaded via Flask, served by Nginx |
| Scheduler | cron or systemd timer | Calls `flask publish-due-content`; no Celery/Redis |

## 2. Prerequisites (installed once, manually, on the VPS)

- Python 3.12.x (matches local development — do not deploy on a different
  major version without testing)
- PostgreSQL server, reachable from the app (same host or private network)
- Node.js + npm (build-time only, for `npm run build`; the built static
  files are all that ships to the served directory — Node is never running
  as part of the live site)
- Nginx
- A dedicated, non-root system user to run the Gunicorn service (e.g.
  `womenshapingfutures`)

## 3. Filesystem layout (adjust to whatever actually exists on the VPS)

```
/var/www/womenshapingfutures/
├── backend/           # this repo's backend/, with a .venv/ inside it
├── frontend/
│   └── dist/          # `npm run build` output — this is what Nginx serves
└── media/             # MEDIA_ROOT — uploaded files, outside both source trees
```

Do not assume these directories exist yet — creating them (and setting
their ownership/permissions) is a manual VPS operation, not something this
repository does for you.

## 4. Environment configuration

Copy `backend/.env.example` to `backend/.env` on the server and fill in
**real** values — never commit this file, and never reuse a development
secret in it. See that file for the full, documented variable list. The
ones that matter most for going to production safely:

| Variable | Production requirement |
|---|---|
| `FLASK_CONFIG` | `production` |
| `SECRET_KEY` | Required. No default exists for `ProductionConfig` — the app refuses to start without a real value (see `config.py:require_production_settings`). Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `JWT_SECRET_KEY` | Required, same rule as `SECRET_KEY`. Use a **different** random value, not the same one. |
| `DATABASE_URL` | Required. Must point at the real production database — the app refuses to start if it still contains `wsf_dev`/`wsf_test`. |
| `CORS_ORIGINS` | Required. Comma-separated exact origin(s), e.g. `https://womenshapingfutures.org`. The app refuses to start if this includes `localhost`/`127.0.0.1`. |
| `MEDIA_ROOT` | Absolute path outside both source trees, e.g. `/var/www/womenshapingfutures/media`. |
| `TRUSTED_PROXY_COUNT` | `1` (exactly one Nginx hop in front of Gunicorn). |
| `LOG_LEVEL` | `INFO` (or `WARNING` once things are stable). |

Run `flask production-check` (see §13) after filling this in — it verifies
all of the above without touching the database and without ever printing
a secret value.

Frontend: copy `frontend/.env.example` to `frontend/.env.production` (or
set the same variables however your build pipeline reads them) with:

```
VITE_API_URL=https://womenshapingfutures.org/api/v1
VITE_USE_MOCK=false
VITE_MEDIA_BASE_URL=https://womenshapingfutures.org/media
```

`VITE_USE_MOCK=false` is the production expectation. Every `src/api/*.js`
module already routes to the real backend when this is false, and never
substitutes mock data on a failed request — a failed request produces a
real error/empty state in the UI, not fabricated content (verified as
part of this task's audit).

## 5. Backend setup

```bash
cd /var/www/womenshapingfutures/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6. Database migrations

**Always** apply already-reviewed, already-committed migrations:

```bash
flask db upgrade
```

**Never** run `flask db init` or `flask db migrate` against production —
those generate new migration files from the current model state, which is
a development-time authoring step, not a deployment step. A production
deploy only ever consumes migrations that were already written, reviewed,
and committed to this repository.

Before running `flask db upgrade` on a real deploy: **back up the database
first** (§10) and sanity-check the migration graph:

```bash
flask db heads     # must show exactly one head
flask db current   # confirms what's actually applied right now
```

## 7. Bootstrap data (idempotent — safe to re-run)

```bash
flask seed-roles       # roles/permissions — safe, idempotent
flask seed-geography   # country reference table — safe, idempotent
flask seed-navigation  # header "primary"/"secondary" menus — safe, idempotent
```

`seed-navigation` bootstraps the public header's core sections (Stories,
Topics, People, Opportunities, Resources, Events, Community, Shop, and the
utility bar) the first time it runs, and — unlike a plain create-only
seed guard — heals a menu that already exists but is missing one of
those sections (e.g. after a later release added a new top-level page)
without ever renaming, reordering, or removing anything already saved
through AdminNavigation. Safe to re-run after every deploy.

**Never run `flask seed-demo` in production.** It loads fictional
articles/jobs/opportunities/events for local development and manual
verification only.

## 8. First Super Admin

There is no default admin account and no hard-coded password anywhere in
this codebase. Create the first Super Admin explicitly, once, with a
strong password you generate yourself:

```bash
flask create-superadmin --email you@womenshapingfutures.org --password '<a-real-strong-password>'
```

Never reuse a password that has appeared anywhere else (including any
development/demo password used while building this app) — treat this as a
brand-new credential.

## 9. Frontend build

```bash
cd /var/www/womenshapingfutures/frontend
npm ci          # reproducible install from package-lock.json — not `npm install`
npm run build   # outputs to dist/
```

Nginx serves `dist/` directly (see `deploy/nginx/womenshapingfutures.conf.example`).
Never run `npm run dev` in production, and never point Nginx at anything
other than the built `dist/` directory.

## 10. Backups (do this before every deploy that includes a migration)

**Database:**

```bash
pg_dump -U <db_user> -h <db_host> <db_name> | gzip > backup-$(date +%Y%m%d-%H%M%S).sql.gz
```

Never put the real password inline in a script committed to this repo —
use a `.pgpass` file or an environment variable read at run time.

**Media:** the database backup alone is not sufficient — uploaded files
live on disk under `MEDIA_ROOT`, not in Postgres. Back it up separately,
e.g.:

```bash
tar czf media-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /var/www/womenshapingfutures media
```

**Retention** (a policy to configure, not something this repo automates):
keep daily backups for at least a week, weekly for a month, and keep at
least one copy off the VPS itself (a second host, object storage, etc.) —
a backup that lives only on the machine it protects doesn't protect
against that machine failing. Test restoring from a backup periodically;
an untested backup is not a verified one.

## 11. Gunicorn

`backend/gunicorn.conf.py` is checked into this repository and is the
canonical way to run the app in production:

```bash
cd /var/www/womenshapingfutures/backend
source .venv/bin/activate
gunicorn -c gunicorn.conf.py "run:app"
```

`run:app` refers to the Flask app object created in `backend/run.py` via
`create_app(os.environ.get("FLASK_CONFIG", "development"))` — set
`FLASK_CONFIG=production` in the environment (already covered by `.env`
via `EnvironmentFile` in the systemd unit, §12) so it boots
`ProductionConfig`.

Worker count is not hard-coded — `GUNICORN_WORKERS` overrides the default
`(2 x CPU cores) + 1` heuristic. Pick a real number once you know the
VPS's actual CPU/RAM budget; see §14 for how that interacts with database
connection limits.

`flask run` (the Flask development server) must never be used in
production — only Gunicorn serves real traffic. `flask` itself remains
the right tool for CLI commands (migrations, seeding, the scheduler hook).

## 12. Running as a service (systemd)

Example unit files are provided under `deploy/systemd/*.example` — copy,
edit the paths/user, then install manually:

```bash
sudo cp deploy/systemd/womenshapingfutures.service.example /etc/systemd/system/womenshapingfutures.service
# edit paths/user in the copy
sudo systemctl daemon-reload
sudo systemctl enable --now womenshapingfutures
```

Restart after a code deploy:

```bash
sudo systemctl restart womenshapingfutures
```

A `restart` briefly drops connections; a full zero-downtime rolling
restart would need multiple Gunicorn instances behind a load balancer,
which is not part of this architecture — don't promise zero downtime here.
`systemctl reload` sends Gunicorn a graceful `HUP` (workers finish their
current request, up to `graceful_timeout` in `gunicorn.conf.py`, before
restarting) and is a smaller disruption than a full restart when only
application code changed and the master process itself doesn't need to
restart.

Logs land in the systemd journal:

```bash
journalctl -u womenshapingfutures -f
```

## 13. Pre-flight check

Run this after configuring `.env` and before starting the service, and
again any time `.env` changes:

```bash
FLASK_CONFIG=production flask production-check
```

It verifies `SECRET_KEY`/`JWT_SECRET_KEY`/`DATABASE_URL`/`CORS_ORIGINS`/
`MEDIA_ROOT` are present and sane, **without printing any secret value**
and **without touching the database** (no migration, no seed, no write —
safe to run repeatedly, including against a live deployment).

## 14. Database connection pooling

Each Gunicorn worker is a separate process with its own SQLAlchemy
connection pool (default: 5 connections + 10 overflow — see
`config.py`'s `SQLALCHEMY_ENGINE_OPTIONS`). That means the realistic
upper bound on simultaneous database connections from this app is
approximately:

```
GUNICORN_WORKERS x (pool_size + max_overflow) = GUNICORN_WORKERS x 15
```

Check PostgreSQL's own `max_connections` (`SHOW max_connections;`) before
picking a worker count, and leave headroom for `psql`/admin/backup
connections on top of the app's own usage. Do not guess a large pool size
or worker count without doing this arithmetic against the real VPS's
Postgres configuration — that's how a small VPS Postgres instance gets
starved of connections under real load.

`pool_pre_ping` and `pool_recycle=1800` are already set (see `config.py`)
so a connection Postgres has silently dropped is detected and replaced
rather than surfacing as a request failure.

## 15. Nginx

An example site config is provided at
`deploy/nginx/womenshapingfutures.conf.example` — **not installed
automatically**. Review it, copy it into
`/etc/nginx/sites-available/`, adjust the domain/paths, symlink into
`sites-enabled/`, then:

```bash
sudo nginx -t      # validate syntax before touching the running config
sudo systemctl reload nginx
```

It covers:

- Serving the Vite production build from `frontend/dist`, with an SPA
  fallback (`try_files ... /index.html`) so direct navigation to a
  client-side route (`/learning/...`, `/admin/...`, a flat article slug
  like `/some-article-title`, etc.) works instead of a raw Nginx 404.
- Proxying `/api/` to Gunicorn on `127.0.0.1:8000`, forwarding `Host`,
  `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` — matched by
  `TRUSTED_PROXY_COUNT=1` in the backend and `forwarded_allow_ips` in
  `gunicorn.conf.py`.
- Serving `/media/` directly from disk (Flask is never in the hot path
  for delivering an uploaded image) with a sensible `Cache-Control`, and
  never executing anything in that directory as code.
- Long-lived immutable caching for hashed `/assets/*` build output;
  `no-cache` on `index.html` specifically, so it always reflects the
  latest deploy's asset hashes.
- Denying access to `.env`, `.git`, and other files that should never be
  reachable over HTTP.
- Basic gzip for text assets (images are already WebP from
  `app/services/media.py` — Nginx does not recompress them).

TLS/HTTPS is a prerequisite this document assumes gets provisioned
separately (Let's Encrypt/certbot, or Hostinger's own tooling) — **this
task does not issue a certificate**. Add the HSTS header
(`Strict-Transport-Security`) only after confirming HTTPS works correctly
end-to-end; sending it prematurely can lock returning visitors' browsers
out of ever falling back to plain HTTP for the header's `max-age`.

## 16. Scheduled publishing

The app already has `flask publish-due-content` (see
`app/services/articles_workflow.py` for its concurrency-safety/
idempotency guarantees — safe to run on a schedule, safe to re-run, never
double-publishes). This task does not add Celery/Redis or any other
scheduler — it only documents invoking the existing command.

**Cron** (simplest option):

```cron
*/5 * * * * cd /var/www/womenshapingfutures/backend && /var/www/womenshapingfutures/backend/.venv/bin/flask publish-due-content >> /var/log/womenshapingfutures/publish.log 2>&1
```

(Set `FLASK_CONFIG=production` and the rest of `.env` however cron reads
environment on this system — e.g. via a wrapper script that sources
`.env` first, since cron does not read it automatically.)

**systemd timer** (alternative): example unit + timer files are provided
at `deploy/systemd/womenshapingfutures-publish.{service,timer}.example` —
not installed automatically; same manual copy/edit/enable flow as §12.

## 17. Health checks

`GET /api/v1/health` returns `{"status": "ok"}` with no authentication and
no database query — safe and cheap for an uptime monitor or load balancer
health check. It intentionally reveals nothing about the environment,
dependency versions, or any count derived from user data. There is no
separate deep/readiness endpoint in this task's scope; if one is added
later, keep it distinct from this endpoint and keep it inexpensive (e.g. a
bare `SELECT 1`), and never let it leak a raw database error message.

## 18. Deployment sequence (manual — nothing here is automated)

1. **Back up** the database (§10) and media directory before any deploy
   that includes a migration.
2. **Pull** the reviewed, already-tested code (a specific commit/tag, not
   an untested branch).
3. **Activate** the virtualenv, **install** backend dependencies
   (`pip install -r requirements.txt`).
4. **Apply** committed migrations: `flask db upgrade`.
5. **Build** the frontend: `npm ci && npm run build`.
6. **Run** `flask production-check` — fix anything it flags before
   proceeding.
7. **Restart** Gunicorn: `sudo systemctl restart womenshapingfutures`.
8. **Reload** Nginx only if its config changed: `sudo nginx -t &&
   sudo systemctl reload nginx`.
9. **Verify** health: `curl https://womenshapingfutures.org/api/v1/health`.
10. **Smoke-test** the site (§19).
11. **Verify** scheduled publishing is still wired up (cron/timer still
    enabled, hasn't been overwritten).

## 19. Rollback

Record the exact commit/tag you deployed before you deploy it, so
"rollback" means "redeploy that known-good commit," not guesswork.

**Application code** rolls back cleanly by redeploying the previous
commit and restarting Gunicorn.

**Database migrations are the hard part.** A code rollback does not
automatically undo a schema change. Before treating `flask db downgrade`
as your rollback plan:

- Confirm the specific migration's `downgrade()` is actually safe and
  reversible for this migration (some are not, by nature — a dropped
  column with real data in it cannot be un-dropped by a downgrade).
- Prefer restoring from the pre-deploy backup (§10) over downgrading a
  live database, if the migration is at all destructive.
- A **forward fix** (a new migration that corrects the problem) is often
  safer than reversing history that other now-newer code may already
  depend on.

Do not treat `flask db downgrade` as the default rollback strategy — it's
one option, evaluated per-migration, not a blanket procedure.

## 20. Post-deploy smoke test

**Public pages** (each should load without error and without exposing
draft/private content):

- `/` (homepage)
- A published Article's flat URL (`/some-article-slug`)
- `/learning`
- `/jobs`
- `/opportunities`
- `/events`
- `/resources`
- `/directory`
- `/contact`

**Admin** (log in as the Super Admin created in §8):

- Login succeeds; an unauthenticated request to an admin API route is
  rejected (401/403 — never a Flask HTML debug page).
- Dashboard loads.
- Media library loads; a test upload of an allowed image type succeeds
  and appears via its `/media/...` URL.
- Articles list loads.
- Notifications bell/inbox loads.

**Backend:**

- `GET /api/v1/health` returns `{"status": "ok"}`.
- Search returns results for a known term.
- `flask publish-due-content` runs cleanly with 0 due articles (a no-op
  is not an error).

## 21. Security smoke test

- A draft (unpublished) Article's URL returns 404, not the draft content.
- An unauthenticated request to an admin API endpoint (e.g.
  `GET /api/v1/admin/notifications`) returns 401, not data.
- The frontend is built with `VITE_USE_MOCK=false` and genuinely calls the
  real API — check the Network tab, don't just trust the env file.
- Uploading a disallowed file type (anything outside
  `ALLOWED_IMAGE_EXTENSIONS`) is rejected, not silently accepted.
- A private-data admin endpoint (Contact inquiries, Mentorship
  applications, Story Submissions, Nominations, Partnership inquiries)
  requires the right permission — test with a logged-in account that
  deliberately lacks it and confirm a 403.
- Hitting `/api/...` with a path that doesn't exist returns the app's own
  JSON 404, not a Flask/Werkzeug HTML debug page, and never a stack trace.
- `https://womenshapingfutures.org/.env` and
  `https://womenshapingfutures.org/.git/config` both return 404 (blocked
  by the Nginx config in §15).

## 22. Logging

Application logs (via `app/logging_config.py`) use a consistent
`timestamp LEVEL [logger] message` format and honor `LOG_LEVEL`. Under
systemd they land in the journal (§12); Gunicorn's own access/error logs
(`gunicorn.conf.py`) go to the same place by default.

**Never logged, anywhere in this app:** passwords, JWT tokens,
`Authorization` headers, full Contact messages, Mentorship application
answers, Story Submission bodies, or any other private submission
content. Server-side logs record that an event happened (a login, an
unexpected exception, a scheduler run) and enough to correlate it (a
request ID — see the `X-Request-ID` response header), not the sensitive
content involved.

## 23. What still needs manual VPS setup

This repository provides code, configuration templates, and this guide —
it does not and cannot do the following for you:

- Provisioning the VPS itself, installing PostgreSQL/Nginx/Python/Node.
- Creating the real `/var/www/womenshapingfutures/` directories and
  setting their ownership (the app's service user needs write access to
  `MEDIA_ROOT`; Nginx needs read access; never make anything world-writable).
- Issuing a TLS certificate and pointing DNS at the VPS.
- Installing the Nginx/systemd example configs from `deploy/` as real
  system files.
- Setting real values in `backend/.env` (never committed) and the
  frontend's production env file.
- Creating the first Super Admin account with a real, unique password.
- Setting up the actual backup schedule/retention/off-server copy and
  testing a restore.
- Any ongoing monitoring beyond the basic `/api/v1/health` endpoint —
  Sentry or a similar service is a reasonable **future** addition but is
  explicitly out of scope here (no vendor credentials are part of this
  repository).

## 24. Optional future enhancements (not built, not required)

- External error monitoring (e.g. Sentry) — would need its own account
  and DSN; not added here.
- A CI workflow that runs the backend/frontend test+build steps on every
  push (this repo has none yet) — a reasonable next step, kept simple
  (test + build only, no automated production deploy), not built as part
  of this task.
- A real XML sitemap endpoint — audited as part of this task and found
  not to exist yet; building one is a content-surface feature, out of
  scope for a production-hardening pass, and is called out as a
  remaining gap rather than invented here.
