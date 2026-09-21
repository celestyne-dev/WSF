from sqlalchemy import or_


def apply_equality_filters(query, model, args, fields):
    """Apply `?field=value` equality filters for each field present in args."""
    for field in fields:
        value = args.get(field)
        if value:
            query = query.filter(getattr(model, field) == value)
    return query


def apply_search(query, model, args, fields, param="q"):
    """Apply a case-insensitive `?q=...` search across the given text fields."""
    term = args.get(param)
    if not term:
        return query
    like = f"%{term}%"
    return query.filter(or_(*[getattr(model, field).ilike(like) for field in fields]))


def apply_country_or_region_filter(query, model, args, country_field="country_code"):
    """Standard global-geography filtering shared by every listing endpoint
    that carries a location (people, jobs, opportunities, events, ...):
    `?country=US`, `?region=Africa`, or `?remote=true` / the pseudo-values
    GLOBAL/REMOTE stored directly in country_field.
    """
    country = args.get("country")
    region = args.get("region")
    column = getattr(model, country_field)

    if country:
        query = query.filter(column == country.upper())
    if region:
        from app.services.geography import country_codes_for_region

        query = query.filter(column.in_(country_codes_for_region(region)))
    return query
