import csv
import io
from datetime import date

from flask import Blueprint, Response, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.event_registration import EVENT_REGISTRATION_STATUSES, EventRegistration
from app.models.opportunity import Event, EventSpeaker, EventSponsor
from app.models.people import Organization, Person
from app.models.user import User
from app.schemas.opportunity import EventInputSchema, EventSchema
from app.services.audit import log_action
from app.services.content_blocks import sanitize_content_blocks
from app.services.event_registrations import (
    admin_update_registration_status,
    count_active_registrations,
    is_event_publicly_visible,
    public_event_access_fields,
    registration_availability,
    serialize_event_for_viewer,
)
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_country_or_region_filter, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

events_bp = Blueprint("events", __name__)
api = Api(events_bp)

event_schema = EventSchema()


def _dump_event_for_staff(event):
    """EventSchema always excludes virtual_link (see that schema's own
    Meta.exclude note) — every staff-authored dump (CMS create/update/
    detail-as-editor) re-attaches the raw value here, since a caller
    that already passed _require_manage()/the editor check is exactly
    who the admin editor needs to be able to read/edit it.
    """
    data = event_schema.dump(event)
    data["virtual_link"] = event.virtual_link
    return data


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _current_user_or_none():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    return current_user


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("events.manage"):
        raise ApiError("You do not have permission to manage events.", 403, code="forbidden")
    return user


def _can_edit_or_none():
    try:
        return _require_manage()
    except Exception:
        return None


def _resolve_organizer(organizer_id):
    if not organizer_id:
        return None
    org = db.session.get(Organization, organizer_id)
    if org is None:
        raise ApiError("Organization not found.", 404, code="not_found")
    return org


def _resolve_speakers(entries):
    """Build ordered EventSpeaker rows from the input list — each entry
    either links an existing Person (never duplicating their name/bio/
    headshot) or carries its own fallback fields for a speaker with no
    People profile yet.
    """
    speakers = []
    for position, entry in enumerate(entries):
        person = None
        if entry.get("person_slug"):
            person = Person.query.filter_by(slug=entry["person_slug"]).first()
            if person is None:
                raise ApiError(f'Person "{entry["person_slug"]}" not found.', 404, code="not_found")
        speakers.append(
            EventSpeaker(
                person=person,
                name=entry.get("name"),
                title=entry.get("title"),
                organization_name=entry.get("organization_name"),
                bio=entry.get("bio"),
                headshot_media_id=entry.get("headshot_media_id"),
                position=position,
            )
        )
    return speakers


def _resolve_sponsors(entries):
    """Build ordered EventSponsor rows — each entry either links an
    existing Organization or carries fallback name/logo/url for a sponsor
    with no Organization profile yet.
    """
    sponsors = []
    for position, entry in enumerate(entries):
        organization = None
        if entry.get("organization_id"):
            organization = db.session.get(Organization, entry["organization_id"])
            if organization is None:
                raise ApiError("Organization not found.", 404, code="not_found")
        sponsors.append(
            EventSponsor(
                organization=organization,
                name=entry.get("name"),
                logo_media_id=entry.get("logo_media_id"),
                url=entry.get("url"),
                tier=entry.get("tier"),
                position=position,
            )
        )
    return sponsors


def _apply_fields(event, data, organizer, speakers, sponsors):
    event.title = data["title"]
    event.short_description = data.get("short_description")
    event.description = sanitize_content_blocks(data.get("description", []))
    event.type = data.get("type")
    event.format = data.get("format")
    event.date = data["date"]
    event.end_date = data.get("end_date")
    event.start_time = data.get("start_time")
    event.end_time = data.get("end_time")
    event.timezone = data.get("timezone")
    event.location = data.get("location")
    event.address = data.get("address")
    event.city = data.get("city")
    event.country_code = data.get("country_code")
    event.venue = data.get("venue")
    event.virtual_link = data.get("virtual_link")
    event.virtual_link_public = data.get("virtual_link_public", False)
    event.access_type = data.get("access_type", "public")
    event.organizer = organizer
    event.organizer_name = data.get("organizer_name") or (organizer.name if organizer else event.organizer_name)
    event.registration_url = data.get("registration_url")
    event.registration_required = data.get("registration_required", True)
    event.registration_mode = data.get("registration_mode", "external")
    event.registration_deadline = data.get("registration_deadline")
    event.registration_instructions = data.get("registration_instructions")
    event.sold_out = data.get("sold_out", False)
    event.ticket_price = data.get("ticket_price")
    event.currency = data.get("currency")
    event.capacity = data.get("capacity")
    event.agenda = data.get("agenda", [])
    event.status = data.get("status", "published")
    event.seo = data.get("seo")
    event.cover_media_id = data.get("cover_media_id")
    event.featured = data.get("featured", False)
    event.sponsored = data.get("sponsored", False)
    event.speakers = speakers
    event.sponsors = sponsors
    if event.status in ("published", "scheduled") and event.published_date is None:
        event.published_date = data.get("published_date") or date.today()
    elif data.get("published_date"):
        event.published_date = data["published_date"]


def _validate_for_publish(event):
    """A published (or scheduled-to-publish) event needs a real
    description, and — when it actually requires registration — a real
    registration destination; a draft/review event may stay incomplete
    indefinitely.

    registration_required=False: no destination of any kind is needed.
    registration_mode=external: registration_url is required exactly as
    before this module existed (so an existing external event's publish
    behavior never silently changes). registration_mode=wsf: no URL is
    needed (WSF itself manages registration), but a WSF-managed event
    cannot (yet) be paid — see schemas/opportunity.py's
    EventInputSchema.validate_pricing for the same rule enforced at
    submit time too.

    circle_only additionally requires WSF-managed, required, free
    registration and a non-public virtual link (spec section C) — WSF
    cannot securely enforce Circle entitlement through an external
    registration platform, and a Circle-only joining link must never be
    intentionally public. A draft/review circle_only event may still
    carry an incomplete combination; only publishing/scheduling rejects
    it.

    A circle_only event whose format is virtual or hybrid additionally
    needs a real virtual_link before publishing (Module 10, part C) —
    WSF Circle is virtual-first (WSF operates from Kenya, its audience
    is global), so a Circle event promising online attendance must
    actually have a joining link behind it; an in-person circle_only
    event is never required to have one.
    """
    errors = []
    if not event.description:
        errors.append("Add an event description before publishing.")
    if event.registration_required:
        if event.registration_mode == "external" and not event.registration_url:
            errors.append("Add a registration URL before publishing — WSF never shows a fake Register button.")
        elif event.registration_mode == "wsf" and event.ticket_price:
            errors.append(
                "Paid WSF-managed event registration is not available yet. Use external registration for paid events."
            )
    if event.access_type == "circle_only":
        if not event.registration_required:
            errors.append("Circle-only events must require registration.")
        elif event.registration_mode != "wsf":
            errors.append("Circle-only events must use WSF-managed registration.")
        if event.virtual_link_public:
            errors.append("A Circle-only event cannot expose its virtual joining link publicly.")
        if event.format in ("virtual", "hybrid") and not event.virtual_link:
            errors.append("A virtual or hybrid Circle-only event needs a private joining link before publishing.")
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


class EventListResource(Resource):
    def get(self):
        user = _current_user_or_none()
        can_manage = bool(user and user.has_permission("events.manage"))

        query = Event.query.order_by(Event.featured.desc(), Event.date)
        today = date.today()
        if can_manage:
            if request.args.get("status"):
                query = query.filter(Event.status == request.args["status"])
        else:
            # A "scheduled" event is only publicly visible once its
            # published_date has actually arrived — mirrors Job's identical
            # scheduled-publish behavior.
            query = query.filter(
                or_(
                    Event.status.in_(["published", "cancelled", "postponed"]),
                    (Event.status == "scheduled") & (Event.published_date.isnot(None)) & (Event.published_date <= today),
                )
            )

        when = request.args.get("when")
        end_expr = db.func.coalesce(Event.end_date, Event.date)
        if when == "past":
            query = query.filter(end_expr < today)
        elif when == "upcoming" or (when is None and not can_manage):
            # Default public listing prioritizes what's actually upcoming;
            # CMS callers with no explicit `when` see everything so a
            # manager can still find/manage past events.
            query = query.filter(end_expr >= today)

        date_from = request.args.get("dateFrom")
        if date_from:
            query = query.filter(Event.date >= date_from)
        date_to = request.args.get("dateTo")
        if date_to:
            query = query.filter(Event.date <= date_to)

        query = apply_country_or_region_filter(query, Event, request.args)
        if request.args.get("city"):
            query = query.filter(Event.city.ilike(f"%{request.args['city']}%"))
        event_format = request.args.get("format")
        if event_format:
            query = query.filter(Event.format == event_format)
        event_type = request.args.get("type")
        if event_type:
            query = query.filter(Event.type == event_type)
        access_type = request.args.get("access_type")
        if access_type:
            query = query.filter(Event.access_type == access_type)
        if request.args.get("organizer"):
            query = query.filter(Event.organizer.has(slug=request.args["organizer"]))
        if request.args.get("featured") == "true":
            query = query.filter(Event.featured.is_(True))
        price = request.args.get("price")
        if price == "free":
            query = query.filter(or_(Event.ticket_price.is_(None), Event.ticket_price == 0))
        elif price == "paid":
            query = query.filter(Event.ticket_price.isnot(None), Event.ticket_price > 0)

        query = apply_search(query, Event, request.args, ["title", "short_description"], param="query")

        # Dumped manually (schema=None) rather than via paginate(query,
        # event_schema) so each item can still carry the safe
        # requiresCircle/viewerCanAccess UI hints (spec section N) —
        # public_event_access_fields() never queries EventRegistration,
        # so this stays the same one-query-per-page cost as before.
        result = paginate(query, schema=None)
        viewer = _current_user_or_none()
        items = [{**event_schema.dump(e), **public_event_access_fields(e, viewer)} for e in result["items"]]
        return success_response(items, meta=result["meta"])

    def post(self):
        _require_manage()
        data = EventInputSchema().load(request.get_json(silent=True) or {})
        organizer = _resolve_organizer(data.get("organizer_id"))
        speakers = _resolve_speakers(data.pop("speakers", []))
        sponsors = _resolve_sponsors(data.pop("sponsors", []))

        event = Event()
        if data.get("slug"):
            event.slug = validate_explicit_slug(Event, data["slug"])
        else:
            event.slug = generate_unique_slug(Event, data["title"])

        _apply_fields(event, data, organizer, speakers, sponsors)
        if event.status in ("published", "scheduled"):
            _validate_for_publish(event)
        db.session.add(event)
        db.session.commit()
        return success_response(_dump_event_for_staff(event), status=201)


class EventDetailResource(Resource):
    def get(self, slug):
        event = Event.query.filter_by(slug=slug).first()
        if event is None:
            raise ApiError("Event not found.", 404, code="not_found")
        editor = _can_edit_or_none()
        if not is_event_publicly_visible(event) and not editor:
            raise ApiError("Event not found.", 404, code="not_found")

        if editor:
            # Staff with events.manage get the raw field back (same
            # value they can edit in the CMS) rather than the
            # viewer-authorization logic below, which is about public
            # attendee access, not CMS access.
            data = _dump_event_for_staff(event)
        else:
            data = serialize_event_for_viewer(event, _current_user_or_none())
        data.update(registration_availability(event))
        return success_response(data)

    def put(self, slug):
        event = Event.query.filter_by(slug=slug).first()
        if event is None:
            raise ApiError("Event not found.", 404, code="not_found")
        _require_manage()

        data = EventInputSchema().load(request.get_json(silent=True) or {})
        organizer = _resolve_organizer(data.get("organizer_id"))
        speakers = _resolve_speakers(data.pop("speakers", []))
        sponsors = _resolve_sponsors(data.pop("sponsors", []))

        if data.get("slug") and data["slug"] != event.slug:
            event.slug = validate_explicit_slug(Event, data["slug"], current_id=event.id)

        _apply_fields(event, data, organizer, speakers, sponsors)
        if event.status in ("published", "scheduled"):
            _validate_for_publish(event)
        db.session.commit()
        return success_response(_dump_event_for_staff(event))

    def delete(self, slug):
        event = Event.query.filter_by(slug=slug).first()
        if event is None:
            raise ApiError("Event not found.", 404, code="not_found")
        _require_manage()

        db.session.delete(event)
        db.session.commit()
        return success_response({"deleted": True})


def _fetch_event_by_id_or_404(event_id):
    event = db.session.get(Event, event_id)
    if event is None:
        raise ApiError("Event not found.", 404, code="not_found")
    return event


def _fetch_event_registration_or_404(event_id, registration_id):
    """Scoped to `event_id` so a registration id that belongs to a
    DIFFERENT event can never be read or mutated through this event's
    own admin routes — the lookup itself fails closed (404) rather than
    trusting registration_id alone.
    """
    registration = EventRegistration.query.filter_by(id=registration_id, event_id=event_id).first()
    if registration is None:
        raise ApiError("Registration not found.", 404, code="not_found")
    return registration


def _dump_admin_registration(registration):
    user = registration.user
    return {
        "id": registration.id,
        "status": registration.status,
        "registered_at": registration.registered_at.isoformat() if registration.registered_at else None,
        "cancelled_at": registration.cancelled_at.isoformat() if registration.cancelled_at else None,
        "attended_at": registration.attended_at.isoformat() if registration.attended_at else None,
        "attendee_name": user.full_name if user else None,
        "attendee_email": user.email if user else None,
        "attendee_country": user.country.name if user and user.country else None,
    }


class EventRegistrationAdminListResource(Resource):
    def get(self, event_id):
        _require_manage()
        event = _fetch_event_by_id_or_404(event_id)

        query = EventRegistration.query.filter_by(event_id=event.id).join(EventRegistration.user)

        status_filter = request.args.get("status")
        if status_filter:
            query = query.filter(EventRegistration.status == status_filter)

        search_term = request.args.get("q")
        if search_term:
            like = f"%{search_term}%"
            query = query.filter(
                or_(User.first_name.ilike(like), User.last_name.ilike(like), User.email.ilike(like))
            )

        query = query.order_by(EventRegistration.registered_at.desc())
        result = paginate(query, schema=None)

        active_count = count_active_registrations(event.id)
        counts = {
            "registered": EventRegistration.query.filter_by(event_id=event.id, status="registered").count(),
            "attended": EventRegistration.query.filter_by(event_id=event.id, status="attended").count(),
            "cancelled": EventRegistration.query.filter_by(event_id=event.id, status="cancelled").count(),
        }
        items = [_dump_admin_registration(r) for r in result["items"]]
        # Pagination nested inside `data` (rather than passed via the
        # `meta=` kwarg) deliberately: the frontend apiClient's response
        # interceptor only promotes a top-level `meta` into {items,
        # pagination} when `data` itself is a bare array (see
        # frontend/src/api/client.js and app/api/v1/saved.py's identical
        # note) — here `data` carries the capacity/counts aggregates
        # alongside `items`, so nesting pagination inside it is what the
        # frontend can actually read back out.
        return success_response(
            {
                "items": items,
                "counts": counts,
                "active_count": active_count,
                "capacity": event.capacity,
                "available": None if event.capacity is None else max(0, event.capacity - active_count),
                "pagination": result["meta"],
            }
        )


class EventRegistrationAdminDetailResource(Resource):
    def patch(self, event_id, registration_id):
        _require_manage()
        _fetch_event_by_id_or_404(event_id)
        registration = _fetch_event_registration_or_404(event_id, registration_id)

        data = request.get_json(silent=True) or {}
        new_status = data.get("status")
        if new_status not in EVENT_REGISTRATION_STATUSES:
            raise ApiError("status must be one of: " + ", ".join(EVENT_REGISTRATION_STATUSES), 422, code="validation_error")

        old_status = registration.status
        registration, changed = admin_update_registration_status(registration, new_status)
        if changed:
            # Safe operational metadata only — never the attendee's name
            # or email (see task spec's AUDIT section).
            log_action(
                current_user,
                "event_registration.status_changed",
                "EventRegistration",
                registration.id,
                changes={"event_id": event_id, "status_from": old_status, "status_to": new_status},
            )
        return success_response(_dump_admin_registration(registration))


class EventRegistrationExportResource(Resource):
    def get(self, event_id):
        _require_manage()
        event = _fetch_event_by_id_or_404(event_id)
        registrations = (
            EventRegistration.query.filter_by(event_id=event.id)
            .join(EventRegistration.user)
            .order_by(EventRegistration.registered_at.asc())
            .all()
        )

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["name", "email", "country", "status", "registered_at", "attended_at", "cancelled_at"])
        for r in registrations:
            user = r.user
            writer.writerow(
                [
                    user.full_name if user else "",
                    user.email if user else "",
                    user.country.name if user and user.country else "",
                    r.status,
                    r.registered_at.isoformat() if r.registered_at else "",
                    r.attended_at.isoformat() if r.attended_at else "",
                    r.cancelled_at.isoformat() if r.cancelled_at else "",
                ]
            )

        log_action(
            current_user, "event_registration.export", "Event", event.id, changes={"count": len(registrations)}
        )
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=wsf-event-{event.slug}-registrations-{date.today().isoformat()}.csv"
        )
        return response


api.add_resource(EventListResource, "")
api.add_resource(EventDetailResource, "/<string:slug>")
api.add_resource(EventRegistrationAdminListResource, "/<int:event_id>/registrations")
api.add_resource(EventRegistrationAdminDetailResource, "/<int:event_id>/registrations/<int:registration_id>")
api.add_resource(EventRegistrationExportResource, "/<int:event_id>/registrations/export")
