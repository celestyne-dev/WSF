from app.extensions import db


class AnalyticsEvent(db.Model):
    """A generic event-ingestion sink for the frontend's trackEvent() calls
    (article_view, article_share_click, job_apply_click,
    opportunity_apply_click, event_registration_click,
    resource_download_click, ...) — see frontend/src/utils/analytics.js.
    `payload` holds whatever fields that specific event name carries;
    `acquisition` carries the same first-touch UTM/LinkedIn attribution
    blob used across the public forms in Phase 6.
    """

    __tablename__ = "analytics_events"

    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.String(100))
    payload = db.Column(db.JSON)
    acquisition = db.Column(db.JSON)
    session_id = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False, index=True)

    user = db.relationship("User", foreign_keys=[user_id])
