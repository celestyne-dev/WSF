from app.extensions import db
from app.models.geography import SEED_COUNTRIES, Country


def seed_countries():
    """Idempotently load/refresh the Country reference table. Safe to
    re-run — existing rows are updated in place rather than duplicated.
    """
    for code, name, region in SEED_COUNTRIES:
        country = db.session.get(Country, code)
        if country is None:
            country = Country(code=code)
            db.session.add(country)
        country.name = name
        country.region = region
    db.session.commit()


def country_codes_for_region(region):
    rows = Country.query.filter_by(region=region).all()
    return [c.code for c in rows]


def get_country_name(code):
    if not code:
        return None
    country = db.session.get(Country, code.upper())
    return country.name if country else code
