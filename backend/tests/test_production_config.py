"""Focused tests for production-hardening behavior: fail-fast production
config validation (config.require_production_settings), the read-only
`flask production-check` CLI command, and security response headers.

These deliberately do not go through the `app`/`client` fixtures in
conftest.py (which always build "testing" config against the real
Postgres test DB) — require_production_settings() only ever inspects
app.config, so a bare Flask app with hand-set config is enough and keeps
these tests fast and independent of any database.
"""

import os

import pytest
from flask import Flask

from config import require_production_settings


def _bare_app(**config_overrides):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "a-real-random-production-secret"
    app.config["JWT_SECRET_KEY"] = "a-different-real-random-jwt-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://wsf:x@db-host:5432/womenshapingfutures"
    app.config["CORS_ORIGINS"] = ["https://womenshapingfutures.org"]
    # See app/services/email.py / config.py's require_production_settings:
    # the console email backend (which would log raw password-reset
    # links) is forbidden in production, so a "valid" production config
    # must select smtp and carry its two required fields.
    app.config["EMAIL_BACKEND"] = "smtp"
    app.config["SMTP_HOST"] = "smtp.example.com"
    app.config["SMTP_FROM_EMAIL"] = "noreply@womenshapingfutures.org"
    # FRONTEND_URL/PUBLIC_SITE_URL/Paystack/MEDIA_ROOT: a "valid" production
    # config must satisfy every check, same as the fields above, so every
    # test that overrides just ONE field below to exercise ITS failure mode
    # isn't tripped up by one of these instead.
    app.config["FRONTEND_URL"] = "https://womenshapingfutures.org"
    app.config["PUBLIC_SITE_URL"] = "https://womenshapingfutures.org"
    app.config["PAYSTACK_ENABLED"] = False
    app.config["PAYSTACK_SECRET_KEY"] = None
    app.config["MEDIA_ROOT"] = "/var/lib/womenshapingfutures/media"
    app.config.update(config_overrides)
    return app


def test_require_production_settings_passes_with_valid_config():
    app = _bare_app()
    require_production_settings(app)  # must not raise


def test_require_production_settings_rejects_missing_secret_key():
    app = _bare_app(SECRET_KEY=None)
    with pytest.raises(RuntimeError, match="SECRET_KEY is not set"):
        require_production_settings(app)


def test_require_production_settings_rejects_dev_placeholder_secret_key():
    app = _bare_app(SECRET_KEY="dev-secret-change-me")
    with pytest.raises(RuntimeError, match="development placeholder"):
        require_production_settings(app)


def test_require_production_settings_rejects_dev_placeholder_jwt_secret():
    app = _bare_app(JWT_SECRET_KEY="dev-jwt-secret-change-me-please-32-bytes-min")
    with pytest.raises(RuntimeError, match="development placeholder"):
        require_production_settings(app)


def test_require_production_settings_rejects_missing_database_url():
    app = _bare_app(SQLALCHEMY_DATABASE_URI=None)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        require_production_settings(app)


@pytest.mark.parametrize(
    "db_uri",
    [
        "postgresql://wsf:wsf_dev_pw@localhost:5432/wsf_dev",
        "postgresql://wsf:wsf_dev_pw@localhost:5432/wsf_test",
    ],
)
def test_require_production_settings_rejects_dev_or_test_database_name(db_uri):
    app = _bare_app(SQLALCHEMY_DATABASE_URI=db_uri)
    with pytest.raises(RuntimeError, match="development/test database name"):
        require_production_settings(app)


def test_require_production_settings_rejects_missing_cors_origins():
    app = _bare_app(CORS_ORIGINS=[])
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        require_production_settings(app)


@pytest.mark.parametrize(
    "origins",
    [
        ["http://localhost:5173"],
        ["https://womenshapingfutures.org", "http://127.0.0.1:3000"],
    ],
)
def test_require_production_settings_rejects_localhost_cors_origin(origins):
    app = _bare_app(CORS_ORIGINS=origins)
    with pytest.raises(RuntimeError, match="localhost/127.0.0.1"):
        require_production_settings(app)


def test_require_production_settings_rejects_console_email_backend():
    app = _bare_app(EMAIL_BACKEND="console")
    with pytest.raises(RuntimeError, match="EMAIL_BACKEND must be 'smtp'"):
        require_production_settings(app)


def test_require_production_settings_rejects_missing_smtp_host():
    app = _bare_app(SMTP_HOST=None)
    with pytest.raises(RuntimeError, match="SMTP_HOST is not set"):
        require_production_settings(app)


def test_require_production_settings_rejects_missing_smtp_from_email():
    app = _bare_app(SMTP_FROM_EMAIL=None)
    with pytest.raises(RuntimeError, match="SMTP_FROM_EMAIL is not set"):
        require_production_settings(app)


@pytest.mark.parametrize(
    "frontend_url",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)
def test_require_production_settings_rejects_localhost_frontend_url(frontend_url):
    app = _bare_app(FRONTEND_URL=frontend_url)
    with pytest.raises(RuntimeError, match="FRONTEND_URL must not be localhost"):
        require_production_settings(app)


def test_require_production_settings_rejects_http_frontend_url():
    app = _bare_app(FRONTEND_URL="http://womenshapingfutures.org")
    with pytest.raises(RuntimeError, match="FRONTEND_URL must be an https"):
        require_production_settings(app)


def test_require_production_settings_accepts_valid_https_frontend_url():
    app = _bare_app(FRONTEND_URL="https://womenshapingfutures.org")
    require_production_settings(app)  # must not raise


@pytest.mark.parametrize(
    "public_site_url",
    ["http://localhost:5173", "http://127.0.0.1:8000"],
)
def test_require_production_settings_rejects_localhost_public_site_url(public_site_url):
    app = _bare_app(PUBLIC_SITE_URL=public_site_url)
    with pytest.raises(RuntimeError, match="PUBLIC_SITE_URL must not be localhost"):
        require_production_settings(app)


def test_require_production_settings_rejects_http_public_site_url():
    app = _bare_app(PUBLIC_SITE_URL="http://womenshapingfutures.org")
    with pytest.raises(RuntimeError, match="PUBLIC_SITE_URL must be an https"):
        require_production_settings(app)


def test_require_production_settings_accepts_valid_https_public_site_url():
    app = _bare_app(PUBLIC_SITE_URL="https://womenshapingfutures.org")
    require_production_settings(app)  # must not raise


def test_require_production_settings_accepts_paystack_disabled_with_no_secret():
    app = _bare_app(PAYSTACK_ENABLED=False, PAYSTACK_SECRET_KEY=None)
    require_production_settings(app)  # must not raise


def test_require_production_settings_rejects_paystack_enabled_with_no_secret():
    app = _bare_app(PAYSTACK_ENABLED=True, PAYSTACK_SECRET_KEY=None)
    with pytest.raises(RuntimeError, match="PAYSTACK_SECRET_KEY is not set"):
        require_production_settings(app)


def test_require_production_settings_accepts_paystack_enabled_with_secret_without_exposing_it():
    # A deliberately neutral, non-key-shaped placeholder — this test exists
    # specifically to prove a configured secret never ends up in the
    # exception message, not to assert anything about Paystack's real key
    # format. Use a neutral dummy value so secret scanners do not mistake
    # the fixture for a real provider key.
    app = _bare_app(PAYSTACK_ENABLED=True, PAYSTACK_SECRET_KEY="dummy-paystack-secret")
    require_production_settings(app)  # must not raise
    # Re-run a failing case alongside a configured secret to confirm the
    # secret value itself never appears in any problem message.
    app = _bare_app(
        PAYSTACK_ENABLED=True,
        PAYSTACK_SECRET_KEY="dummy-paystack-secret",
        SECRET_KEY=None,
    )
    with pytest.raises(RuntimeError) as excinfo:
        require_production_settings(app)
    assert "dummy-paystack-secret" not in str(excinfo.value)


def test_require_production_settings_rejects_media_root_inside_backend_subdir():
    from config import basedir

    app = _bare_app(MEDIA_ROOT=os.path.join(basedir, "instance", "media"))
    with pytest.raises(RuntimeError, match="resolves inside the application's deployment checkout"):
        require_production_settings(app)


def test_require_production_settings_rejects_media_root_inside_frontend_subdir():
    # The checkout root is backend/'s PARENT directory (where backend/ and
    # frontend/ sit side by side) — this proves the check covers frontend/
    # too, not just backend/, since a fresh-clone/rm-rf redeploy replaces
    # the whole checkout, not only the backend half of it.
    from config import basedir

    repo_root = os.path.dirname(basedir)
    app = _bare_app(MEDIA_ROOT=os.path.join(repo_root, "frontend", "dist", "media"))
    with pytest.raises(RuntimeError, match="resolves inside the application's deployment checkout"):
        require_production_settings(app)


def test_require_production_settings_rejects_media_root_equal_to_repo_root():
    from config import basedir

    repo_root = os.path.dirname(basedir)
    app = _bare_app(MEDIA_ROOT=repo_root)
    with pytest.raises(RuntimeError, match="resolves inside the application's deployment checkout"):
        require_production_settings(app)


def test_require_production_settings_accepts_media_root_outside_checkout():
    app = _bare_app(MEDIA_ROOT="/var/lib/womenshapingfutures/media")
    require_production_settings(app)  # must not raise


def test_require_production_settings_accepts_sibling_directory_sharing_a_string_prefix():
    # Robustness check for the os.path.commonpath-based containment test:
    # a directory that merely starts with the same characters as the repo
    # root (e.g. "<repo>-backup") is a SIBLING, not something actually
    # inside the checkout — a naive string startswith() would wrongly
    # reject this; real path containment must not.
    from config import basedir

    repo_root = os.path.dirname(basedir)
    sibling = repo_root.rstrip("/") + "-media-backup"
    app = _bare_app(MEDIA_ROOT=sibling)
    require_production_settings(app)  # must not raise


def test_require_production_settings_reports_every_problem_at_once():
    app = Flask(__name__)
    # Nothing set at all — every check should fail together, not just the
    # first one, so an operator can fix everything in one pass instead of
    # re-running the check repeatedly to discover each problem in turn.
    with pytest.raises(RuntimeError) as excinfo:
        require_production_settings(app)
    message = str(excinfo.value)
    assert "SECRET_KEY is not set" in message
    assert "JWT_SECRET_KEY is not set" in message
    assert "DATABASE_URL is not set" in message
    assert "CORS_ORIGINS" in message


def test_create_app_production_boots_when_config_is_valid(monkeypatch):
    # config.py's class attributes are computed once, at module import
    # time, from os.environ — by the time this test runs, config has
    # already been imported (e.g. via conftest.py), so monkeypatching env
    # vars here would have no effect on the already-defined ProductionConfig
    # attributes. Patching the class attributes directly exercises the same
    # create_app("production") code path against the values it will
    # actually see.
    from config import ProductionConfig

    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a-real-random-production-secret")
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "a-different-real-random-jwt-secret")
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", "postgresql://wsf:x@db-host:5432/womenshapingfutures")
    monkeypatch.setattr(ProductionConfig, "CORS_ORIGINS", ["https://womenshapingfutures.org"])
    monkeypatch.setattr(ProductionConfig, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr(ProductionConfig, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(ProductionConfig, "SMTP_FROM_EMAIL", "noreply@womenshapingfutures.org")
    # FRONTEND_URL/MEDIA_ROOT default (inherited from Config, unpatched) to
    # http://localhost:5173 and a path inside this backend checkout — both
    # now rejected by require_production_settings (see above), so a
    # "boots when valid" test must patch them to real values too.
    monkeypatch.setattr(ProductionConfig, "FRONTEND_URL", "https://womenshapingfutures.org")
    monkeypatch.setattr(ProductionConfig, "MEDIA_ROOT", "/var/lib/womenshapingfutures/media")

    from app import create_app

    app = create_app("production")
    assert app.config["ENV"] == "production"
    assert app.config["DEBUG"] is False
    assert app.config["CONFIG_NAME"] == "production"


def test_create_app_production_refuses_to_boot_with_dev_secret(monkeypatch):
    from config import ProductionConfig

    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "dev-secret-change-me")
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "a-different-real-random-jwt-secret")
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", "postgresql://wsf:x@db-host:5432/womenshapingfutures")
    monkeypatch.setattr(ProductionConfig, "CORS_ORIGINS", ["https://womenshapingfutures.org"])

    from app import create_app

    with pytest.raises(RuntimeError, match="development placeholder"):
        create_app("production")


def test_create_app_rejects_unknown_config_name():
    # The real danger this guards against: an explicit but invalid
    # FLASK_CONFIG value (a typo, a stale value from a renamed config) must
    # never be silently accepted — see app/__init__.py's own config_by_name
    # lookup, which now raises a clear RuntimeError naming the bad value and
    # the valid options instead of a bare KeyError.
    from app import create_app

    with pytest.raises(RuntimeError, match="Unknown FLASK_CONFIG 'staging'"):
        create_app("staging")


def test_create_app_development_still_works_with_no_config_name():
    # Ordinary local development is explicitly NOT required to set
    # FLASK_CONFIG — create_app()'s own default ("development") is
    # unchanged by this module's hardening. This only guards against an
    # explicit-but-wrong value, never against omitting it entirely.
    from app import create_app

    app = create_app()
    assert app.config["ENV"] == "development"
    assert app.config["CONFIG_NAME"] == "development"
    # DevelopmentConfig's own dev-only secret fallbacks (never valid in
    # production — see require_production_settings) are fine here, and
    # require_production_settings is never even invoked for this config
    # name, exactly as before.
    assert app.config["DEBUG"] is True


def test_production_check_cli_fails_when_active_config_is_not_production():
    # The exact scenario Module 7 fixes: `flask production-check` run
    # against whatever app create_app() actually built — here the
    # ordinary development default (no config_name passed), the same
    # thing Flask's own CLI auto-discovery falls back to when invoked
    # bare (no `--app run:app`), silently ignoring FLASK_CONFIG. This
    # must be a hard failure (non-zero exit), never a warning that still
    # reports PASSED.
    from app import create_app

    app = create_app()
    assert app.config["CONFIG_NAME"] == "development"

    runner = app.test_cli_runner()
    result = runner.invoke(args=["production-check"])

    assert result.exit_code != 0
    assert "PRODUCTION CHECK FAILED" in result.output
    assert "CONFIG_NAME is 'development'" in result.output
    assert "not 'production'" in result.output
    # Never downgraded to a mere warning line (the pre-fix bug).
    assert "PRODUCTION CHECK PASSED" not in result.output


def test_production_check_cli_passes_with_valid_production_config(monkeypatch):
    # Mirrors test_create_app_production_boots_when_config_is_valid's own
    # monkeypatch pattern, but drives the actual `production-check` CLI
    # command end-to-end (not just require_production_settings) — this is
    # the "production app + valid settings -> passes" counterpart to the
    # failure test above.
    from config import ProductionConfig

    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a-real-random-production-secret")
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "a-different-real-random-jwt-secret")
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", "postgresql://wsf:x@db-host:5432/womenshapingfutures")
    monkeypatch.setattr(ProductionConfig, "CORS_ORIGINS", ["https://womenshapingfutures.org"])
    monkeypatch.setattr(ProductionConfig, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr(ProductionConfig, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(ProductionConfig, "SMTP_FROM_EMAIL", "noreply@womenshapingfutures.org")
    monkeypatch.setattr(ProductionConfig, "FRONTEND_URL", "https://womenshapingfutures.org")
    monkeypatch.setattr(ProductionConfig, "MEDIA_ROOT", "/var/lib/womenshapingfutures/media")

    from app import create_app

    app = create_app("production")
    assert app.config["CONFIG_NAME"] == "production"

    runner = app.test_cli_runner()
    result = runner.invoke(args=["production-check"])

    assert result.exit_code == 0
    assert "PRODUCTION CHECK PASSED" in result.output
    assert "Active config: FLASK_CONFIG='production'" in result.output
    assert "PRODUCTION CHECK FAILED" not in result.output


def test_security_headers_present_on_response(client):
    resp = client.get("/api/v1/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in resp.headers


def test_health_endpoint_never_leaks_secret_values(client):
    resp = client.get("/api/v1/health")
    body = resp.get_data(as_text=True)
    assert "SECRET_KEY" not in body
    assert "DATABASE_URL" not in body
    assert "dev-secret-change-me" not in body
