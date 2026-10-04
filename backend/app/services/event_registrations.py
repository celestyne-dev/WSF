"""First-party WSF-managed event registration — the actual eligibility,
capacity, and private-virtual-link-authorization logic behind
app/api/v1/event_registrations.py (self-service) and the
registration-management endpoints added to app/api/v1/events.py (staff).

Reuses Event's own existing public-visibility rule (see
is_event_publicly_visible below, copied verbatim from
EventDetailResource.get in app/api/v1/events.py — the one authoritative
definition of "can an anonymous visitor see this event") rather than
inventing a second one: a draft/review/archived event is never a valid
registration target, exactly as it's never a valid Saved-Item target.

CAPACITY / RACE SAFETY: registering (or restoring a cancelled
registration to active) always re-reads the Event row with
`SELECT ... FOR UPDATE` first (see register() and
admin_update_registration_status() below), so two concurrent requests
for the last available place serialize on that row lock rather than both
reading a stale count and both succeeding — the second request's count
query runs only after the first's transaction has committed (or rolled
back), so it always sees the up-to-date count. The table's own
UniqueConstraint(event_id, user_id) is kept as a second, independent
safety net against ever creating two rows for the same person.
"""
from datetime import date, datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.event_registration import EVENT_REGISTRATION_STATUSES, EventRegistration
from app.models.opportunity import Event
from app.schemas.opportunity import EventSchema
from app.services.event_access import can_access_event
from app.utils.responses import ApiError

_event_schema = EventSchema()

# Statuses that occupy a seat against Event.capacity — see module
# docstring's CAPACITY note and the task spec's own "Statuses consuming
# capacity: registered, attended" rule. "cancelled" never counts.
_CAPACITY_CONSUMING_STATUSES = ("registered", "attended")


def is_event_publicly_visible(event):
    """The exact same rule EventDetailResource.get() uses to decide
    whether an anonymous visitor may see this event at all — copied
    here (not imported from app/api/v1/events.py) to avoid a service ->
    api backward dependency; kept in sync by hand, the same convention
    already used for every other content type's visibility predicate in
    this codebase (see app/services/saved_items.py).
    """
    return event.status in ("published", "cancelled", "postponed") or (
        event.status == "scheduled" and event.published_date is not None and event.published_date <= date.today()
    )


def fetch_visible_event_or_404(event_id):
    event = db.session.get(Event, event_id)
    if event is None or not is_event_publicly_visible(event):
        raise ApiError("Event not found.", 404, code="not_found")
    return event


def count_active_registrations(event_id):
    return EventRegistration.query.filter(
        EventRegistration.event_id == event_id,
        EventRegistration.status.in_(_CAPACITY_CONSUMING_STATUSES),
    ).count()


def registration_availability(event):
    """Safe, aggregate-only state for the public detail page's CTA — no
    attendee names/emails/counts of who, just whether a seat remains.
    Deliberately NOT part of EventSchema (so it never runs on a public
    event LIST page, which would mean one count query per card) — call
    this only for a single event on its own detail view.
    """
    full = None
    if event.registration_mode == "wsf" and event.capacity is not None:
        full = count_active_registrations(event.id) >= event.capacity
    return {
        "registration_full": full,
        "registration_available": True if full is None else not full,
    }


def public_event_access_fields(event, user):
    """The same requiresCircle/viewerCanAccess UI hints
    serialize_event_for_viewer() adds, WITHOUT that function's
    virtual_link/registration-row lookup — safe to call once per item on
    the public Event LIST page (same no-N+1-query discipline
    registration_availability's own docstring describes) since
    can_access_event() never queries EventRegistration.
    """
    return {
        "requiresCircle": event.access_type == "circle_only",
        "viewerCanAccess": can_access_event(event, user),
    }


def is_authorized_for_virtual_link(event, user):
    """True iff `user` may be shown event.virtual_link right now.

    - Always true for staff with events.manage (CMS/admin access).
    - circle_only: virtual_link_public is NEVER consulted — a Circle-only
      joining link must never be intentionally public (spec section C),
      and a historical/bad row with virtual_link_public == True must
      still not leak it anonymously (spec section D, a security
      boundary, not just a publish-time validation). Requires BOTH
      can_access_event() (current Circle entitlement) AND an ACTIVE
      (registered or attended) registration for this exact event.
    - public (unchanged): true when the organizer marked it public;
      otherwise only true for a user with an ACTIVE (registered or
      attended) WSF-managed registration for this exact event — never
      merely because they're logged in, never because the event happens
      to use external registration (WSF never issued or tracked that
      attendee's registration, so it has no basis to call them
      authorized), and never for a cancelled registrant.
    """
    if user and user.has_permission("events.manage"):
        return True
    if event.access_type == "circle_only":
        if not user or not can_access_event(event, user):
            return False
        registration = EventRegistration.query.filter_by(event_id=event.id, user_id=user.id).first()
        return bool(registration and registration.status in ("registered", "attended"))
    if event.virtual_link_public:
        return True
    if not user:
        return False
    registration = EventRegistration.query.filter_by(event_id=event.id, user_id=user.id).first()
    return bool(registration and registration.status in ("registered", "attended"))


def serialize_event_for_viewer(event, user):
    """The same safe public Event representation EventSchema always
    produces (virtual_link excluded unconditionally — see that schema's
    own Meta.exclude note), with the private virtual_link re-attached
    only when `user` is actually authorized for it right now. Also
    carries the UI-guidance-only requiresCircle/viewerCanAccess hints
    (spec section N) — never authoritative themselves; backend
    registration and virtual-link authorization remain the real gate.
    """
    data = _event_schema.dump(event)
    data["virtual_link"] = event.virtual_link if is_authorized_for_virtual_link(event, user) else None
    data["requiresCircle"] = event.access_type == "circle_only"
    data["viewerCanAccess"] = can_access_event(event, user)
    return data


def _check_registration_window(event):
    """Raises ApiError with a specific reason the moment any requirement
    for *starting or resuming* a WSF-managed registration isn't met.
    Called with a freshly re-read (and, from register(), row-locked)
    Event so every check reflects the current committed state.
    """
    if not event.registration_required:
        raise ApiError("This event does not require registration.", 422, code="registration_not_required")
    if event.registration_mode != "wsf":
        raise ApiError(
            "This event uses external registration — WSF does not manage registration for it.",
            422,
            code="external_registration",
        )
    if event.status == "cancelled":
        raise ApiError("This event has been cancelled.", 409, code="event_cancelled")
    if event.status == "postponed":
        raise ApiError("This event has been postponed — registration is not open yet.", 409, code="event_postponed")
    end = event.end_date or event.date
    if end and end < date.today():
        raise ApiError("This event has already taken place.", 409, code="event_past")
    if event.registration_deadline and event.registration_deadline < date.today():
        raise ApiError("The registration deadline for this event has passed.", 409, code="registration_closed")
    if event.sold_out:
        raise ApiError("This event is sold out.", 409, code="sold_out")


def register(event, user):
    """Creates a new registration, or reactivates the user's own
    cancelled one — never a second row (see UniqueConstraint(event_id,
    user_id)). Returns (registration, created) where `created` is False
    for an idempotent repeat call while already actively registered (no
    email should be sent for that case — see the resource).

    circle_only additionally requires can_access_event() (the one
    central Event access-tier rule, see app/services/event_access.py)
    BEFORE touching any existing registration row or consuming capacity
    — denied access creates/reactivates nothing and never counts toward
    capacity, matching public's own "no partial side effects on
    rejection" behavior.
    """
    locked_event = Event.query.with_for_update().filter_by(id=event.id).one()
    _check_registration_window(locked_event)
    if locked_event.access_type == "circle_only" and not can_access_event(locked_event, user):
        raise ApiError(
            "Active WSF Circle membership is required to register for this event.", 403, code="circle_required"
        )

    existing = EventRegistration.query.filter_by(event_id=locked_event.id, user_id=user.id).first()
    if existing and existing.status in ("registered", "attended"):
        return existing, False

    if locked_event.capacity is not None and count_active_registrations(locked_event.id) >= locked_event.capacity:
        raise ApiError("This event is full.", 409, code="capacity_full")

    now = datetime.now(timezone.utc)
    if existing:
        existing.status = "registered"
        existing.cancelled_at = None
        existing.attended_at = None
        existing.registered_at = now
        registration = existing
    else:
        registration = EventRegistration(event_id=locked_event.id, user_id=user.id, status="registered", registered_at=now)
        db.session.add(registration)

    try:
        db.session.commit()
    except IntegrityError:
        # Lost a true photo-finish race at the database layer despite the
        # row lock above (e.g. this was the very first registration and
        # another request's INSERT committed in between) — the row that
        # won is just as valid a "you're registered" outcome.
        db.session.rollback()
        winner = EventRegistration.query.filter_by(event_id=locked_event.id, user_id=user.id).first()
        return winner, False
    return registration, True


def self_cancel(registration, user):
    """Idempotent: already-cancelled is returned as-is. Only the
    registration's own owner may call this (checked by the caller before
    reaching here is also fine, but enforced here too so this function is
    safe on its own).
    """
    if registration.user_id != user.id:
        raise ApiError("You do not have permission to cancel this registration.", 403, code="forbidden")
    if registration.status == "cancelled":
        return registration

    event = registration.event
    end = event.end_date or event.date
    if end and end < date.today():
        raise ApiError("This event has already taken place and can no longer be cancelled.", 409, code="event_past")

    registration.status = "cancelled"
    registration.cancelled_at = datetime.now(timezone.utc)
    db.session.commit()
    return registration


def admin_update_registration_status(registration, new_status):
    """Staff-only status transition (see app/api/v1/events.py's PATCH
    registrations endpoint, which is the only caller and handles its own
    permission check + audit logging). Idempotent when `new_status`
    already matches. Restoring a cancelled registration to "registered"
    re-checks capacity under the same row-lock strategy as register().
    Marking "attended" directly from "cancelled" is rejected — attendance
    applies to an active registration, not a resurrected one; restore it
    first.
    """
    if new_status not in EVENT_REGISTRATION_STATUSES:
        raise ApiError("Invalid status.", 422, code="invalid_status")

    old_status = registration.status
    if old_status == new_status:
        return registration, False

    now = datetime.now(timezone.utc)
    if new_status == "attended":
        if old_status == "cancelled":
            raise ApiError(
                "Restore the registration to registered before marking attendance.", 422, code="invalid_transition"
            )
        registration.status = "attended"
        registration.attended_at = now
    elif new_status == "registered":
        if old_status == "cancelled":
            locked_event = Event.query.with_for_update().filter_by(id=registration.event_id).one()
            if locked_event.capacity is not None and count_active_registrations(locked_event.id) >= locked_event.capacity:
                raise ApiError("Cannot restore — the event is at capacity.", 409, code="capacity_full")
            registration.cancelled_at = None
        registration.status = "registered"
        registration.attended_at = None
    elif new_status == "cancelled":
        registration.status = "cancelled"
        registration.cancelled_at = now

    db.session.commit()
    return registration, True
