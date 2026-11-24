"""Rate-limit counters: the DATABASE FALLBACK store for the limiter.

Normal operation keeps rate-limit counters in Redis (shared by every
Gunicorn worker). Only when Redis is unavailable does the limiter write
here instead (app/services/rate_limit_storage.py), so limits keep working
across processes; it never falls back to per-process memory. A row holds a
fixed-window counter: the limiter's own key (scope + client IP, no other
data), the hit count and when the window ends. Expired rows are removed
opportunistically.
"""
from app.extensions import db


class RateLimitCounter(db.Model):
    __tablename__ = "rate_limit_counters"

    key = db.Column(db.String(255), primary_key=True)
    count = db.Column(db.Integer, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
