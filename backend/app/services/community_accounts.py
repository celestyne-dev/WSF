"""Authenticated-account <-> Community Member self-service logic (join,
leave, rejoin, profile update) and the staff-only exact-email account
link/unlink actions. Sits on top of the optional one-to-one
Member.user_id link (see app/models/community.py's Member docstring) —
User (account identity) and Member (Community profile/lifecycle) stay
entirely separate records even when linked.

See app/api/v1/community.py's MemberJoinResource for the separate,
unrelated anonymous public /community/join flow this module never
touches. join_as_account() below only ever CREATES a Member (never
mutates an existing linked one's status, even on a repeat call) —
leave_community()/rejoin_community() are the only two places a linked
Member's status changes, so the three endpoints can never step on each
other.
"""
from app.extensions import db
from app.models.community import Member
from app.models.geography import Country
from app.models.taxonomy import Topic
from app.models.user import User
from app.services.newsletter import upsert_subscriber
from app.utils.responses import ApiError

# Self-service reactivation is allowed only from these two statuses — the
# exact same eligibility set api/v1/community.py's anonymous join already
# uses for its own reactivation branch (_REACTIVATABLE_STATUSES there).
# paused/pending/declined/archived are deliberate staff states that no
# self-service action may reverse.
_REACTIVATABLE_STATUSES = ("left", "inactive")

_SELF_UPDATE_FIELDS = (
    "first_name", "last_name", "professional_title", "organization_name", "short_bio",
    "website_url", "linkedin_url", "country_code", "city", "community_updates_opt_in", "directory_opt_in",
)
_JOIN_PROFILE_FIELDS = ("professional_title", "organization_name", "short_bio", "website_url", "linkedin_url", "city")


def get_member_for_user(user):
    """Looks up ONLY by Member.user_id == user.id — never by email, so a
    historical, not-yet-linked Member sharing this user's email is never
    silently surfaced through this path (see join_as_account's own,
    separate conflict check below for how that case is actually handled).
    """
    return Member.query.filter_by(user_id=user.id).first()


def _resolve_topics(slugs):
    """Strict for these authenticated account flows: every submitted slug
    must match an existing Topic, or the whole request is rejected (422
    `invalid_interest`) before anything is written — never silently drops
    an unknown slug and keeps the rest. Contrast with the separate,
    deliberately lenient anonymous /community/join flow's own resolver in
    api/v1/community.py, which this module never shares or touches (see
    that file's own _resolve_topics). An empty list is valid and means no
    interests. Duplicate slugs collapse to their one matching Topic (no
    duplicate associations), since in_() naturally de-duplicates and a
    Topic's slug is itself unique.
    """
    if not slugs:
        return []
    unique_slugs = list(dict.fromkeys(slugs))
    topics = Topic.query.filter(Topic.slug.in_(unique_slugs)).all()
    found = {t.slug for t in topics}
    missing = [s for s in unique_slugs if s not in found]
    if missing:
        raise ApiError(
            f"Unknown interest{'s' if len(missing) > 1 else ''}: {', '.join(missing)}",
            422,
            code="invalid_interest",
        )
    return topics


def _normalize_country_code(data):
    if "country_code" not in data:
        return
    code = (data["country_code"] or "").strip().upper() or None
    if code and not db.session.get(Country, code):
        raise ApiError("Unknown country code.", 422, code="invalid_country")
    data["country_code"] = code


def join_as_account(user, data):
    """POST /community/me/join. Idempotent: if `user` already has ANY
    linked Member (whatever its status), this returns it unchanged and
    `created=False` — reactivation is rejoin_community()'s job, never
    this one's.

    Returns (member, created).
    """
    existing = get_member_for_user(user)
    if existing is not None:
        return existing, False

    _normalize_country_code(data)
    email = user.email.strip().lower()

    # A pre-existing Member with this email (unlinked, or linked to a
    # different account — either way Member.email is globally unique, so
    # a new row can't be created) is never auto-claimed or revealed here.
    # Staff must explicitly connect it via link_account_by_exact_email().
    if Member.query.filter_by(email=email).first() is not None:
        raise ApiError(
            "We couldn't connect your Community membership automatically. Please contact Women Shaping Futures for help.",
            409,
            code="membership_link_required",
        )

    interest_slugs = data.pop("interest_slugs", [])
    topics = _resolve_topics(interest_slugs)  # validated before any Member field is touched
    member = Member(
        email=email,
        user_id=user.id,
        status="active",
        activated_at=db.func.now(),
        membership_type="Community Member",
        source="Community page",
        first_name=data.get("first_name") or user.first_name,
        last_name=data.get("last_name") or user.last_name,
        country_code=data.get("country_code") or user.country_code,
    )
    for field in _JOIN_PROFILE_FIELDS:
        if field in data:
            setattr(member, field, data[field])
    member.consent_given = True
    member.consent_at = db.func.now()
    member.newsletter_opt_in = bool(data.get("subscribe_newsletter"))
    # Directory visibility never defaults on through the account-join path
    # either — the model column default already is False, set explicitly
    # here so the rule is visible at the call site, not just implied.
    member.directory_opt_in = False
    member.interests = topics

    db.session.add(member)
    db.session.commit()

    if member.newsletter_opt_in:
        upsert_subscriber(
            email=member.email,
            first_name=member.first_name,
            last_name=member.last_name,
            country_code=member.country_code,
            placement="community-join",
        )
        db.session.commit()

    return member, True


def update_self_profile(member, data):
    """PATCH /community/me — only the fields in _SELF_UPDATE_FIELDS are
    ever touched; the schema that produced `data`
    (MemberSelfUpdateInputSchema) never even declares user_id, email,
    status, membership_type, source, admin_tags, person_id, acquisition,
    or the lifecycle timestamps, so a request naming them is rejected by
    the schema before this function is ever called.
    """
    _normalize_country_code(data)
    interest_slugs = data.pop("interest_slugs", None)
    # Validated BEFORE any field is applied — an unknown slug must reject
    # the whole request and leave the Member (interests included)
    # completely untouched, never a partial apply.
    topics = _resolve_topics(interest_slugs) if interest_slugs is not None else None
    for field in _SELF_UPDATE_FIELDS:
        if field in data:
            setattr(member, field, data[field])
    if topics is not None:
        member.interests = topics
    db.session.commit()
    return member


def leave_community(member):
    """Idempotent for an already left/inactive member."""
    if member.status in ("left", "inactive"):
        return member
    member.status = "left"
    member.left_at = db.func.now()
    # PRIVACY: leaving always clears directory visibility immediately,
    # regardless of its prior value.
    member.directory_opt_in = False
    db.session.commit()
    return member


def rejoin_community(member):
    """Reuses the SAME Member row — never creates another, never touches
    user_id. Idempotent if already active.
    """
    if member.status == "active":
        return member
    if member.status not in _REACTIVATABLE_STATUSES:
        raise ApiError(
            "This membership can't be reactivated automatically. Please contact Women Shaping Futures for help.",
            409,
            code="rejoin_not_allowed",
        )
    member.status = "active"
    member.activated_at = db.func.now()
    member.left_at = None
    # Directory visibility is never silently restored on rejoin — a member
    # who wants to be public again opts back in explicitly afterward via
    # PATCH /community/me.
    member.directory_opt_in = False
    db.session.commit()
    return member


def link_account_by_exact_email(member):
    """Staff-only (community.manage — enforced by the caller). Matches by
    EXACT normalized email only; staff never search/browse arbitrary
    Users. Returns (member, user).
    """
    if member.user_id is not None:
        raise ApiError("This member is already linked to a WSF account.", 409, code="already_linked")

    normalized = member.email.strip().lower()
    user = User.query.filter_by(email=normalized).first()
    if user is None:
        raise ApiError("No WSF account currently uses this member email.", 404, code="no_matching_account")
    if Member.query.filter_by(user_id=user.id).first() is not None:
        raise ApiError("That WSF account is already linked to a different member.", 409, code="account_already_linked")

    member.user_id = user.id
    db.session.commit()
    return member, user


def unlink_account(member):
    """Severs the link only — preserves the Member, the User, and all
    membership history.
    """
    member.user_id = None
    db.session.commit()
    return member
