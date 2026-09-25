from marshmallow import fields, validate

from app.extensions import ma
from app.models.page import PAGE_STATUSES, PAGE_TYPES, Page
from app.schemas.media import MediaSchema


class _ReviewerSchema(ma.Schema):
    """Minimal, safe-to-expose identity — never the full User row (no
    email/roles), matching how other admin-only "who touched this" fields
    surface a user elsewhere in the CMS.
    """

    id = fields.Integer()
    full_name = fields.Method("get_full_name")

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class PageSchema(ma.SQLAlchemyAutoSchema):
    """Admin-only dump — every field, including internal notes, review/
    audit metadata, and raw status. See PagePublicSchema for what the
    public endpoint actually returns.
    """

    hero_media = fields.Nested(MediaSchema, dump_only=True)
    last_reviewed_by = fields.Nested(_ReviewerSchema, dump_only=True)
    updated_by = fields.Nested(_ReviewerSchema, dump_only=True)
    is_system = fields.Method("get_is_system")

    class Meta:
        model = Page
        load_instance = False

    def get_is_system(self, obj):
        return obj.is_system()


class PagePublicSchema(ma.Schema):
    """Only what a public visitor should ever see for a page — no
    internal_name, no status, no created_at/updated_by/last_reviewed_by,
    no revision history. `effective_date` is the explicit editor-set legal
    date (never a raw timestamp) for LegalPage's "Last updated" line.
    """

    key = fields.String()
    slug = fields.String()
    page_type = fields.String()
    title = fields.String()
    subtitle = fields.String(allow_none=True)
    content = fields.List(fields.Dict())
    hero_media = fields.Nested(MediaSchema, dump_only=True)
    seo = fields.Dict(allow_none=True)
    effective_date = fields.Date(allow_none=True)


class PageRevisionSchema(ma.Schema):
    id = fields.Integer()
    note = fields.String(allow_none=True)
    created_by = fields.Nested(_ReviewerSchema, dump_only=True)
    created_at = fields.DateTime()


class PageInputSchema(ma.Schema):
    """Create. `key`/`slug` are only meaningful for a general page — a
    system page's key/slug are fixed to one of SYSTEM_PAGE_KEYS and set by
    the route/seed, never taken from client input (see api/v1/pages.py).
    """

    key = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    page_type = fields.String(required=False, load_default="general", validate=validate.OneOf(PAGE_TYPES))
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    internal_name = fields.String(required=False, allow_none=True, data_key="internalName", validate=validate.Length(max=200))
    subtitle = fields.String(required=False, allow_none=True)
    content = fields.List(fields.Dict(), required=False, load_default=list)
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    seo = fields.Dict(required=False, allow_none=True)
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(PAGE_STATUSES))
    effective_date = fields.Date(required=False, allow_none=True, data_key="effectiveDate")


class PageUpdateSchema(ma.Schema):
    """Partial update — every field optional, no load_default, so a PATCH
    only ever touches what the client actually sent (house rule shared by
    every other CMS content type's update schema)."""

    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    title = fields.String(required=False, validate=validate.Length(min=1, max=200))
    internal_name = fields.String(required=False, allow_none=True, data_key="internalName", validate=validate.Length(max=200))
    subtitle = fields.String(required=False, allow_none=True)
    content = fields.List(fields.Dict(), required=False)
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    seo = fields.Dict(required=False, allow_none=True)
    effective_date = fields.Date(required=False, allow_none=True, data_key="effectiveDate")


class PageStatusUpdateSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(PAGE_STATUSES))


class PageReviewInputSchema(ma.Schema):
    note = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
