from app.extensions import db

# reviewing -> accepted / declined
REVIEW_STATUSES = ("new", "reviewing", "accepted", "declined")

# WSF community membership is currently free and open — a public Join
# submission becomes "active" immediately (see api/v1/community.py's join
# route), not a gated "applicant"/"pending" review queue. "pending" is kept
# in the enum (unused by the default join flow) so this can be switched to
# an approval-gated flow later without a schema change. "declined" and
# "archived" are reserved for deliberate admin actions (spam/duplicate
# cleanup, retiring a record) — never something a public join can trigger.
MEMBERSHIP_STATUSES = ("pending", "active", "paused", "inactive", "declined", "left", "archived")
_MEMBERSHIP_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in MEMBERSHIP_STATUSES) + ")"

# A simple, extensible tier label — not a priced product. Every new member
# starts as "Community Member"; the others exist so staff can recognize
# early/founding members or a future partner-org member by hand, without
# any billing or entitlement logic attached to the value (see section 31
# of the Community/Membership CMS task: paid-membership-ready, not
# paid-membership-implemented).
MEMBERSHIP_TYPES = ("Community Member", "Founding Member", "Premium Member", "Partner Member")
_MEMBERSHIP_TYPE_CHECK_SQL = "membership_type IN (" + ", ".join(f"'{t}'" for t in MEMBERSHIP_TYPES) + ")"

# Where a join came from — a small controlled set (never an arbitrary
# client-supplied string) so admin filtering/reporting stays meaningful.
MEMBERSHIP_SOURCES = ("Community page", "LinkedIn", "Newsletter", "Event", "Referral", "Organic", "Other")
_MEMBERSHIP_SOURCE_CHECK_SQL = "source IS NULL OR source IN (" + ", ".join(
    f"'{s}'" for s in MEMBERSHIP_SOURCES
) + ")"

member_topics = db.Table(
    "member_topics",
    db.Column("member_id", db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)


class Member(db.Model):
    """A WSF community member — entirely separate from `User` (CMS/admin
    login accounts) and from `Person` (public profile subjects). Joining
    the community never creates a User (no admin login/permissions) and
    never creates a Person (no automatic public profile); a Member may
    optionally be linked to an existing Person by an admin (see
    `person_id`), and that link never changes either record's own
    visibility rules.
    """

    __tablename__ = "members"
    __table_args__ = (
        db.CheckConstraint(_MEMBERSHIP_STATUS_CHECK_SQL, name="ck_members_status"),
        db.CheckConstraint(_MEMBERSHIP_TYPE_CHECK_SQL, name="ck_members_type"),
        db.CheckConstraint(_MEMBERSHIP_SOURCE_CHECK_SQL, name="ck_members_source"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    # Normalized (stripped + lowercased) at write time — see
    # api/v1/community.py — so "Person@Example.com" and "person@example.com"
    # can never both become active members. Historical rows are never
    # rewritten by the normalization itself; it only governs new writes.
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # Optional professional profile — entirely voluntary.
    professional_title = db.Column(db.String(200))
    organization_name = db.Column(db.String(200))
    short_bio = db.Column(db.Text)
    website_url = db.Column(db.String(500))
    linkedin_url = db.Column(db.String(500))
    profile_image_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    # Geography — reuses the single Country/region table; no duplicate
    # geography data. City is a plain optional string (no separate model).
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    city = db.Column(db.String(120))

    # Membership lifecycle
    status = db.Column(db.String(20), nullable=False, default="active")
    membership_type = db.Column(db.String(30), nullable=False, default="Community Member")
    source = db.Column(db.String(50))  # controlled MEMBERSHIP_SOURCES value, set by the join placement
    referral_note = db.Column(db.String(300))  # freeform "how did you hear about us?" — optional, not a rewards system
    applied_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    activated_at = db.Column(db.DateTime(timezone=True))
    left_at = db.Column(db.DateTime(timezone=True))

    # Interests — reuses the existing editorial Topic taxonomy; no second
    # interests table. Multiple interests allowed; none required.
    interests = db.relationship("Topic", secondary=member_topics, backref="members")

    # Privacy / consent
    consent_given = db.Column(db.Boolean, nullable=False, default=False)
    consent_at = db.Column(db.DateTime(timezone=True))
    # A record of what was explicitly chosen at join time — the live
    # subscription itself lives in NewsletterSubscriber (see
    # app/services/newsletter.py::upsert_subscriber, called separately by
    # the join route only when this was true). Never implied true.
    newsletter_opt_in = db.Column(db.Boolean, nullable=False, default=False)
    # Membership-service communication (e.g. "your application was
    # reviewed") — distinct from newsletter/marketing consent. Defaults to
    # true as an ordinary part of joining a community (you expect to hear
    # from the community you joined); this is not a marketing channel and
    # has no automation attached to it yet.
    community_updates_opt_in = db.Column(db.Boolean, nullable=False, default=True)
    # Public member-directory participation — OFF by default. Joining WSF
    # never makes anyone publicly discoverable on its own; this is the one
    # field that can change that, and only when explicitly set true.
    directory_opt_in = db.Column(db.Boolean, nullable=False, default=False)

    # Optional admin link to an existing public Person profile — set only
    # by an admin, never automatically, and never itself makes the member
    # (or the Person) more or less publicly visible.
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True)

    # Internal only — never serialized to any public response.
    admin_tags = db.Column(db.JSON)  # list[str], optional

    acquisition = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    person = db.relationship("Person", foreign_keys=[person_id])
    profile_image = db.relationship("Media", foreign_keys=[profile_image_media_id])
    notes = db.relationship(
        "MemberNote", order_by="MemberNote.created_at.desc()", cascade="all, delete-orphan", backref="member"
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def is_publicly_listable(self):
        return self.status == "active" and self.directory_opt_in


class MemberNote(db.Model):
    """An internal, staff-only note on a member — never returned by any
    public response. Same append-only association-object pattern as
    PartnershipNote/OrderNote, so each entry carries its own author and
    timestamp rather than being a single overwritable text blob.
    """

    __tablename__ = "member_notes"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])


COMMUNITY_PAGE_STATUSES = ("draft", "published")
_COMMUNITY_PAGE_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in COMMUNITY_PAGE_STATUSES) + ")"


class CommunityPage(db.Model):
    """The single editable public /community page — hero, intro, benefits,
    who-it's-for/how-to-join copy, CTA, FAQ, and SEO. One row (id=1),
    seeded by migration so the public route never 404s just because no
    admin has opened the editor yet. Deliberately scoped to Community-page
    content only, not a generic page builder.
    """

    __tablename__ = "community_page"
    __table_args__ = (db.CheckConstraint(_COMMUNITY_PAGE_STATUS_CHECK_SQL, name="ck_community_page_status"),)

    id = db.Column(db.Integer, primary_key=True)

    hero_heading = db.Column(db.String(200))
    hero_description = db.Column(db.Text)
    hero_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    # Ordered content-block list — same shape/sanitizer/editor
    # (ArticleBlockEditor + sanitize_content_blocks) as every other
    # editorial content field in this app, not a new block system.
    intro_content = db.Column(db.JSON, nullable=False, default=list)

    # [{title, description}, ...] — a lightweight structured list, not a
    # separate technical system per benefit (see task section 25).
    benefits = db.Column(db.JSON, nullable=False, default=list)

    who_for_text = db.Column(db.Text)
    how_to_join_text = db.Column(db.Text)

    cta_heading = db.Column(db.String(200))
    cta_description = db.Column(db.Text)
    cta_button_label = db.Column(db.String(50))

    faq = db.Column(db.JSON, nullable=False, default=list)  # [{question, answer}, ...]

    status = db.Column(db.String(20), nullable=False, default="draft")
    seo = db.Column(db.JSON)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    hero_media = db.relationship("Media", foreign_keys=[hero_media_id])


class StorySubmission(db.Model):
    __tablename__ = "story_submissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    excerpt = db.Column(db.Text)
    body = db.Column(db.Text)  # the full pitch/draft, if provided
    status = db.Column(db.String(20), nullable=False, default="new")
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])


class Nomination(db.Model):
    __tablename__ = "nominations"

    id = db.Column(db.Integer, primary_key=True)
    nominee_name = db.Column(db.String(200), nullable=False)
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    profession = db.Column(db.String(200))
    organization = db.Column(db.String(200))
    achievements = db.Column(db.Text)
    nominator_name = db.Column(db.String(200), nullable=False)
    nominator_email = db.Column(db.String(255), nullable=False)
    relationship_to_nominee = db.Column(db.String(200))
    category = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default="new")
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
