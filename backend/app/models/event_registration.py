"""First-party WSF-managed event registration (see app/services/
event_registrations.py). Only relevant for an Event whose
registration_mode == "wsf" — an externally-registered event never gets a
row here (see that module's own docstring for why).

One lifecycle row per (event, user): re-registering after cancelling
reactivates the SAME row rather than creating a new one, so a user's
attendance history for an event is never duplicated. On reactivation
this app refreshes `registered_at` to the moment of the new commitment
to attend (rather than preserving the original request time) — `status`
transitions and `updated_at` already capture the full history of what
happened and when, so `registered_at` staying meaningful as "when did
this become an active registration" is more useful here than a frozen
first-ever timestamp. See event_registrations.py's register() for where
that decision is implemented.
"""
from app.extensions import db

EVENT_REGISTRATION_STATUSES = ("registered", "cancelled", "attended")
_EVENT_REGISTRATION_STATUS_CHECK_SQL = (
    "status IN (" + ", ".join(f"'{s}'" for s in EVENT_REGISTRATION_STATUSES) + ")"
)


class EventRegistration(db.Model):
    __tablename__ = "event_registrations"
    __table_args__ = (
        db.CheckConstraint(_EVENT_REGISTRATION_STATUS_CHECK_SQL, name="ck_event_registrations_status"),
        # One lifecycle row per (event, user) — see module docstring.
        # Also the race-safety net behind the idempotent POST /register
        # (app/api/v1/event_registrations.py catches the resulting
        # IntegrityError rather than trusting the capacity check alone).
        db.UniqueConstraint("event_id", "user_id", name="uq_event_registrations_event_user"),
        # "This user's registrations" (GET /event-registrations/me,
        # optionally filtered by status) — a leftmost prefix covers both
        # the filtered and unfiltered case.
        db.Index("ix_event_registrations_user_status", "user_id", "status"),
        # "This event's attendees" (admin registrations list, capacity
        # counting) — same leftmost-prefix reasoning.
        db.Index("ix_event_registrations_event_status", "event_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="registered")
    registered_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    attended_at = db.Column(db.DateTime(timezone=True), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    event = db.relationship("Event", foreign_keys=[event_id])
    user = db.relationship("User", foreign_keys=[user_id])
