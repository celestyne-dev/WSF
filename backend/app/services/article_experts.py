"""Article provenance: Reviewed by / Fact checked by / Expert contribution.

Rows live in article_experts and always point at an existing Author or
Person. Publicly, a row is shown only while that profile is public (active
Author / published Person); otherwise it is silently left out, never shown
as a bare name. Nothing here infers a review: no row, no label.
"""
from marshmallow import ValidationError

from app.models.article import ARTICLE_EXPERT_ROLES, ArticleExpert
from app.models.people import Author, Person
from app.services.public_visibility import is_public_author, is_public_organization, is_public_person

ROLE_LABELS = {
    "reviewed_by": "Reviewed by",
    "fact_checked_by": "Fact checked by",
    "expert_contributor": "Expert contribution by",
}
MAX_EXPERTS = 8


def _media(media):
    if media is None:
        return None
    from app.schemas.media import MediaSchema

    data = MediaSchema().dump(media)
    for key in ("file_path", "stored_filename", "uploaded_by_id"):
        data.pop(key, None)
    return data


def _professional_line(profile, kind):
    """One short, real professional line: the profile's own role/title
    (and a published organization for People). Never invented."""
    if kind == "author":
        return profile.headline or profile.role or None
    org = profile.organization if is_public_organization(getattr(profile, "organization", None)) else None
    parts = [p for p in (profile.title, org.name if org else None) if p]
    return ", ".join(parts) or None


def _credentials(profile, limit=2):
    out = []
    for credential in profile.credentials or []:
        if isinstance(credential, dict) and credential.get("name"):
            out.append({"name": credential["name"], "issuer": credential.get("issuer") or None})
        if len(out) >= limit:
            break
    return out


def public_experts(article, with_credentials=True):
    """[{role, label, kind, slug, name, line, href, photo, credentials}] in
    editor order, public profiles only."""
    out = []
    for row in getattr(article, "experts", None) or []:
        if row.author_id is not None:
            profile, kind = row.author, "author"
            if not is_public_author(profile):
                continue
            href, photo = f"/authors/{profile.slug}", profile.photo if hasattr(profile, "photo") else None
        else:
            profile, kind = row.person, "person"
            if not is_public_person(profile):
                continue
            href, photo = f"/people/{profile.slug}", profile.photo
        entry = {
            "role": row.role, "label": ROLE_LABELS[row.role], "kind": kind, "slug": profile.slug,
            "name": profile.name, "line": _professional_line(profile, kind), "href": href, "photo": _media(photo),
        }
        if with_credentials:
            entry["credentials"] = _credentials(profile)
        out.append(entry)
    return out


def admin_experts(article):
    return [
        {"role": row.role, "authorSlug": row.author.slug if row.author else None,
         "personSlug": row.person.slug if row.person else None,
         "name": (row.author or row.person).name if (row.author or row.person) else None}
        for row in article.experts
    ]


def set_article_experts(article, entries):
    """Replace the Article's provenance rows from Studio input
    [{role, authorSlug | personSlug}]. Validates before changing anything."""
    if entries is None:
        return
    if not isinstance(entries, list):
        raise ValidationError("Experts must be a list.", field_name="experts")
    if len(entries) > MAX_EXPERTS:
        raise ValidationError(f"Add at most {MAX_EXPERTS} reviewers and experts.", field_name="experts")
    rows, seen = [], set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValidationError("Each expert must be an object.", field_name="experts")
        role = entry.get("role")
        if role not in ARTICLE_EXPERT_ROLES:
            raise ValidationError(f"Role must be one of: {', '.join(ARTICLE_EXPERT_ROLES)}.", field_name="experts")
        author_slug, person_slug = entry.get("authorSlug") or None, entry.get("personSlug") or None
        if bool(author_slug) == bool(person_slug):
            raise ValidationError("Pick exactly one Author or Person for each expert.", field_name="experts")
        if author_slug:
            profile = Author.query.filter_by(slug=author_slug).first()
            key = (role, "author", author_slug)
        else:
            profile = Person.query.filter_by(slug=person_slug).first()
            key = (role, "person", person_slug)
        if profile is None:
            raise ValidationError(f'"{author_slug or person_slug}" does not exist.', field_name="experts")
        if key in seen:
            raise ValidationError("The same profile is listed twice for one role.", field_name="experts")
        seen.add(key)
        rows.append(ArticleExpert(role=role, author_id=profile.id if author_slug else None,
                                  person_id=profile.id if person_slug else None, position=index))
    article.experts = rows
