from app.extensions import db


class AuditLog(db.Model):
    """An append-only trail of who did what. Written via
    app/services/audit.py, never edited or deleted through the API.
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)  # e.g. "article.publish"
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100), nullable=True)
    changes = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User")
