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

    # Media is stored on the Hostinger VPS filesystem, outside the app's
    # source tree, and served in production by Nginx directly from
    # MEDIA_ROOT at the MEDIA_URL path — Flask only handles the
    # upload/validate/process/authorize side (see app/services/media.py).
    MEDIA_ROOT = os.environ.get(
        "MEDIA_ROOT", os.path.join(basedir, "instance", "media")
    )
    MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")
    MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))  # 10MB
    ALLOWED_IMAGE_EXTENSIONS = set(
        os.environ.get("ALLOWED_IMAGE_EXTENSIONS", "jpg,jpeg,png,webp").split(",")
    )
    MAX_CONTENT_LENGTH = MAX_UPLOAD_SIZE
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
