from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.opportunity import Event
from app.models.people import Organization, Person
from app.schemas.opportunity import EventInputSchema, EventSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_country_or_region_filter
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

events_bp = Blueprint("events", __name__)
api = Api(events_bp)

event_schema = EventSchema()


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


def _lookup_all(model, slugs, label):
    if not slugs:
        return []
    found = model.query.filter(model.slug.in_(slugs)).all()
    missing = set(slugs) - {item.slug for item in found}
    if missing:
        raise ApiError(f'{label.capitalize()} "{sorted(missing)[0]}" not found.', 404, code="not_found")
    return found


def _resolve_organizer(organizer_id):
    if not organizer_id:
        return None
    org = db.session.get(Organization, organizer_id)
    if org is None:
        raise ApiError("Organization not found.", 404, code="not_found")
    return org


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
    event.country_code = data.get("country_code")
    event.venue = data.get("venue")
    event.virtual_link = data.get("virtual_link")
    event.virtual_link_public = data.get("virtual_link_public", False)
    event.organizer = organizer
    event.organizer_name = data.get("organizer_name") or (organizer.name if organizer else event.organizer_name)
    event.registration_url = data.get("registration_url")
    event.registration_required = data.get("registration_required", True)
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
    if event.status == "published" and event.published_date is None:
        event.published_date = data.get("published_date") or date.today()
    elif data.get("published_date"):
        event.published_date = data["published_date"]


def _validate_for_publish(event):
    """A published event needs a real description, and a real registration
    destination when it actually requires registration; a draft may stay
    incomplete indefinitely.
    """
    errors = []
    if not event.description:
        errors.append("Add an event description before publishing.")
    if event.registration_required and not event.registration_url:
        errors.append("Add a registration URL before publishing — WSF never shows a fake Register button.")
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


class EventListResource(Resource):
    def get(self):
        user = _current_user_or_none()
        can_manage = bool(user and user.has_permission("events.manage"))

        query = Event.query.order_by(Event.featured.desc(), Event.date)
        if can_manage:
            if request.args.get("status"):
                query = query.filter(Event.status == request.args["status"])
        else:
            query = query.filter(Event.status.in_(["published", "cancelled"]))

        when = request.args.get("when")
        today = date.today()
        end_expr = db.func.coalesce(Event.end_date, Event.date)
        if when == "past":
            query = query.filter(end_expr < today)
        elif when == "upcoming" or (when is None and not can_manage):
            # Default public listing prioritizes what's actually upcoming;
            # CMS callers with no explicit `when` see everything so a
            # manager can still find/manage past events.
            query = query.filter(end_expr >= today)

        query = apply_country_or_region_filter(query, Event, request.args)
        event_format = request.args.get("format")
        if event_format:
            query = query.filter(Event.format == event_format)
        event_type = request.args.get("type")
        if event_type:
            query = query.filter(Event.type == event_type)
        if request.args.get("organizer"):
            query = query.filter(Event.organizer.has(slug=request.args["organizer"]))
        if request.args.get("featured") == "true":
            query = query.filter(Event.featured.is_(True))
        result = paginate(query, event_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        _require_manage()
        data = EventInputSchema().load(request.get_json(silent=True) or {})
        organizer = _resolve_organizer(data.get("organizer_id"))
        speakers = _lookup_all(Person, data.pop("speaker_slugs", []), "speaker")
        sponsors = _lookup_all(Organization, data.pop("sponsor_slugs", []), "sponsor")

        event = Event()
        if data.get("slug"):
            event.slug = validate_explicit_slug(Event, data["slug"])
        else:
            event.slug = generate_unique_slug(Event, data["title"])

        _apply_fields(event, data, organizer, speakers, sponsors)
        if event.status == "published":
            _validate_for_publish(event)
        db.session.add(event)
        db.session.commit()
        return success_response(event_schema.dump(event), status=201)


class EventDetailResource(Resource):
    def get(self, slug):
        event = Event.query.filter_by(slug=slug).first()
        if event is None:
            raise ApiError("Event not found.", 404, code="not_found")
        if event.status not in ("published", "cancelled") and not _can_edit_or_none():
            raise ApiError("Event not found.", 404, code="not_found")
        return success_response(event_schema.dump(event))

    def put(self, slug):
        event = Event.query.filter_by(slug=slug).first()
        if event is None:
            raise ApiError("Event not found.", 404, code="not_found")
        _require_manage()

        data = EventInputSchema().load(request.get_json(silent=True) or {})
        organizer = _resolve_organizer(data.get("organizer_id"))
        speakers = _lookup_all(Person, data.pop("speaker_slugs", []), "speaker")
        sponsors = _lookup_all(Organization, data.pop("sponsor_slugs", []), "sponsor")

        if data.get("slug") and data["slug"] != event.slug:
            event.slug = validate_explicit_slug(Event, data["slug"], current_id=event.id)

        _apply_fields(event, data, organizer, speakers, sponsors)
        if event.status == "published":
            _validate_for_publish(event)
        db.session.commit()
        return success_response(event_schema.dump(event))

    def delete(self, slug):
        event = Event.query.filter_by(slug=slug).first()
        if event is None:
            raise ApiError("Event not found.", 404, code="not_found")
        _require_manage()

        db.session.delete(event)
        db.session.commit()
        return success_response({"deleted": True})


api.add_resource(EventListResource, "")
api.add_resource(EventDetailResource, "/<string:slug>")
