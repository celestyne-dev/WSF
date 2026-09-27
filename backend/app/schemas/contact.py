from marshmallow import fields, validate

from app.extensions import ma
from app.models.contact import CONTACT_INQUIRY_TYPES, CONTACT_STATUSES, ContactInquiry, ContactNote
from app.schemas.user import UserSchema

_STAFF_ONLY = UserSchema(only=("id", "full_name", "email"))


class ContactNoteSchema(ma.SQLAlchemyAutoSchema):
    user = ma.Nested(_STAFF_ONLY, dump_only=True)

    class Meta:
        model = ContactNote
        load_instance = False
        exclude = ("inquiry_id", "user_id")


class ContactInquirySchema(ma.SQLAlchemyAutoSchema):
    """Full admin detail dump — internal notes and assignment included.
    Never used for the public create response (see ContactPage's
    write-only confirmation, built by hand in the route)."""

    full_name = fields.String(dump_only=True)
    assigned_to = ma.Nested(_STAFF_ONLY, dump_only=True)
    resolved_by = ma.Nested(_STAFF_ONLY, dump_only=True)
    notes = ma.Nested(ContactNoteSchema, many=True, dump_only=True)

    class Meta:
        model = ContactInquiry
        load_instance = False


class ContactInquiryListItemSchema(ma.SQLAlchemyAutoSchema):
    """Lighter list-row shape — no notes/message body, so the admin list
    endpoint never pulls full message text or internal notes for every row
    on a page."""

    full_name = fields.String(dump_only=True)
    assigned_to = ma.Nested(_STAFF_ONLY, dump_only=True)

    class Meta:
        model = ContactInquiry
        load_instance = False
        exclude = ("message", "privacy_acknowledged")


# ---------------------------------------------------------------------------
# Public submission input — never dumped back; the route builds its own
# small {reference, status} confirmation by hand.
# ---------------------------------------------------------------------------


class ContactInquiryInputSchema(ma.Schema):
    first_name = fields.String(required=True, validate=validate.Length(min=1, max=120), data_key="firstName")
    last_name = fields.String(required=True, validate=validate.Length(min=1, max=120), data_key="lastName")
    email = fields.Email(required=True)
    inquiry_type = fields.String(
        required=False, load_default="general", validate=validate.OneOf(CONTACT_INQUIRY_TYPES), data_key="inquiryType"
    )
    subject = fields.String(required=True, validate=validate.Length(min=1, max=200))
    message = fields.String(required=True, validate=validate.Length(min=10, max=5000))
    privacy_acknowledged = fields.Boolean(required=True, data_key="privacyAcknowledged")

    # Anti-spam signals — never persisted, never returned. See
    # app/api/v1/contact.py:ContactInquiryListResource.post for how these
    # are used (a filled honeypot or too-fast a submission is treated as
    # spam and silently dropped, not rejected with an error that would
    # tell a bot it was caught).
    hp_website = fields.String(required=False, allow_none=True, load_default="", data_key="hpWebsite")
    elapsed_ms = fields.Integer(required=False, allow_none=True, load_default=None, data_key="elapsedMs")


# ---------------------------------------------------------------------------
# Admin action schemas — every field required for its own narrow purpose,
# matching the Submission/Nomination house pattern.
# ---------------------------------------------------------------------------


class ContactStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(CONTACT_STATUSES))


class ContactAssignInputSchema(ma.Schema):
    user_id = fields.Integer(required=True, allow_none=True, data_key="userId")


class ContactNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1, max=4000))
