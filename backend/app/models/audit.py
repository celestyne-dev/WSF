from app.extensions import db


class AuditLog(db.Model):
    """An append-only trail of who did what. Written via
    app/services/audit.py, never edited or deleted through the API.

    Indexed on every column the Admin Audit Log actually filters/sorts by
    (app/api/v1/admin_audit.py) — this table has no other consumer that
    needs different access patterns, and it's expected to grow large
    (every log_action() call across the backend writes here), so an
    unindexed scan over created_at/actor/action/entity would get
    noticeably slower well before the table is "large" in absolute terms.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (db.Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)  # e.g. "article.publish"
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100), nullable=True)
    changes = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False, index=True)

    user = db.relationship("User")
