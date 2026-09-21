from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.opportunity import Event
from app.models.people import Organization, Person
from app.schemas.opportunity import EventInputSchema, EventSchema
from app.services.slugs import generate_unique_slug
from app.utils.filtering import apply_country_or_region_filter
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

events_bp = Blueprint("events", __name__)
api = Api(events_bp)

event_schema = EventSchema()


def _lookup_all(model, slugs, label):
    if not slugs:
        return []
    found = model.query.filter(model.slug.in_(slugs)).all()
    missing = set(slugs) - {item.slug for item in found}
    if missing:
        raise ApiError(f'{label.capitalize()} "{sorted(missing)[0]}" not found.', 404, code="not_found")
    return found


class EventListResource(Resource):
    def get(self):
        query = Event.query.filter_by(status="upcoming").order_by(Event.featured.desc(), Event.date)
        query = apply_country_or_region_filter(query, Event, request.args)
        event_format = request.args.get("format")
        if event_format:
            query = query.filter(Event.format == event_format)
        result = paginate(query, event_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("events.manage")
    def post(self):
        data = EventInputSchema().load(request.get_json(silent=True) or {})
        speakers = _lookup_all(Person, data.pop("speaker_slugs", []), "speaker")
        sponsors = _lookup_all(Organization, data.pop("sponsor_slugs", []), "sponsor")

        event = Event(**{k: v for k, v in data.items() if k != "slug"})
        event.slug = data.get("slug") or generate_unique_slug(Event, data["title"])
        event.speakers = speakers
        event.sponsors = sponsors
        db.session.add(event)
        db.session.commit()
        return success_response(event_schema.dump(event), status=201)


class EventDetailResource(Resource):
    def get(self, slug):
        event = Event.query.filter_by(slug=slug).first()
        if event is None:
            raise ApiError("Event not found.", 404, code="not_found")
        return success_response(event_schema.dump(event))


api.add_resource(EventListResource, "")
api.add_resource(EventDetailResource, "/<string:slug>")
