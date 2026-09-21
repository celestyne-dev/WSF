from marshmallow import fields

from app.extensions import ma
from app.models.media import Media, MediaVariant


class MediaVariantSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = MediaVariant
        load_instance = False


class MediaSchema(ma.SQLAlchemyAutoSchema):
    # Normalized by variant name (thumbnail/card/medium/large/hero) rather
    # than the raw list of MediaVariant rows, so a consumer can do
    # media.variants.card.url directly instead of searching an array —
    # this is the shape frontend/src/api/media.js's mapMedia() and every
    # image-rendering component key off of.
    variants = fields.Method("get_variants", dump_only=True)

    class Meta:
        model = Media
        load_instance = False

    def get_variants(self, obj):
        return {v.variant: {"url": v.public_url, "width": v.width, "height": v.height} for v in obj.variants}


class MediaUpdateSchema(ma.Schema):
    alt_text = fields.String(required=False, allow_none=True, data_key="altText")
    caption = fields.String(required=False, allow_none=True)
    credit = fields.String(required=False, allow_none=True)
    copyright_source = fields.String(required=False, allow_none=True, data_key="copyrightSource")
