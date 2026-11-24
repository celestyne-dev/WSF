"""Security headers + CSP Report-Only (app/services/security_headers.py) and
CSP violation collection (app/api/v1/security.py)."""
import json
import os

import pytest

from app.extensions import db
from app.models.csp_violation import CspViolation
from app.services.security_headers import build_csp, serialize_csp

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _csp(res):
    return res.headers.get("Content-Security-Policy-Report-Only")


def _directives(header):
    out = {}
    for part in header.split(";"):
        bits = part.strip().split()
        if bits:
            out[bits[0]] = bits[1:]
    return out


def test_baseline_headers_on_every_response(client):
    for path in ("/api/v1/public/settings", "/"):
        res = client.get(path)
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert res.headers["X-Frame-Options"] == "DENY"
        pp = res.headers["Permissions-Policy"]
        for feature in ("camera=()", "microphone=()", "geolocation=()", "payment=()", "usb=()", "autoplay=()"):
            assert feature in pp
        assert 'fullscreen=(self "https://www.youtube-nocookie.com"' in pp


def test_csp_report_only_on_html_only(client):
    assert _csp(client.get("/api/v1/public/settings")) is None
    res = client.get("/")
    header = _csp(res)
    assert header and "Content-Security-Policy" not in res.headers  # not enforced yet
    d = _directives(header)
    assert d["default-src"] == ["'self'"] and d["script-src"] == ["'self'"]
    assert d["object-src"] == ["'none'"] and d["frame-ancestors"] == ["'none'"]
    assert d["frame-src"] == ["https://www.youtube-nocookie.com", "https://player.vimeo.com",
                              "https://fast.wistia.net", "https://www.loom.com"]
    assert d["report-uri"] == ["/api/v1/security/csp-report"]
    assert "report-to" not in header and "Reporting-Endpoints" not in res.headers
    assert "*" not in header  # no wildcard while no tracker is configured
    assert "'unsafe-inline'" not in header and "'unsafe-eval'" not in header


def test_style_nonce_matches_the_page_meta_and_changes_per_request(client):
    first, second = client.get("/"), client.get("/")
    nonces = []
    for res in (first, second):
        style = _directives(_csp(res))["style-src"]
        nonce = next(s for s in style if s.startswith("'nonce-"))[7:-1]
        assert f'<meta name="csp-nonce" content="{nonce}">' in res.get_data(as_text=True)
        nonces.append(nonce)
    assert nonces[0] != nonces[1]


def test_tracker_origins_only_when_configured():
    plain = serialize_csp(build_csp({}))
    for host in ("googletagmanager", "licdn", "facebook"):
        assert host not in plain
    d = _directives(serialize_csp(build_csp({"ga4MeasurementId": "G-X1234", "metaPixelId": "123456789"})))
    assert "https://*.googletagmanager.com" in d["script-src"] and "https://connect.facebook.net" in d["script-src"]
    assert "https://*.google-analytics.com" in d["connect-src"] and "https://snap.licdn.com" not in d["script-src"]


def test_enforce_mode_switches_header_name(app, client):
    app.config["CSP_MODE"] = "enforce"
    res = client.get("/")
    assert res.headers.get("Content-Security-Policy") and _csp(res) is None


def test_hsts_only_in_production_mode_over_https(app, client):
    assert "Strict-Transport-Security" not in client.get("/", base_url="https://localhost").headers
    app.config["HSTS_ENABLED"] = True
    assert "Strict-Transport-Security" not in client.get("/").headers  # plain HTTP: never
    res = client.get("/", base_url="https://localhost")
    assert res.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    assert "preload" not in res.headers["Strict-Transport-Security"]


def test_production_config_enables_hsts_and_report_only_by_default():
    from config import Config, ProductionConfig

    assert ProductionConfig.HSTS_ENABLED is True and Config.HSTS_ENABLED is False
    assert Config.CSP_MODE == os.environ.get("CSP_MODE", "report-only").strip().lower()


def test_csp_reports_are_aggregated_without_identifying_detail(client, app):
    legacy = {"csp-report": {"document-uri": "https://wsf.example/account?email=a@b.c#x",
                             "violated-directive": "style-src-elem", "effective-directive": "style-src-elem",
                             "blocked-uri": "inline"}}
    for _ in range(2):
        assert client.post("/api/v1/security/csp-report", data=json.dumps(legacy),
                           content_type="application/csp-report").status_code == 204
    modern = [{"type": "csp-violation", "body": {"documentURL": "https://wsf.example/articles/x?utm=1",
                                                  "effectiveDirective": "img-src",
                                                  "blockedURL": "https://tracker.example/p.gif?id=123"}},
              {"type": "deprecation", "body": {}}]
    assert client.post("/api/v1/security/csp-report", data=json.dumps(modern),
                       content_type="application/reports+json").status_code == 204
    assert client.post("/api/v1/security/csp-report", data="not json").status_code == 204
    with app.app_context():
        rows = {(r.directive, r.blocked, r.page_path): r.count for r in CspViolation.query.all()}
    assert rows == {("style-src-elem", "inline", "/account"): 2,
                    ("img-src", "https://tracker.example", "/articles/x"): 1}


def test_summary_command(client, app):
    with app.app_context():
        db.session.add(CspViolation(directive="script-src", blocked="https://x.example", page_path="/", count=3))
        db.session.commit()
    out = app.test_cli_runner().invoke(args=["csp-report-summary", "--days", "7"]).output
    assert "CSP mode: report-only" in out and "https://x.example" in out


def test_every_server_rendered_style_element_carries_the_page_nonce(client):
    import re

    res = client.get("/")
    nonce = next(s for s in _directives(_csp(res))["style-src"] if s.startswith("'nonce-"))[7:-1]
    styles = re.findall(r"<style\b[^>]*>", res.get_data(as_text=True))
    assert styles, "the first-paint header reserve style is expected on /"
    assert all(f'nonce="{nonce}"' in tag for tag in styles)
