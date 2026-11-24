"""Aggregated Content-Security-Policy violation reports.

One row per distinct (directive, blocked origin, page path); repeats only
increase `count` and `last_seen`. Nothing identifying is kept: no IP, no
user agent, no query strings or fragments (the blocked URI is reduced to its
origin or keyword, the page to its path). Used to decide when the policy can
move from Report-Only to enforced (`flask csp-report-summary`).
"""
from app.extensions import db


class CspViolation(db.Model):
    __tablename__ = "csp_violations"
    __table_args__ = (
        db.UniqueConstraint("directive", "blocked", "page_path", name="uq_csp_violations_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    directive = db.Column(db.String(60), nullable=False)
    blocked = db.Column(db.String(200), nullable=False)
    page_path = db.Column(db.String(300), nullable=False)
    count = db.Column(db.Integer, nullable=False, default=1)
    first_seen = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    last_seen = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
