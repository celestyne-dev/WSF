from app.extensions import db


class TokenBlocklist(db.Model):
    """Revoked JWTs (logout), checked by the `token_in_blocklist_loader`
    callback in app/auth/jwt_callbacks.py. DB-backed rather than in-memory
    so revocation survives restarts and works across multiple app workers.
    """

    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    revoked_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
