"""Contact & General Inquiries — a focused public-inquiry inbox, not a
support desk. Public visitors submit through POST (no auth), and
authorized staff review/assign/annotate/resolve through the rest of this
blueprint (see app/services/rbac.py:contact.manage).

Deliberately narrow: no reply/email-sending (see module docstring in
app/services/contact.py), no bulk actions, no CSV export, no delete route
(status/lifecycle management only — see CONTACT_STATUS_TRANSITIONS).
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db, limiter
from app.models.contact import ContactInquiry, ContactNote
from app.models.user import User
from app.schemas.contact import (
    ContactAssignInputSchema,
    ContactInquiryInputSchema,
    ContactInquiryListItemSchema,
    ContactInquirySchema,
    ContactNoteInputSchema,
    ContactStatusInputSchema,
)
from app.services.audit import log_action
from app.services.contact import generate_contact_reference, is_valid_contact_status_transition
from app.services.notifications import notify_contact_received
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

contact_bp = Blueprint("contact", __name__)
api = Api(contact_bp)

inquiry_schema = ContactInquirySchema()
inquiry_list_schema = ContactInquiryListItemSchema()

# A visitor who fills the honeypot, or submits faster than a human
# plausibly could read+fill the form, is silently treated as spam: no
# record is created and no error is returned, so a bot never learns it
# was caught (see task spec HONEYPOT: "do not expose anti-spam internals").
_MIN_HUMAN_SUBMIT_MS = 1500


def _looks_like_spam(data):
    if (data.get("hp_website") or "").strip():
        return True
    elapsed = data.get("elapsed_ms")
    if elapsed is not None and elapsed < _MIN_HUMAN_SUBMIT_MS:
        return True
    return False


def _find_recent_duplicate(email, subject, message):
    """Prevent an accidental double submission from repeated button
    clicks — an identical subject+message from the same email within a
    short window is treated as the same click, not a second inquiry.
    """
    window_start = datetime.now(timezone.utc) - timedelta(minutes=5)
    return ContactInquiry.query.filter(
        ContactInquiry.email == email,
        ContactInquiry.subject == subject,
        ContactInquiry.message == message,
        ContactInquiry.created_at >= window_start,
    ).first()


def _build_confirmation(inquiry):
    return {"reference": inquiry.reference, "status": "received"}


class ContactInquiryListResource(Resource):
    @permission_required("contact.manage")
    def get(self):
        query = ContactInquiry.query.order_by(ContactInquiry.created_at.desc())
        args = request.args
        query = apply_equality_filters(query, ContactInquiry, args, ["status", "inquiry_type"])
        if args.get("assigned_to_user_id"):
            query = query.filter(ContactInquiry.assigned_to_user_id == args["assigned_to_user_id"])
        if args.get("date_from"):
            query = query.filter(ContactInquiry.created_at >= args["date_from"])
        if args.get("date_to"):
            query = query.filter(ContactInquiry.created_at <= args["date_to"])
        query = apply_search(query, ContactInquiry, args, ["reference", "first_name", "last_name", "email", "subject"])
        result = paginate(query, inquiry_list_schema)
        return success_response(result["items"], meta=result["meta"])

    # Public, unauthenticated write endpoint — see task spec's RATE
    # LIMITING section. Conservative per-IP limit against scripted spam;
    # the honeypot/timing check below already catches obvious bots, this
    # is a backstop against a burst of genuinely form-shaped requests.
    @limiter.limit("5 per minute")
    def post(self):
        """The public submission endpoint — write-only besides a small
        {reference, status} confirmation. Never returns the inquiry's id,
        assignment, or any internal field (see PUBLIC RESPONSE in the
        task spec).
        """
        payload = request.get_json(silent=True) or {}
        data = ContactInquiryInputSchema().load(payload)

        if not data.pop("privacy_acknowledged"):
            raise ApiError("Please acknowledge the privacy notice before submitting.", 422, code="validation_error")

        if _looks_like_spam(data):
            # A believable-looking confirmation, but nothing is persisted.
            return success_response({"reference": "WSF-CON-0000-000000", "status": "received"}, status=201)

        data.pop("hp_website", None)
        data.pop("elapsed_ms", None)
        email = data["email"].strip().lower()
        data["email"] = email

        duplicate = _find_recent_duplicate(email, data["subject"], data["message"])
        if duplicate is not None:
            return success_response(_build_confirmation(duplicate), status=201)

        inquiry = ContactInquiry(**data, privacy_acknowledged=True, source="contact_page")
        db.session.add(inquiry)
        db.session.flush()
        inquiry.reference = generate_contact_reference(inquiry)
        db.session.commit()
        notify_contact_received(inquiry)

        log_action(None, "contact.received", "ContactInquiry", inquiry.id, {"reference": inquiry.reference})
        return success_response(_build_confirmation(inquiry), status=201)


class ContactInquiryDetailResource(Resource):
    @permission_required("contact.manage")
    def get(self, inquiry_id):
        inquiry = db.session.get(ContactInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Inquiry not found.", 404, code="not_found")
        return success_response(inquiry_schema.dump(inquiry))


class ContactStatusResource(Resource):
    @permission_required("contact.manage")
    def patch(self, inquiry_id):
        inquiry = db.session.get(ContactInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Inquiry not found.", 404, code="not_found")

        payload = request.get_json(silent=True) or {}
        data = ContactStatusInputSchema().load(payload)
        new_status = data["status"]

        if not is_valid_contact_status_transition(inquiry.status, new_status):
            raise ApiError(
                f"Cannot move an inquiry from '{inquiry.status}' to '{new_status}'.", 409, code="invalid_transition"
            )

        from_status = inquiry.status
        inquiry.status = new_status
        if new_status == "resolved":
            inquiry.resolved_at = datetime.now(timezone.utc)
            inquiry.resolved_by_user_id = current_user.id
        db.session.commit()

        log_action(
            current_user,
            "contact.status_changed",
            "ContactInquiry",
            inquiry.id,
            {"reference": inquiry.reference, "from_status": from_status, "to_status": new_status},
        )
        return success_response(inquiry_schema.dump(inquiry))


class ContactAssignResource(Resource):
    @permission_required("contact.manage")
    def post(self, inquiry_id):
        inquiry = db.session.get(ContactInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Inquiry not found.", 404, code="not_found")

        data = ContactAssignInputSchema().load(request.get_json(silent=True) or {})
        user_id = data["user_id"]
        if user_id is not None:
            assignee = db.session.get(User, user_id)
            if assignee is None:
                raise ApiError("That staff member could not be found.", 422, code="invalid_assignee")
            if not assignee.is_active:
                raise ApiError("That staff member's account is inactive.", 422, code="inactive_assignee")

        inquiry.assigned_to_user_id = user_id
        db.session.commit()
        log_action(
            current_user, "contact.assigned", "ContactInquiry", inquiry.id,
            {"reference": inquiry.reference, "assigned_user_id": user_id},
        )
        return success_response(inquiry_schema.dump(inquiry))


class ContactNoteListResource(Resource):
    @permission_required("contact.manage")
    def post(self, inquiry_id):
        inquiry = db.session.get(ContactInquiry, inquiry_id)
        if inquiry is None:
            raise ApiError("Inquiry not found.", 404, code="not_found")

        data = ContactNoteInputSchema().load(request.get_json(silent=True) or {})
        note = ContactNote(inquiry_id=inquiry.id, user_id=current_user.id, body=data["body"])
        db.session.add(note)
        db.session.commit()
        log_action(current_user, "contact.note_added", "ContactInquiry", inquiry.id, {"reference": inquiry.reference})
        return success_response(inquiry_schema.dump(inquiry), status=201)


api.add_resource(ContactInquiryListResource, "")
api.add_resource(ContactInquiryDetailResource, "/<int:inquiry_id>")
api.add_resource(ContactStatusResource, "/<int:inquiry_id>/status")
api.add_resource(ContactAssignResource, "/<int:inquiry_id>/assign")
api.add_resource(ContactNoteListResource, "/<int:inquiry_id>/notes")
