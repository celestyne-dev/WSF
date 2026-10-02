"""Focused tests for production-hardening behavior: fail-fast production
config validation (config.require_production_settings), the read-only
`flask production-check` CLI command, and security response headers.

These deliberately do not go through the `app`/`client` fixtures in
conftest.py (which always build "testing" config against the real
Postgres test DB) — require_production_settings() only ever inspects
app.config, so a bare Flask app with hand-set config is enough and keeps
these tests fast and independent of any database.
"""

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

    from app import create_app

    app = create_app("production")
    assert app.config["ENV"] == "production"
    assert app.config["DEBUG"] is False


def test_create_app_production_refuses_to_boot_with_dev_secret(monkeypatch):
    from config import ProductionConfig

    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "dev-secret-change-me")
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "a-different-real-random-jwt-secret")
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", "postgresql://wsf:x@db-host:5432/womenshapingfutures")
    monkeypatch.setattr(ProductionConfig, "CORS_ORIGINS", ["https://womenshapingfutures.org"])

    from app import create_app

    with pytest.raises(RuntimeError, match="development placeholder"):
        create_app("production")


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
