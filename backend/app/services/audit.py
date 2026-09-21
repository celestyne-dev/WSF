from flask import request

from app.extensions import db
from app.models.audit import AuditLog


def log_action(user, action, entity_type, entity_id=None, changes=None):
    """Write one audit trail entry. `user` may be None for system actions."""
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        changes=changes,
        ip_address=request.remote_addr if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )
    db.session.add(entry)
    db.session.commit()
    return entry
