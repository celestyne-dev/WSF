"""Safe video/recording references for WSF Learning lessons and Event
recordings. WSF hosts no video: a lesson or event stores only a public
http(s) watch URL. The provider is detected from that URL's host, and an
embed URL is built here from an extracted, character-checked id for the
four allowlisted providers (YouTube, Vimeo, Wistia, Loom). Arbitrary
iframe HTML is never accepted or stored, and "other" providers are only
ever linked to, never embedded.
"""
import re
from urllib.parse import parse_qs, urlparse

VIDEO_PROVIDERS = ("youtube", "vimeo", "wistia", "loom", "other")
VIDEO_PROVIDER_LABELS = {
    "youtube": "YouTube",
    "vimeo": "Vimeo",
    "wistia": "Wistia",
    "loom": "Loom",
    "other": "Other",
}

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
_DIGITS_RE = re.compile(r"^\d{3,20}$")

_PROVIDER_HOSTS = {
    "youtube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "vimeo": ("vimeo.com",),
    "wistia": ("wistia.com", "wistia.net", "wi.st"),
    "loom": ("loom.com",),
}


def _host(parsed):
    host = (parsed.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)


def is_safe_video_url(url):
    if not url or not isinstance(url, str) or len(url) > 500:
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.hostname) and not any(c.isspace() for c in url.strip())


def detect_video_provider(url):
    if not is_safe_video_url(url):
        return None
    host = _host(urlparse(url.strip()))
    for provider, domains in _PROVIDER_HOSTS.items():
        if _matches(host, domains):
            return provider
    return "other"


def _youtube_id(parsed):
    host = _host(parsed)
    parts = [p for p in parsed.path.split("/") if p]
    if host == "youtu.be" and parts:
        return parts[0]
    if parts and parts[0] == "watch":
        return (parse_qs(parsed.query).get("v") or [None])[0]
    if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v"):
        return parts[1]
    return None


def _vimeo_id(parsed):
    parts = [p for p in parsed.path.split("/") if p]
    for part in parts:
        if _DIGITS_RE.match(part):
            return part
    return None


def _wistia_id(parsed):
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[-2] in ("medias", "iframe"):
        return parts[-1]
    return None


def _loom_id(parsed):
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] in ("share", "embed"):
        return parts[1]
    return None


def video_embed_url(url, provider=None):
    """An embeddable https URL on the provider's own player host, or None
    (unknown provider, unparseable id, or unsafe input) -> link out only."""
    if not is_safe_video_url(url):
        return None
    detected = detect_video_provider(url)
    if provider and provider != detected:
        return None
    parsed = urlparse(url.strip())
    if detected == "youtube":
        vid = _youtube_id(parsed)
        return f"https://www.youtube-nocookie.com/embed/{vid}" if vid and _ID_RE.match(vid) else None
    if detected == "vimeo":
        vid = _vimeo_id(parsed)
        return f"https://player.vimeo.com/video/{vid}" if vid else None
    if detected == "wistia":
        vid = _wistia_id(parsed)
        return f"https://fast.wistia.net/embed/iframe/{vid}" if vid and _ID_RE.match(vid) else None
    if detected == "loom":
        vid = _loom_id(parsed)
        return f"https://www.loom.com/embed/{vid}" if vid and _ID_RE.match(vid) else None
    return None


def resolve_video_provider(url, requested=None):
    """The provider stored with a URL: the detected provider, or "other".
    A requested provider that contradicts the URL's host is rejected so a
    "YouTube" label can never sit on a non-YouTube link."""
    detected = detect_video_provider(url)
    if detected is None:
        raise ValueError("Video links must be a full https:// URL.")
    if requested and requested not in VIDEO_PROVIDERS:
        raise ValueError("Unknown video provider.")
    if requested and requested != "other" and requested != detected:
        raise ValueError(f"This link is not a {VIDEO_PROVIDER_LABELS[requested]} URL.")
    return detected if not requested or requested != "other" else "other"
