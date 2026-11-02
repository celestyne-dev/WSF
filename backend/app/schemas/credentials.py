"""Profile credentials & qualifications (AI Search / GEO Phase 4B) — the
ordered, editor-entered credentials stored in Person.credentials and
Author.credentials:

    {"name": "...", "category": "...", "issuer": "...", "url": "...", "note": "..."}

`name` is required; everything else optional. `category` is free text
(Degree, Certification, Licence, Fellowship, ...) — deliberately not an
enum. An entry records that the profile STATES this credential; it is
never a claim that WSF (or the issuer) verified it, that it is current
or accredited. Plain text only (always rendered escaped); `url`, when
given, must be a public http(s) link — the same validate_public_http_url
rule sources use. Never fetched, never resolved.
"""
from marshmallow import EXCLUDE, ValidationError, fields, post_load, pre_load, validate

from app.extensions import ma
from app.schemas.sources import validate_public_http_url

MAX_CREDENTIALS = 30
_OPTIONAL = ("category", "issuer", "url", "note")


class CredentialSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=250))
    category = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    issuer = fields.String(required=False, allow_none=True, validate=validate.Length(max=250))
    url = fields.String(required=False, allow_none=True, validate=[validate.Length(max=2048), validate_public_http_url])
    note = fields.String(required=False, allow_none=True, validate=validate.Length(max=500))

    class Meta:
        unknown = EXCLUDE  # same policy as SourceSchema

    @pre_load
    def _trim(self, data, **kwargs):
        """Trim every string; a blank optional field counts as absent (so an
        empty URL box is never validated as a URL)."""
        if not isinstance(data, dict):
            return data
        out = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip()
                if not value and key in _OPTIONAL:
                    continue
            out[key] = value
        return out

    @post_load
    def _to_stored_shape(self, data, **kwargs):
        stored = {"name": data["name"]}
        for key in _OPTIONAL:
            if data.get(key):
                stored[key] = data[key]
        return stored


def credential_key(credential):
    """Duplicate identity: same name AND same issuer (case/space-insensitive)."""
    return (credential["name"].strip().lower(), (credential.get("issuer") or "").strip().lower())


def credentials_validator(noun):
    def _validate(credentials):
        if len(credentials) > MAX_CREDENTIALS:
            raise ValidationError(f"{noun} can list at most {MAX_CREDENTIALS} credentials.")
        seen = set()
        for credential in credentials:
            key = credential_key(credential)
            if key in seen:
                issuer = f' from "{credential["issuer"]}"' if credential.get("issuer") else ""
                raise ValidationError(f'The credential "{credential["name"]}"{issuer} is listed more than once.')
            seen.add(key)

    return _validate


def credentials_field(noun):
    """No load_default: an update payload that omits `credentials` leaves
    the stored list untouched; an explicit [] clears it."""
    return fields.List(fields.Nested(CredentialSchema), required=False, validate=credentials_validator(noun))
