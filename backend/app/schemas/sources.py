"""Editorial sources & references — the one shared source shape used by
Article.sources (AI Search / GEO Phase 3A) and Person.sources /
Author.sources (Phase 4A). Moved here verbatim from schemas/article.py so
all three validate identically; schemas/article.py re-exports the names
it always had (ArticleSourceSchema, MAX_ARTICLE_SOURCES, _validate_sources).

Plain text only — every field is rendered escaped, never as markup — and
the URL must be http(s). Never fetched or checked for reachability: an
editor can always save even if the cited site is temporarily down. A
source is context an editor chose to cite; nothing is ever inferred from
it, and it is never treated as identity verification.
"""
from marshmallow import EXCLUDE, ValidationError, fields, post_load, pre_load, validate

from app.extensions import ma

MAX_SOURCES = 50


class SourceSchema(ma.Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=300))
    url = fields.String(
        required=True,
        validate=[validate.Length(min=1, max=2048), validate.URL(schemes={"http", "https"}, require_tld=True)],
    )
    publisher = fields.String(required=False, allow_none=True, validate=validate.Length(max=250))
    author = fields.String(required=False, allow_none=True, validate=validate.Length(max=250))
    published_date = fields.Date(required=False, allow_none=True, data_key="publishedDate")
    note = fields.String(required=False, allow_none=True, validate=validate.Length(max=500))

    class Meta:
        unknown = EXCLUDE

    @pre_load
    def _trim(self, data, **kwargs):
        if not isinstance(data, dict):
            return data
        return {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items()}

    @post_load
    def _to_stored_shape(self, data, **kwargs):
        """The exact JSON stored in <entity>.sources and returned publicly:
        camelCase keys, empty optional fields dropped, date as YYYY-MM-DD."""
        stored = {"title": data["title"], "url": data["url"]}
        for key in ("publisher", "author", "note"):
            if data.get(key):
                stored[key] = data[key]
        if data.get("published_date"):
            stored["publishedDate"] = data["published_date"].isoformat()
        return stored


def sources_validator(noun):
    """List-level rules: at most MAX_SOURCES entries, no repeated URL
    (compared after the per-source trim). `noun` only words the message
    ("An article can list at most 50 sources.")."""

    def _validate(sources):
        if len(sources) > MAX_SOURCES:
            raise ValidationError(f"{noun} can list at most {MAX_SOURCES} sources.")
        seen = set()
        for source in sources:
            if source["url"] in seen:
                raise ValidationError(f'The source URL "{source["url"]}" is listed more than once.')
            seen.add(source["url"])

    return _validate


def sources_field(noun):
    """No load_default: an update payload that omits `sources` leaves the
    stored list untouched rather than silently wiping it; an explicit []
    clears it."""
    return fields.List(fields.Nested(SourceSchema), required=False, validate=sources_validator(noun))
