from app.extensions import ma
from app.models.media import Media, MediaVariant


class MediaVariantSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = MediaVariant
        load_instance = False


class MediaSchema(ma.SQLAlchemyAutoSchema):
    variants = ma.Nested(MediaVariantSchema, many=True, dump_only=True)

    class Meta:
        model = Media
        load_instance = False
