from flask import request

from app.extensions import db
from app.models.audit import AuditLog

# Centralized safety net (spec: "do not rely solely on every caller
# remembering to sanitize") — every log_action() caller already passes a
# small, deliberately narrow `changes` dict (a status transition, a
# renamed field, a role list — never a full record snapshot), and an
# audit of every existing call site found none of these sensitive keys in
# practice. This denylist exists so a future caller's mistake is caught
# here, once, rather than relying on 100+ call sites each remembering to
# scrub themselves. Matched case-insensitively against dict keys, at any
# nesting depth.
_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "passwordhash",
    "new_password",
    "old_password",
    "current_password",
    "temporary_password",
    "temp_password",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "token",
    "jwt",
    "secret",
    "secret_key",
    "secretkey",
    "jwt_secret_key",
    "api_key",
    "apikey",
    "api_secret",
    "client_secret",
    "smtp_password",
    "database_url",
    "database_password",
    "db_password",
    "credit_card",
    "card_number",
    "cvv",
    "cvc",
}

_REDACTED = "[redacted]"


def _redact(value):
    if isinstance(value, dict):
        return {
            k: (_REDACTED if isinstance(k, str) and k.lower().replace("-", "_") in _SENSITIVE_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


def log_action(user, action, entity_type, entity_id=None, changes=None):
    """Write one audit trail entry. `user` may be None for system actions."""
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        changes=_redact(changes) if changes is not None else None,
        ip_address=request.remote_addr if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )
    db.session.add(entry)
    db.session.commit()
    return entry
