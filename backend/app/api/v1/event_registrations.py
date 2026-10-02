"""Self-service event registration for any active authenticated WSF
account — see app/services/event_registrations.py for the eligibility/
capacity/virtual-link-authorization rules this namespace enforces, and
app/models/event_registration.py for the data model. Every endpoint here
is implicitly scoped to current_user: there is no user_id parameter
anywhere, by design — a user must never be able to register or cancel
on another user's behalf, or read another user's registration state.
This is a WSF-account feature, not a CMS permission — it carries no
`events.manage`-style gate and is not gated by Community membership.
"""
from datetime import date

from flask import Blueprint, current_app, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required
from app.extensions import db
from app.models.event_registration import EventRegistration
from app.models.opportunity import Event
from app.services.email import send_email
from app.services.event_registrations import (
    fetch_visible_event_or_404,
    register,
    self_cancel,
    serialize_event_for_viewer,
)
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

event_registrations_bp = Blueprint("event_registrations", __name__)
api = Api(event_registrations_bp)


def _dump_registration(registration, user):
    return {
        "id": registration.id,
        "status": registration.status,
        "registered_at": registration.registered_at.isoformat() if registration.registered_at else None,
        "cancelled_at": registration.cancelled_at.isoformat() if registration.cancelled_at else None,
        "attended_at": registration.attended_at.isoformat() if registration.attended_at else None,
        "event": serialize_event_for_viewer(registration.event, user),
    }


def _send_registration_confirmation_email(user, event):
    """Best-effort only — see app/services/email.py's own docstring on
    why send_email() never raises. A delivery failure here must never
    undo an already-committed registration (the caller sends this AFTER
    committing), and is logged with no event title/user content, just
    enough to find the failure operationally.
    """
    frontend_url = current_app.config["FRONTEND_URL"].rstrip("/")
    my_events_url = f"{frontend_url}/account/events"
    when = event.date.strftime("%A, %B %-d, %Y") if event.date else ""
    if event.start_time:
        when += f" at {event.start_time.strftime('%-I:%M %p')}"
    where = "Online" if event.format == "virtual" else (event.venue or event.location or "")
    if event.format == "hybrid" and where:
        where += " + Online"

    text_body = (
        f"You're registered for {event.title} with Women Shaping Futures.\n\n"
        f"When: {when}\n"
        f"Where: {where}\n\n"
        f"Manage your registration any time: {my_events_url}"
    )
    html_body = (
        f"<p>You're registered for <strong>{event.title}</strong> with Women Shaping Futures.</p>"
        f"<p><strong>When:</strong> {when}<br><strong>Where:</strong> {where}</p>"
        f'<p><a href="{my_events_url}">Manage your registration</a></p>'
    )
    if not send_email(to=user.email, subject=f"You're registered: {event.title}", text_body=text_body, html_body=html_body):
        current_app.logger.error(
            "Event registration confirmation email delivery failed for user_id=%s event_id=%s.", user.id, event.id
        )


class EventRegistrationListResource(Resource):
    @active_user_required
    def post(self):
        data = request.get_json(silent=True) or {}
        event_id = data.get("event_id")
        if not isinstance(event_id, int) or isinstance(event_id, bool) or event_id <= 0:
            raise ApiError("event_id must be a positive integer.", 422, code="validation_error")

        event = fetch_visible_event_or_404(event_id)
        registration, created = register(event, current_user)

        if created:
            _send_registration_confirmation_email(current_user, event)

        return success_response({"registration": _dump_registration(registration, current_user), "registered": True})


class EventRegistrationCheckResource(Resource):
    @active_user_required
    def get(self):
        event_id = request.args.get("event_id", type=int)
        if not event_id or event_id <= 0:
            return success_response({"registered": False, "registration": None})

        registration = EventRegistration.query.filter_by(event_id=event_id, user_id=current_user.id).first()
        if registration is None or registration.status not in ("registered", "attended"):
            return success_response({"registered": False, "registration": None})
        return success_response({"registered": True, "registration": _dump_registration(registration, current_user)})


class EventRegistrationMeResource(Resource):
    @active_user_required
    def get(self):
        query = EventRegistration.query.filter_by(user_id=current_user.id).join(EventRegistration.event)

        status_filter = request.args.get("status")
        if status_filter:
            query = query.filter(EventRegistration.status == status_filter)
        else:
            # No explicit status filter: default to the user's ACTIVE
            # registrations (registered/attended) — this is what makes
            # /account/events' Upcoming and Past tabs clean, non-
            # overlapping groups distinct from its own Cancelled tab
            # (?status=cancelled), rather than a cancelled-but-still-
            # upcoming row appearing in both places.
            query = query.filter(EventRegistration.status.in_(("registered", "attended")))

        when = request.args.get("when")
        end_expr = db.func.coalesce(Event.end_date, Event.date)
        today = date.today()
        is_past = end_expr < today
        if when == "upcoming":
            query = query.filter(end_expr >= today).order_by(Event.date.asc())
        elif when == "past":
            query = query.filter(is_past).order_by(Event.date.desc())
        else:
            # Deterministic default with no `when` filter: every upcoming
            # registration first (soonest event first), then every past
            # one (most recently ended first) — never events interleaved
            # by raw date alone, which would bury "happening tomorrow"
            # under "happened five years ago".
            query = query.order_by(is_past.asc(), db.case((is_past, Event.date), else_=None).desc(), Event.date.asc())

        result = paginate(query, schema=None)
        items = [_dump_registration(r, current_user) for r in result["items"]]
        return success_response(items, meta=result["meta"])


class EventRegistrationCancelResource(Resource):
    @active_user_required
    def post(self, registration_id):
        registration = db.session.get(EventRegistration, registration_id)
        if registration is None:
            raise ApiError("Registration not found.", 404, code="not_found")
        if registration.user_id != current_user.id:
            # Same safe not-found treatment as every other owner-scoped
            # lookup in this app — never confirm that a registration id
            # belonging to someone else exists.
            raise ApiError("Registration not found.", 404, code="not_found")

        registration = self_cancel(registration, current_user)
        return success_response({"registration": _dump_registration(registration, current_user)})


api.add_resource(EventRegistrationListResource, "")
api.add_resource(EventRegistrationCheckResource, "/check")
api.add_resource(EventRegistrationMeResource, "/me")
api.add_resource(EventRegistrationCancelResource, "/<int:registration_id>/cancel")
