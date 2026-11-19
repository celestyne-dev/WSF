"""Post-event content for Events: a recording reference plus links to an
existing Resource, Article and Learning program. Everything is a
reference to content that already exists elsewhere in WSF; nothing is
copied or uploaded here.

`post_event_payload` is built for the Event DETAIL response only (never
list/card dumps), so linked rows are loaded for one event at a time and
event lists gain no extra queries.
"""
from app.models.article import Article
from app.models.learning import LearningProgram
from app.models.resource import Resource
from app.services.video_embed import VIDEO_PROVIDER_LABELS, resolve_video_provider, video_embed_url
from app.utils.responses import ApiError

_LINKS = (
    ("post_event_resource_slug", "post_event_resource_id", Resource, "Resource"),
    ("post_event_article_slug", "post_event_article_id", Article, "Article"),
    ("post_event_learning_program_slug", "post_event_learning_program_id", LearningProgram, "Learning program"),
)


def apply_post_event_fields(event, data):
    """Only keys present in `data` change (an omitted key keeps the saved
    value). Unknown slugs 404; an unsafe recording URL or a provider that
    contradicts the URL's host is a 422."""
    if "recording_url" in data or "recording_provider" in data:
        url = (data.get("recording_url", event.recording_url) or "").strip() or None
        requested = data.get("recording_provider", event.recording_provider) or None
        if url is None:
            event.recording_url, event.recording_provider = None, None
        else:
            try:
                event.recording_provider = resolve_video_provider(url, requested)
            except ValueError as exc:
                raise ApiError(f"Recording: {exc}", 422, code="invalid_url")
            event.recording_url = url
    for key, column, model, label in _LINKS:
        if key not in data:
            continue
        slug = (data[key] or "").strip()
        if not slug:
            setattr(event, column, None)
            continue
        row = model.query.filter_by(slug=slug).first()
        if row is None:
            raise ApiError(f'{label} "{slug}" not found.', 404, code="not_found")
        setattr(event, column, row.id)


def _public_resource(resource):
    return resource is not None and resource.is_publicly_visible()


def _public_article(article):
    return article is not None and article.status == "published"


def _public_program(program):
    return program is not None and program.status == "published"


def post_event_payload(event, staff=False, can_view_recording=True):
    """Public: only links whose targets are themselves public, or None
    when there is nothing to show (the page then renders no section).
    The recording follows the event's own access rule: for a Circle-only
    event a viewer without access gets `recordingLocked` instead of the
    URL. Staff: also the raw slugs for the CMS editor, regardless of status."""
    resource, article, program = event.post_event_resource, event.post_event_article, event.post_event_learning_program
    recording = None
    locked = bool(event.recording_url) and not can_view_recording and not staff
    if event.recording_url and not locked:
        provider = event.recording_provider or "other"
        recording = {
            "url": event.recording_url,
            "provider": provider,
            "providerLabel": VIDEO_PROVIDER_LABELS.get(provider, "Other"),
            "embedUrl": video_embed_url(event.recording_url, provider),
        }
    payload = {
        "recording": recording,
        "resource": {"slug": resource.slug, "name": resource.name} if _public_resource(resource) else None,
        "article": {"slug": article.slug, "title": article.title} if _public_article(article) else None,
        "learningProgram": {"slug": program.slug, "title": program.title} if _public_program(program) else None,
        "recordingLocked": locked,
    }
    if staff:
        payload["editor"] = {
            "recordingUrl": event.recording_url,
            "recordingProvider": event.recording_provider,
            "resourceSlug": resource.slug if resource else None,
            "articleSlug": article.slug if article else None,
            "learningProgramSlug": program.slug if program else None,
        }
        return payload
    return payload if any(payload.values()) else None
