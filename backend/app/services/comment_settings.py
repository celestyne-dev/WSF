"""Studio -> Settings -> "Comments" (SiteSetting key "comments").

Stored in the generic SiteSetting table like the other Studio settings
(app/services/engagement_settings.py): strictly validated, unknown keys
rejected, no secrets. Defaults are configurable product defaults, not
legal requirements, except reportHideThreshold = 3 (product requirement).

  enabled                    master switch: off closes comments on every
                             article (existing published comments stay visible)
  trustedThreshold           published comments a member needs before new
                             comments publish without review (min 1, so a
                             first comment is always held)
  reportHideThreshold        unique reports that hide a published comment
  blockedWords               words/phrases that hold a comment for review
                             (matching: app/services/comments.py
                             blocked_word_hits)
  minSubmitSeconds           a comment submitted sooner than this after its
                             form was issued is refused (signed server time)
  replyNotificationsEnabled  whether members may opt in to reply emails
"""
from app.extensions import db
from app.models.cms import SiteSetting

COMMENTS_KEY = "comments"

COMMENT_DEFAULTS = {
    "enabled": True,
    "trustedThreshold": 3,
    "reportHideThreshold": 3,
    "blockedWords": [],
    "minSubmitSeconds": 3,
    "replyNotificationsEnabled": True,
}
_RANGES = {"trustedThreshold": (1, 50), "reportHideThreshold": (1, 50), "minSubmitSeconds": (1, 60)}
_BOOLS = ("enabled", "replyNotificationsEnabled")
MAX_BLOCKED_WORDS = 300
MAX_BLOCKED_WORD_LENGTH = 80


class CommentSettingsError(ValueError):
    pass


def get_comment_settings():
    row = db.session.get(SiteSetting, COMMENTS_KEY)
    stored = row.value if row and isinstance(row.value, dict) else {}
    settings = dict(COMMENT_DEFAULTS)
    settings.update({k: v for k, v in stored.items() if k in COMMENT_DEFAULTS})
    settings["blockedWords"] = list(settings.get("blockedWords") or [])
    return settings


def _clean_words(value):
    if not isinstance(value, list):
        raise CommentSettingsError("blockedWords must be a list of words or phrases.")
    words, seen = [], set()
    for item in value:
        if not isinstance(item, str):
            raise CommentSettingsError("Each blocked word must be text.")
        word = " ".join(item.split())
        if not word:
            continue
        if len(word) > MAX_BLOCKED_WORD_LENGTH:
            raise CommentSettingsError(f"Blocked words are limited to {MAX_BLOCKED_WORD_LENGTH} characters.")
        key = word.casefold()
        if key not in seen:
            seen.add(key)
            words.append(word)
    if len(words) > MAX_BLOCKED_WORDS:
        raise CommentSettingsError(f"At most {MAX_BLOCKED_WORDS} blocked words or phrases.")
    return words


def save_comment_settings(data):
    """Validates the full or partial settings object, stores it, returns the
    resolved settings. Caller commits and audits."""
    if not isinstance(data, dict):
        raise CommentSettingsError("Comment settings must be an object.")
    unknown = set(data) - set(COMMENT_DEFAULTS)
    if unknown:
        raise CommentSettingsError(f"Unknown comment setting(s): {', '.join(sorted(unknown))}.")
    current = get_comment_settings()
    for key in _BOOLS:
        if key in data:
            if not isinstance(data[key], bool):
                raise CommentSettingsError(f"{key} must be true or false.")
            current[key] = data[key]
    for key, (low, high) in _RANGES.items():
        if key in data:
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise CommentSettingsError(f"{key} must be a whole number from {low} to {high}.")
            current[key] = value
    if "blockedWords" in data:
        current["blockedWords"] = _clean_words(data["blockedWords"])
    row = db.session.get(SiteSetting, COMMENTS_KEY)
    if row is None:
        db.session.add(SiteSetting(key=COMMENTS_KEY, value=current))
    else:
        row.value = current
    return current


def audit_summary(settings):
    """What goes into the Audit Log for a settings change: values, but the
    blocked list only as a count (the list itself may contain slurs)."""
    summary = {k: v for k, v in settings.items() if k != "blockedWords"}
    summary["blockedWordsCount"] = len(settings.get("blockedWords") or [])
    return summary
