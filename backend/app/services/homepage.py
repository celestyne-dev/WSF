import re

from marshmallow import ValidationError

from app.models.article import Article
from app.models.cms import HOMEPAGE_MODULE_ITEM_COUNT_BOUNDS, HOMEPAGE_SINGLETON_TYPES
from app.models.people import Organization, Person
from app.models.taxonomy import Series, Topic

# A CTA URL is either an internal route (starts with "/", never validated
# against the exact set of live routes — that would recreate a routing
# table here — just shape-checked so it can't be blank/whitespace) or a
# safe external http(s) link. Anything else (javascript:, data:, bare
# "example.com", ...) is rejected before it ever reaches a rendered <a>.
_EXTERNAL_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def validate_cta_url(url, field_name="cta_url"):
    if url is None or url == "":
        return
    if url.startswith("/"):
        if len(url) > 1 and url[1] == "/":  # "//evil.com" is scheme-relative, not internal
            raise ValidationError("Internal links must be a real path, not \"//\".", field_name=field_name)
        return
    if _EXTERNAL_URL_RE.match(url):
        return
    raise ValidationError(
        "Links must be an internal path starting with \"/\" or a full https:// URL.", field_name=field_name
    )


def validate_item_count(module_type, item_count, field_name="config"):
    bounds = HOMEPAGE_MODULE_ITEM_COUNT_BOUNDS.get(module_type)
    if bounds is None or item_count is None:
        return
    lo, hi = bounds
    if not (lo <= item_count <= hi):
        raise ValidationError(
            f"{module_type} supports between {lo} and {hi} items.", field_name=field_name
        )


def validate_no_duplicate_singletons(modules_data):
    seen = set()
    for m in modules_data:
        if m["type"] in HOMEPAGE_SINGLETON_TYPES:
            if m["type"] in seen:
                raise ValidationError(f'Only one "{m["type"]}" module is allowed on the homepage.', field_name="type")
            seen.add(m["type"])


def _slug_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [s for s in value if s]


def compute_module_warnings(module):
    """Non-blocking configuration warnings shown in the admin builder —
    never raised as errors, since content naturally drifts (an Article
    that was Published when selected can later go back to Draft) and a
    stale reference shouldn't block unrelated homepage edits from saving.
    """
    warnings = []
    config = module.config or {}
    mtype = module.type

    def _article_missing(slug):
        return Article.query.filter_by(slug=slug, status="published").first() is None

    if mtype == "hero":
        lead = config.get("leadArticleSlug")
        if lead and _article_missing(lead):
            warnings.append(f'Lead article "{lead}" is no longer published.')
        for slug in _slug_list(config.get("secondaryArticleSlugs")):
            if _article_missing(slug):
                warnings.append(f'Secondary article "{slug}" is no longer published.')
        if not lead and not module.cta_label and not module.heading:
            warnings.append("Hero has no lead article and no manual headline — it will render empty.")

    elif mtype == "featured_stories":
        slugs = _slug_list(config.get("articleSlugs"))
        if not slugs:
            warnings.append("No articles selected yet.")
        for slug in slugs:
            if _article_missing(slug):
                warnings.append(f'Article "{slug}" is no longer published.')

    elif mtype == "featured_woman":
        slug = config.get("personSlug")
        if not slug:
            warnings.append("No person selected yet.")
        elif Person.query.filter_by(slug=slug, status="published").first() is None:
            warnings.append(f'Person "{slug}" is no longer published.')

    elif mtype == "series_feature":
        slug = config.get("seriesSlug")
        if not slug:
            warnings.append("No series selected yet.")
        elif Series.query.filter_by(slug=slug, status="published").first() is None:
            warnings.append(f'Series "{slug}" is no longer published.')

    elif mtype == "topic_collection":
        slug = config.get("topicSlug")
        if not slug:
            warnings.append("No topic selected yet.")
        elif Topic.query.filter_by(slug=slug, status="published").first() is None:
            warnings.append(f'Topic "{slug}" is no longer published.')

    elif mtype == "partners":
        slugs = _slug_list(config.get("partnerSlugs"))
        if not slugs:
            warnings.append("No partner organizations selected yet.")
        for slug in slugs:
            if Organization.query.filter_by(slug=slug, status="published").first() is None:
                warnings.append(f'Organization "{slug}" is no longer published.')

    elif mtype in ("community_cta", "mentorship_cta", "editorial_callout"):
        if not module.heading:
            warnings.append("No heading set yet.")
        if not module.cta_url:
            warnings.append("No call-to-action link set yet.")

    return warnings


def modules_with_warnings(modules):
    return {m.id: compute_module_warnings(m) for m in modules}
