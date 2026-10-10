import os
from datetime import timedelta

from sqlalchemy.pool import NullPool

basedir = os.path.abspath(os.path.dirname(__file__))

# Insecure placeholders that must NEVER reach ProductionConfig. Kept as a
# named constant (rather than inlined in DevelopmentConfig) so
# ProductionConfig's own __init__ can assert against it below — a simple
# string-equality check is a deliberately low-tech guard against "someone
# copy-pastes the dev default into a real .env file" without needing a
# secrets-strength heuristic.
_DEV_SECRET_KEY = "dev-secret-change-me"
_DEV_JWT_SECRET_KEY = "dev-jwt-secret-change-me-please-32-bytes-min"


def _parse_currency_allowlist(raw_value, default):
    """Shared by PAYSTACK_ALLOWED_CURRENCIES — split on commas, strip
    whitespace, uppercase, drop empties. Pulled out as its own function
    (rather than inlined in the Config class body, same as every other
    env-parsed value here) purely so a test can exercise the parsing
    rule directly without needing to reload this module under a
    monkeypatched environment variable.
    """
    if not raw_value:
        return list(default)
    return [c.strip().upper() for c in raw_value.split(",") if c.strip()]


class Config:
    ENV = "production"
    DEBUG = False
    TESTING = False

    # No default here at the shared-base-class level — see
    # DevelopmentConfig/TestingConfig (which set their own dev-only
    # fallback) and ProductionConfig (which requires the real env var and
    # fails fast if it's missing or still the dev placeholder).
    SECRET_KEY = os.environ.get("SECRET_KEY")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # pool_pre_ping avoids handing out a connection Postgres has silently
    # dropped (idle timeout, restart) — one extra cheap round-trip per
    # checkout rather than a request failing with an opaque
    # OperationalError. pool_recycle bounds how long any single connection
    # is reused for, so a connection that goes stale in some way
    # pre_ping doesn't catch is still replaced periodically. Deliberately
    # not setting pool_size/max_overflow here: SQLAlchemy's defaults (5 +
    # 10 overflow) per Gunicorn worker are a reasonable starting point for
    # a single small-to-medium VPS Postgres instance, and guessing a larger
    # number without real production traffic data would just make it
    # easier to exhaust Postgres's own max_connections when multiplied
    # across workers — see DEPLOYMENT.md's pool-sizing note for the actual
    # math to do once real Gunicorn worker count is known.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 1800}

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_ERROR_MESSAGE_KEY = "message"
    # PyJWT's `iat`/`nbf`/`exp` checks (flask_jwt_extended.config.Config.leeway
    # -> JWT_DECODE_LEEWAY, passed straight through to jwt.decode()'s `leeway`)
    # default to zero tolerance: a token is rejected as "not yet valid (iat)"
    # if its issued-at second is even fractionally ahead of the decoding
    # process's own clock read. A brand-new token, verified on the very next
    # request, can trip that with nothing wrong — ordinary sub-second
    # scheduling/clock jitter between the encode and decode calls (most
    # visible under sustained load, e.g. a large test suite) is enough to
    # flip which side of a whole-second boundary each integer timestamp
    # truncates to. Real deployments hit the same class of skew (VM/container
    # clocks, NTP correction), so this is set centrally rather than only for
    # tests. Two seconds is the conservative end of the standard clock-skew
    # tolerance range and does not touch signature, revocation, or the
    # exp/iat checks themselves — it only widens their comparison by a couple
    # of seconds.
    JWT_DECODE_LEEWAY = 2

    # Media is stored on the Hostinger VPS filesystem, entirely outside the
    # application's deployment checkout (not just outside backend/ — see
    # require_production_settings' repo-root containment check below), and
    # served in production by Nginx directly from MEDIA_ROOT at the
    # MEDIA_URL path — Flask only handles the upload/validate/process/
    # authorize side (see app/services/media.py). The dev-only default
    # below is deliberately inside the checkout purely for local-dev
    # convenience (no separate directory to create by hand); production
    # must override it to a persistent-data location such as
    # /var/lib/womenshapingfutures/media, kept separate from wherever the
    # code itself is checked out so a fresh-clone/rm-rf style redeploy can
    # never touch it.
    MEDIA_ROOT = os.environ.get(
        "MEDIA_ROOT", os.path.join(basedir, "instance", "media")
    )
    MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")

    # A SEPARATE filesystem location for circle_only Resource files (see
    # app/services/resource_downloads.py) — never served by Nginx and
    # never aliased under MEDIA_URL; the only path to a file here is
    # GET /api/v1/resources/downloads/<token> after a Circle entitlement
    # check has already issued that token. Same outside-the-checkout
    # requirement as MEDIA_ROOT (see require_production_settings below),
    # plus it must not be MEDIA_ROOT itself or a path inside it — that
    # would put a "protected" file right back under Nginx's public alias.
    PROTECTED_MEDIA_ROOT = os.environ.get(
        "PROTECTED_MEDIA_ROOT", os.path.join(basedir, "instance", "protected_media")
    )
    # How long a download token issued by POST /resources/{slug}/access
    # stays redeemable — long enough to start even a slow download right
    # after clicking, short enough that a leaked link stops working soon.
    RESOURCE_DOWNLOAD_TOKEN_TTL_MINUTES = int(
        os.environ.get("RESOURCE_DOWNLOAD_TOKEN_TTL_MINUTES", 10)
    )
    MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))  # 10MB
    ALLOWED_IMAGE_EXTENSIONS = set(
        os.environ.get("ALLOWED_IMAGE_EXTENSIONS", "jpg,jpeg,png,webp").split(",")
    )
    # Protected circle_only Resource files (documents, not images — see
    # app/services/resource_downloads.py's save_protected_upload()) are
    # typically larger than an image (a workbook/deck can legitimately be
    # several MB), so this is its own, separate ceiling rather than reusing
    # MAX_UPLOAD_SIZE — MediaService.validate() still enforces that 10MB
    # limit on its own, independent of whatever this is set to.
    MAX_PROTECTED_UPLOAD_SIZE = int(
        os.environ.get("MAX_PROTECTED_UPLOAD_SIZE", 50 * 1024 * 1024)  # 50MB
    )
    ALLOWED_PROTECTED_RESOURCE_EXTENSIONS = set(
        os.environ.get("ALLOWED_PROTECTED_RESOURCE_EXTENSIONS", "pdf,docx,xlsx,pptx,zip").split(",")
    )
    # Flask/Werkzeug refuses any request body above this before either
    # upload endpoint's own validation ever runs — it must be at least as
    # large as the bigger of the two per-endpoint ceilings above, or a
    # legitimate protected-file upload would be rejected at the WSGI layer
    # before MediaService vs. the protected-upload path even gets a say.
    # Each endpoint's own service still separately enforces its own
    # (smaller, for images) limit — this is only the outer ceiling.
    MAX_CONTENT_LENGTH = max(MAX_UPLOAD_SIZE, MAX_PROTECTED_UPLOAD_SIZE)
    # (max_width, max_height) per generated responsive WebP variant.
    MEDIA_VARIANTS = {
        "thumbnail": (200, 200),
        "card": (600, 400),
        "medium": (1000, 667),
        "large": (1600, 1067),
        "hero": (2400, 1350),
    }

    MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY")
    MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET")
    MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE")
    MPESA_PASSKEY = os.environ.get("MPESA_PASSKEY")

    # Paystack — WSF Circle one-time membership-period payments (see
    # app/services/paystack.py, app/models/circle.py's CirclePayment).
    # Unrelated to the MPESA_* placeholders above, which are reserved for
    # a possible future direct Safaricom Daraja integration; Paystack's
    # own M-Pesa channel (for Kenyan customers) goes through Paystack's
    # hosted checkout, never through those credentials.
    #
    # Disabled by default: importing/loading this app, and running its
    # test suite, must never require a real Paystack secret key, and a
    # deployment that hasn't deliberately opted in must never be able to
    # accept a real charge. app/services/paystack.py checks this flag
    # itself before ever making an outbound request, rather than relying
    # on every caller to remember to check it.
    PAYSTACK_ENABLED = os.environ.get("PAYSTACK_ENABLED", "false").strip().lower() in ("true", "1", "yes")
    # Backend-only — never serialized into any API response, never sent to
    # the frontend. The hosted-redirect checkout flow this integration
    # uses has no need for a separate publishable/public key.
    PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY")
    # Currencies WSF has actually enabled for Circle payments — NOT every
    # currency Paystack itself might support. Paystack's Kenya merchants
    # are limited to KES/USD collection regardless of what's listed here,
    # but this is WSF's own narrower allowlist within that, so a
    # CirclePlan in some other ISO 4217 currency can never become
    # Paystack-payable just by existing. Defaults to the single currency
    # already confirmed usable (KES) rather than assuming USD is safe too.
    PAYSTACK_ALLOWED_CURRENCIES = _parse_currency_allowlist(os.environ.get("PAYSTACK_ALLOWED_CURRENCIES"), ["KES"])

    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    API_URL = os.environ.get("API_URL", "http://localhost:5000/api/v1")
    # The canonical public domain (no trailing slash) — used only where the
    # backend genuinely needs to know it (none of the modules touched by
    # this task do yet; kept here so it's documented in one place per the
    # production-readiness audit rather than invented ad hoc later).
    PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "https://womenshapingfutures.org")

    # Comma-separated list of exact origins allowed to call the API with
    # credentials, e.g. "https://womenshapingfutures.org,https://www.womenshapingfutures.org".
    # Falls back to FRONTEND_URL (a single origin) when unset, which keeps
    # existing local-dev behavior unchanged. See app/__init__.py for how
    # this becomes flask-cors's `origins` list.
    _cors_origins_env = os.environ.get("CORS_ORIGINS")
    CORS_ORIGINS = (
        [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
        if _cors_origins_env
        else [FRONTEND_URL]
    )

    # Standard practical log format: timestamp, level, logger name,
    # message — see app/logging_config.py. LOG_LEVEL is a plain stdlib
    # level name (DEBUG/INFO/WARNING/ERROR); invalid values fall back to
    # INFO rather than crashing startup over a typo'd env var.
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Number of reverse proxies (Nginx) actually sitting in front of this
    # app, for werkzeug's ProxyFix (see app/__init__.py). Trusting more
    # hops than truly exist lets a client spoof X-Forwarded-For; trusting
    # zero means every request behind Nginx looks like it came from
    # 127.0.0.1 and https:// always looks like http://. The documented
    # architecture (Nginx -> Gunicorn, no other intermediary load
    # balancer) is exactly one hop.
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", 1))

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # Provider-neutral outbound email (see app/services/email.py) — used
    # today only by password recovery (app/services/password_reset.py).
    # "console" (the shared default, overridden to require "smtp" in
    # ProductionConfig below) logs the email instead of sending it, so a
    # fresh local checkout can exercise the full forgot/reset-password
    # flow with zero mail setup. "smtp" sends via Python's stdlib
    # smtplib/email — no vendor SDK, so WSF isn't locked into one
    # provider; any standard SMTP relay (a VPS's own Postfix, a
    # transactional-email provider's SMTP endpoint, etc.) works.
    EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "console")
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").strip().lower() not in ("false", "0", "no")
    SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL")
    SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Women Shaping Futures")


class DevelopmentConfig(Config):
    ENV = "development"
    DEBUG = True
    # Development-only fallbacks: convenient for a fresh local checkout,
    # never inherited by ProductionConfig (which sets no default at all —
    # see below).
    SECRET_KEY = os.environ.get("SECRET_KEY", _DEV_SECRET_KEY)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _DEV_JWT_SECRET_KEY)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://wsf:wsf_dev_pw@localhost:5432/wsf_dev"
    )
    # A lone local developer's own machine — TRUSTED_PROXY_COUNT=1 would
    # otherwise silently drop the real client IP behind a proxy that
    # doesn't exist in `flask run`.
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", 0))


class TestingConfig(Config):
    ENV = "testing"
    TESTING = True
    # Same reasoning as DevelopmentConfig — tests must never fail merely
    # because no SECRET_KEY/JWT_SECRET_KEY happens to be set in the shell.
    SECRET_KEY = os.environ.get("SECRET_KEY", _DEV_SECRET_KEY)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _DEV_JWT_SECRET_KEY)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://wsf:wsf_dev_pw@localhost:5432/wsf_test"
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    TRUSTED_PROXY_COUNT = 0
    # Each test gets its own create_app("testing") call, and Flask-SQLAlchemy
    # keeps a separate Engine per Flask app instance. A pooled engine (the
    # default QueuePool) leaves idle connections open until the pool is
    # explicitly disposed or the Engine is garbage-collected — neither of
    # which is deterministic across hundreds of function-scoped app
    # fixtures — so the test suite can exhaust Postgres max_connections
    # well before that. NullPool opens a connection per checkout and closes
    # it immediately on checkin, so no idle connections accumulate between
    # tests even if disposal is ever missed.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "poolclass": NullPool}


class ProductionConfig(Config):
    ENV = "production"
    DEBUG = False
    # No fallback for SECRET_KEY/JWT_SECRET_KEY (inherited as None from
    # Config) and no fallback for the database URL — see
    # require_production_settings() below, which create_app() calls only
    # for this config, so a misconfigured production deployment fails at
    # startup with a clear error instead of silently running with a
    # guessable secret or no database at all.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def _path_resolves_inside(candidate, container):
    """True iff `candidate` resolves to a path inside (or equal to)
    `container`. Shared by the MEDIA_ROOT and PROTECTED_MEDIA_ROOT
    containment checks below — a pure path-string comparison (no
    filesystem access required), using os.path.commonpath rather than a
    naive startswith so a sibling directory that merely shares a string
    prefix is never mistaken for being inside `container`.
    """
    normalized_candidate = os.path.realpath(candidate)
    normalized_container = os.path.realpath(container)
    try:
        return os.path.commonpath([normalized_candidate, normalized_container]) == normalized_container
    except ValueError:
        # Can't prove containment (e.g. different drives) — never crash
        # startup over this; treat as "not proven unsafe" rather than
        # silently passing something we can't actually compare.
        return False


def require_production_settings(app):
    """Fail fast at startup if ProductionConfig is missing something that
    must never be allowed to run with an insecure/absent value. Called
    once from create_app() only when config_name == "production" — never
    for development/testing, which each carry their own safe dev-only
    defaults above. Raises RuntimeError (not SystemExit) so callers
    (Gunicorn, `flask production-check`, tests) can catch/report it
    uniformly rather than the process silently vanishing.
    """
    problems = []

    if not app.config.get("SECRET_KEY"):
        problems.append("SECRET_KEY is not set.")
    elif app.config["SECRET_KEY"] == _DEV_SECRET_KEY:
        problems.append("SECRET_KEY is still the development placeholder value.")

    if not app.config.get("JWT_SECRET_KEY"):
        problems.append("JWT_SECRET_KEY is not set.")
    elif app.config["JWT_SECRET_KEY"] == _DEV_JWT_SECRET_KEY:
        problems.append("JWT_SECRET_KEY is still the development placeholder value.")

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        problems.append("DATABASE_URL is not set.")
    elif "wsf_dev" in app.config["SQLALCHEMY_DATABASE_URI"] or "wsf_test" in app.config["SQLALCHEMY_DATABASE_URI"]:
        problems.append("DATABASE_URL points at a development/test database name (wsf_dev/wsf_test).")

    if not app.config.get("CORS_ORIGINS"):
        problems.append("CORS_ORIGINS (or FRONTEND_URL) is not set.")
    elif any("localhost" in origin or "127.0.0.1" in origin for origin in app.config["CORS_ORIGINS"]):
        problems.append("CORS_ORIGINS includes a localhost/127.0.0.1 origin in production.")

    # FRONTEND_URL feeds the Paystack callback URL, password-reset links,
    # and Event/Learning confirmation links (see each call site's own
    # comment) — CORS_ORIGINS being checked above does NOT also cover this:
    # an operator can fix CORS_ORIGINS and still leave FRONTEND_URL at its
    # http://localhost:5173 default, and every one of those links would
    # silently keep pointing at localhost in production.
    frontend_url = app.config.get("FRONTEND_URL") or ""
    if "localhost" in frontend_url or "127.0.0.1" in frontend_url:
        problems.append("FRONTEND_URL must not be localhost/127.0.0.1 in production.")
    elif not frontend_url.startswith("https://"):
        problems.append(f"FRONTEND_URL must be an https:// URL in production (got {frontend_url!r}).")

    # PUBLIC_SITE_URL feeds the canonical /sitemap.xml and /robots.txt
    # output — a wrong value here leaks into search engines, not just a
    # broken link a person might notice and report.
    public_site_url = app.config.get("PUBLIC_SITE_URL") or ""
    if "localhost" in public_site_url or "127.0.0.1" in public_site_url:
        problems.append("PUBLIC_SITE_URL must not be localhost/127.0.0.1 in production.")
    elif not public_site_url.startswith("https://"):
        problems.append(f"PUBLIC_SITE_URL must be an https:// URL in production (got {public_site_url!r}).")

    # Paystack: only checked when WSF has actually opted in. Presence only
    # — never inspect/log the value itself, and deliberately never reject a
    # test-mode secret here (the first VPS deployment intentionally runs
    # Paystack in test mode; distinguishing test vs. live keys is a
    # separate, later decision, not a startup-safety concern).
    if app.config.get("PAYSTACK_ENABLED") and not app.config.get("PAYSTACK_SECRET_KEY"):
        problems.append("PAYSTACK_SECRET_KEY is not set (required when PAYSTACK_ENABLED=true).")

    # MEDIA_ROOT: uploads are persistent, mutable, user-generated data that
    # must survive every future redeploy. The deployment checkout is
    # backend/ and frontend/ side by side under one parent directory (e.g.
    # /var/www/womenshapingfutures/{backend,frontend}) — that whole parent
    # is "the repo root" for this check, not just backend/, because a
    # fresh-clone/`git clean -fdx`/`rm -rf`-and-re-clone style redeploy
    # replaces the ENTIRE checkout, frontend/ included, not only backend/.
    # MEDIA_ROOT defaults (see above) to a path inside backend/, which is
    # inside that same checkout, so catching containment anywhere under
    # the repo root — not just under backend/ — is what actually matches
    # the real hazard. Mutable media belongs in a separate, persistent-data
    # location entirely outside wherever the application code is checked
    # out (e.g. /var/lib/womenshapingfutures/media — any such path is
    # fine, there is nothing special about that one). This is a pure
    # path-string comparison (no filesystem access of MEDIA_ROOT itself
    # required), so it works even before the directory has ever been
    # created — unlike the existence/writability checks, which must stay
    # in `flask production-check` since a fresh VPS provisioning may not
    # have created the directory yet. Uses os.path.commonpath rather than
    # a naive startswith so a sibling directory that merely shares a
    # string prefix (e.g. /var/www/womenshapingfutures-backup) is never
    # mistaken for being inside /var/www/womenshapingfutures.
    media_root = app.config.get("MEDIA_ROOT") or ""
    repo_root = os.path.dirname(basedir)
    if media_root and _path_resolves_inside(media_root, repo_root):
        problems.append(
            f"MEDIA_ROOT ({media_root!r}) resolves inside the application's deployment "
            "checkout — uploads would be lost on a fresh-clone/git-clean/rm-rf style "
            "redeploy. Set it to a path entirely outside the checkout, e.g. "
            "/var/lib/womenshapingfutures/media (any separate, persistent-data location "
            "works — this is just an example, not a required literal path)."
        )

    # PROTECTED_MEDIA_ROOT: same "outside the checkout" hazard as
    # MEDIA_ROOT (a redeploy must never lose a Circle resource's file),
    # plus its own, distinct hazard: it must not be MEDIA_ROOT, and must
    # not resolve inside it — that would put a "protected" file right
    # back under Nginx's public /media/ alias, defeating the entire
    # point (see app/services/resource_downloads.py).
    protected_media_root = app.config.get("PROTECTED_MEDIA_ROOT") or ""
    if protected_media_root:
        if _path_resolves_inside(protected_media_root, repo_root):
            problems.append(
                f"PROTECTED_MEDIA_ROOT ({protected_media_root!r}) resolves inside the "
                "application's deployment checkout — protected Resource files would be lost "
                "on a fresh-clone/git-clean/rm-rf style redeploy. Set it to a path entirely "
                "outside the checkout, e.g. /var/lib/womenshapingfutures/protected_media "
                "(any separate, persistent-data location works — this is just an example, "
                "not a required literal path)."
            )
        if media_root and (
            os.path.realpath(protected_media_root) == os.path.realpath(media_root)
            or _path_resolves_inside(protected_media_root, media_root)
        ):
            problems.append(
                f"PROTECTED_MEDIA_ROOT ({protected_media_root!r}) must not be MEDIA_ROOT or a "
                "path inside it — Nginx serves MEDIA_ROOT publicly, so a protected Resource "
                "file placed there would no longer be protected."
            )

    # The "console" email backend logs full email content — including a
    # raw password-reset link — to the application log. That must be
    # structurally impossible in production, not just discouraged, so
    # this is enforced here (which create_app() calls unconditionally for
    # config_name == "production") rather than left to a reviewer
    # noticing an EMAIL_BACKEND=console line in some .env file.
    email_backend = app.config.get("EMAIL_BACKEND")
    if email_backend != "smtp":
        problems.append(
            f"EMAIL_BACKEND must be 'smtp' in production (got {email_backend!r}) — "
            "the console backend would log raw password-reset links."
        )
    else:
        if not app.config.get("SMTP_HOST"):
            problems.append("SMTP_HOST is not set (required when EMAIL_BACKEND=smtp).")
        if not app.config.get("SMTP_FROM_EMAIL"):
            problems.append("SMTP_FROM_EMAIL is not set (required when EMAIL_BACKEND=smtp).")

    if problems:
        raise RuntimeError(
            "Refusing to start with ProductionConfig due to unsafe configuration:\n  - "
            + "\n  - ".join(problems)
        )
