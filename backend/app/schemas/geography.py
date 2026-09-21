from app.extensions import ma
from app.models.geography import Country


class CountrySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Country
        load_instance = False
