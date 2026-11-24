"""POST /api/v1/security/csp-report — browsers' CSP violation reports.

Accepts both formats browsers send: the legacy `report-uri` body
({"csp-report": {...}}, application/csp-report) and the Reporting API
(application/reports+json: a list of {"type": "csp-violation", "body": {...}}).
Reports are reduced to (directive, blocked origin/keyword, page path) and
counted (app/models/csp_violation.py). Always answers 204; malformed input is
ignored. Rate-limited per client.
"""
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import Blueprint, request
from sqlalchemy.dialects.postgresql import insert

from app.extensions import db, limiter
from app.models.csp_violation import CspViolation

security_bp = Blueprint("security", __name__)
MAX_BODY = 64 * 1024
MAX_REPORTS = 20


def _origin_or_keyword(value):
    value = (value or "").strip()
    if not value:
        return "(none)"
    if "://" not in value:
        return value.split(":")[0][:60]  # inline, eval, data, blob, self, ...
    parts = urlsplit(value)
    return f"{parts.scheme}://{parts.netloc}"[:200]


def _path_of(value):
    try:
        return (urlsplit(value or "").path or "/")[:300]
    except ValueError:
        return "/"


def _normalize(report):
    if not isinstance(report, dict):
        return None
    directive = report.get("effective-directive") or report.get("effectiveDirective") or report.get(
        "violated-directive") or report.get("violatedDirective") or ""
    directive = str(directive).split(" ")[0][:60]
    if not directive:
        return None
    blocked = _origin_or_keyword(report.get("blocked-uri") or report.get("blockedURL"))
    page = _path_of(report.get("document-uri") or report.get("documentURL"))
    return directive, blocked, page


def _reports(payload):
    if isinstance(payload, dict) and "csp-report" in payload:
        return [payload["csp-report"]]
    if isinstance(payload, list):
        return [item.get("body") for item in payload if isinstance(item, dict) and item.get("type") == "csp-violation"]
    return []


@security_bp.route("/csp-report", methods=["POST"])
@limiter.limit("60 per minute")
def csp_report():
    raw = request.get_data(cache=False, as_text=True)[:MAX_BODY]
    try:
        payload = json.loads(raw) if raw else None
    except ValueError:
        return "", 204
    now = datetime.now(timezone.utc)
    for report in _reports(payload)[:MAX_REPORTS]:
        key = _normalize(report)
        if key is None:
            continue
        directive, blocked, page = key
        stmt = insert(CspViolation).values(directive=directive, blocked=blocked, page_path=page, count=1,
                                           first_seen=now, last_seen=now)
        db.session.execute(stmt.on_conflict_do_update(
            constraint="uq_csp_violations_key",
            set_={"count": CspViolation.count + 1, "last_seen": now}))
    db.session.commit()
    return "", 204
