"""Account policy (Step 18): minimum signup age and the legal-document
versions a new member accepts.

The minimum age is a Studio setting (SiteSetting ``account_policy``),
default 16 and bounded 16–21: it can be raised, never lowered below the
approved 16. WSF never asks for a date of birth: signup only records the
person's explicit confirmation and when it was given.
"""
from app.extensions import db
from app.models.page import Page
from app.models.cms import SiteSetting

ACCOUNT_POLICY_KEY = "account_policy"
DEFAULT_MINIMUM_AGE = 16
MINIMUM_AGE_BOUNDS = (16, 21)


class AccountPolicyError(ValueError):
    pass


def get_account_policy():
    row = db.session.get(SiteSetting, ACCOUNT_POLICY_KEY)
    stored = row.value if row and isinstance(row.value, dict) else {}
    age = stored.get("minimumAge")
    low, high = MINIMUM_AGE_BOUNDS
    if isinstance(age, bool) or not isinstance(age, int) or not low <= age <= high:
        age = DEFAULT_MINIMUM_AGE
    return {"minimumAge": age}


def account_policy_payload():
    low, high = MINIMUM_AGE_BOUNDS
    return {**get_account_policy(), "bounds": {"min": low, "max": high, "default": DEFAULT_MINIMUM_AGE}}


def save_account_policy(data):
    if not isinstance(data, dict):
        raise AccountPolicyError("Account policy must be an object.")
    unknown = set(data) - {"minimumAge", "bounds"}
    if unknown:
        raise AccountPolicyError(f"Unknown account policy setting(s): {', '.join(sorted(unknown))}.")
    current = get_account_policy()
    if "minimumAge" in data:
        age = data["minimumAge"]
        low, high = MINIMUM_AGE_BOUNDS
        if isinstance(age, bool) or not isinstance(age, int) or not low <= age <= high:
            raise AccountPolicyError(f"Minimum age: a whole number of years from {low} to {high}.")
        current["minimumAge"] = age
    row = db.session.get(SiteSetting, ACCOUNT_POLICY_KEY)
    if row is None:
        db.session.add(SiteSetting(key=ACCOUNT_POLICY_KEY, value=current))
    else:
        row.value = current
    return current


def legal_document_version(key):
    """A verifiable identifier for the Terms/Privacy text in force right now:
    ``<key>:<effective date or 'undated'>@<last updated, ISO UTC>``. Stored on
    the account at signup, so the exact published revision a member accepted
    can be matched against the page's history. ``<key>:unpublished`` if the
    page isn't published (the signup still proceeds; the legal audit flags
    unpublished legal pages separately)."""
    page = Page.query.filter_by(key=key).first()
    if page is None or page.status != "published":
        return f"{key}:unpublished"
    effective = page.effective_date.isoformat() if page.effective_date else "undated"
    stamp = page.updated_at or page.published_at
    return f"{key}:{effective}@{stamp.isoformat() if stamp else 'unknown'}"
