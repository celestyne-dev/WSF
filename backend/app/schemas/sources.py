"""Editorial sources & references — the one shared source shape used by
Article.sources (AI Search / GEO Phase 3A) and Person.sources /
Author.sources (Phase 4A). Moved here verbatim from schemas/article.py so
all three validate identically; schemas/article.py re-exports the names
it always had (ArticleSourceSchema, MAX_ARTICLE_SOURCES, _validate_sources).

Plain text only — every field is rendered escaped, never as markup — and
the URL must be http(s) on a public domain name (validate_public_host). Never fetched or checked for reachability: an
editor can always save even if the cited site is temporarily down. A
source is context an editor chose to cite; nothing is ever inferred from
it, and it is never treated as identity verification.
"""
import ipaddress
from urllib.parse import urlsplit

from marshmallow import EXCLUDE, ValidationError, fields, post_load, pre_load, validate

from app.extensions import ma

MAX_SOURCES = 50


PUBLIC_HOST_ERROR = "Source URL must use a public domain name."


def validate_public_host(url):
    """A cited source must live on a normal public domain name. marshmallow's
    URL validator (require_tld=True) still lets through `localhost` and IP
    literals, so the parsed hostname is checked here as well: no localhost
    (or *.localhost), no single-label host ("intranet"), no IPv4/IPv6
    literal, and a top-level label that isn't all digits. Purely syntactic —
    never a DNS lookup or fetch, never proof the domain is registered."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        raise ValidationError(PUBLIC_HOST_ERROR)
    if not host:
        return  # malformed URL: validate.URL already reports it
    host = host.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValidationError(PUBLIC_HOST_ERROR)
    labels = host.split(".")
    if host == "localhost" or host.endswith(".localhost") or len(labels) < 2 or labels[-1].isdigit():
        raise ValidationError(PUBLIC_HOST_ERROR)


_HTTP_URL = validate.URL(schemes={"http", "https"}, require_tld=True)


def _validate_source_url(url):
    """The public-host check, then the normal http(s) URL check — chained
    so a bad URL reports exactly one message. Host first so a non-public
    host ("intranet", "localhost", an IP) always gets the clear public-
    domain message; a URL with no parseable host (javascript:, data:,
    garbage) falls through to the URL check's own error."""
    validate_public_host(url)
    _HTTP_URL(url)


class SourceSchema(ma.Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=300))
    url = fields.String(
        required=True,
        validate=[validate.Length(min=1, max=2048), _validate_source_url],
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
