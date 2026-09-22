from app.extensions import db
from app.models.geography import REGIONS

# draft: incomplete, not yet submitted for review. review: submitted,
# awaiting editorial approval before it can go live. scheduled: approved,
# with published_date set in the future — becomes publicly visible
# automatically once that date arrives (computed at read time, no
# scheduler needed). published: live and accepting applications. expired:
# past its deadline/expiry, no longer active but kept for record.
# archived: retained for historical value, not shown in any public
# listing.
JOB_STATUSES = ("draft", "review", "scheduled", "published", "expired", "archived")
_JOB_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in JOB_STATUSES) + ")"

WORK_MODES = ("On-site", "Hybrid", "Remote")
_WORK_MODE_CHECK_SQL = "work_mode IS NULL OR work_mode IN (" + ", ".join(f"'{w}'" for w in WORK_MODES) + ")"

EMPLOYMENT_TYPES = ("Full-time", "Part-time", "Contract", "Temporary", "Internship")
_EMPLOYMENT_TYPE_CHECK_SQL = "employment_type IS NULL OR employment_type IN (" + ", ".join(
    f"'{e}'" for e in EMPLOYMENT_TYPES
) + ")"

CAREER_LEVELS = ("Entry level", "Junior", "Mid-level", "Senior", "Manager", "Director", "Executive")
_CAREER_LEVEL_CHECK_SQL = "career_level IS NULL OR career_level IN (" + ", ".join(
    f"'{c}'" for c in CAREER_LEVELS
) + ")"

# Only meaningful when work_mode is "Remote": worldwide (no geographic
# restriction), country (see country_code), or region (see remote_region).
REMOTE_SCOPES = ("worldwide", "country", "region")
_REMOTE_SCOPE_CHECK_SQL = "remote_scope IS NULL OR remote_scope IN (" + ", ".join(
    f"'{s}'" for s in REMOTE_SCOPES
) + ")"
_REMOTE_REGION_CHECK_SQL = "remote_region IS NULL OR remote_region IN (" + ", ".join(
    f"'{r}'" for r in REGIONS
) + ")"

opportunity_countries = db.Table(
    "opportunity_countries",
    db.Column("opportunity_id", db.Integer, db.ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True),
    db.Column("country_code", db.String(10), db.ForeignKey("countries.code"), primary_key=True),
)

opportunity_topics = db.Table(
    "opportunity_topics",
    db.Column("opportunity_id", db.Integer, db.ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)

SPONSOR_TIERS = ("Presenting Sponsor", "Gold Sponsor", "Silver Sponsor", "Supporting Partner", "Community Partner")


class Job(db.Model):
    __tablename__ = "jobs"
    __table_args__ = (
        db.CheckConstraint(_JOB_STATUS_CHECK_SQL, name="ck_jobs_status"),
        db.CheckConstraint(_WORK_MODE_CHECK_SQL, name="ck_jobs_work_mode"),
        db.CheckConstraint(_EMPLOYMENT_TYPE_CHECK_SQL, name="ck_jobs_employment_type"),
        db.CheckConstraint(_CAREER_LEVEL_CHECK_SQL, name="ck_jobs_career_level"),
        db.CheckConstraint(_REMOTE_SCOPE_CHECK_SQL, name="ck_jobs_remote_scope"),
        db.CheckConstraint(_REMOTE_REGION_CHECK_SQL, name="ck_jobs_remote_region"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)

    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    company_name = db.Column(db.String(200), nullable=False)
    logo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    location = db.Column(db.String(200))
    city = db.Column(db.String(120))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    work_mode = db.Column(db.String(30))  # On-site / Hybrid / Remote
    # Only meaningful when work_mode == "Remote".
    remote_scope = db.Column(db.String(20))  # worldwide / country / region
    remote_region = db.Column(db.String(50))  # set when remote_scope == "region"
    employment_type = db.Column(db.String(30))
    career_level = db.Column(db.String(30))
    industry = db.Column(db.String(140))

    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    currency = db.Column(db.String(3))
    salary_period = db.Column(db.String(10))  # year / month / hour
    # When false, salary_min/max/currency are still stored (useful for
    # internal benchmarking or admin review) but withheld from the public
    # schema/pages — the poster entered real figures without committing to
    # publish them.
    salary_visible = db.Column(db.Boolean, nullable=False, default=True)

    short_description = db.Column(db.Text)  # one or two sentences, for cards
    # Ordered content-block list — same shape/sanitizer/editor as
    # Person.bio/Author.bio/Organization.description/Article.content. The
    # employer/editor writes the free-form narrative ("About the role",
    # "How to apply", etc.) here; the explicit structured lists below
    # (responsibilities/requirements/qualifications/skills/benefits) are
    # separate scannable fields the public page renders as their own
    # sections whenever they're non-empty.
    description = db.Column(db.JSON, nullable=False, default=list)
    responsibilities = db.Column(db.JSON, nullable=False, default=list)  # list[str]
    requirements = db.Column(db.JSON, nullable=False, default=list)  # list[str]
    qualifications = db.Column(db.JSON, nullable=False, default=list)  # list[str]
    skills = db.Column(db.JSON, nullable=False, default=list)  # list[str]
    benefits = db.Column(db.JSON, nullable=False, default=list)  # list[str]

    application_url = db.Column(db.String(500))
    application_email = db.Column(db.String(255))
    application_instructions = db.Column(db.Text)

    deadline = db.Column(db.Date)
    published_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)

    featured = db.Column(db.Boolean, nullable=False, default=False)
    sponsored = db.Column(db.Boolean, nullable=False, default=False)
    # Optional link to a specific paid-sponsorship deal record, for
    # internal reporting/attribution — the public "Sponsored" badge is
    # driven by the `sponsored` flag above regardless of whether a deal
    # record is linked.
    sponsor_id = db.Column(db.Integer, db.ForeignKey("sponsors.id"), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="published")
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}

    posted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    organization = db.relationship("Organization", foreign_keys=[organization_id])
    logo = db.relationship("Media", foreign_keys=[logo_media_id])
    country = db.relationship("Country", foreign_keys=[country_code])
    posted_by = db.relationship("User", foreign_keys=[posted_by_id])
    sponsor = db.relationship("Sponsor", foreign_keys=[sponsor_id])


OPPORTUNITY_TYPES = (
    "Scholarship",
    "Fellowship",
    "Grant",
    "Award",
    "Competition",
    "Accelerator",
    "Incubator",
    "Training Program",
    "Mentorship Program",
    "Internship",
    "Volunteer Opportunity",
    "Conference Opportunity",
    "Funding Opportunity",
    "Other",
)
_OPPORTUNITY_TYPE_CHECK_SQL = "type IS NULL OR type IN (" + ", ".join(f"'{t}'" for t in OPPORTUNITY_TYPES) + ")"

# draft: incomplete/unpublished. published: live and accepting applications.
# closed: manually closed to applications by the poster. archived: kept for
# historical/reference value, no longer promoted in active listings.
OPPORTUNITY_STATUSES = ("draft", "published", "closed", "archived")
_OPPORTUNITY_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in OPPORTUNITY_STATUSES) + ")"

FUNDING_TYPES = ("fully_funded", "partially_funded", "stipend", "unpaid", "not_applicable")
_FUNDING_TYPE_CHECK_SQL = "funding_type IS NULL OR funding_type IN (" + ", ".join(
    f"'{f}'" for f in FUNDING_TYPES
) + ")"


class Opportunity(db.Model):
    __tablename__ = "opportunities"
    __table_args__ = (
        db.CheckConstraint(_OPPORTUNITY_TYPE_CHECK_SQL, name="ck_opportunities_type"),
        db.CheckConstraint(_OPPORTUNITY_STATUS_CHECK_SQL, name="ck_opportunities_status"),
        db.CheckConstraint(_FUNDING_TYPE_CHECK_SQL, name="ck_opportunities_funding_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)

    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    organization_name = db.Column(db.String(200))
    logo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    type = db.Column(db.String(50))  # Scholarship / Fellowship / Grant / ... — see OPPORTUNITY_TYPES

    short_description = db.Column(db.Text)  # one or two sentences, for cards
    # Ordered content-block list — same shape/sanitizer/editor as
    # Job.description/Article.content. The editor structures "About",
    # "What's offered", "Eligibility", "How to apply" etc. themselves with
    # headings and lists rather than the app hard-coding those sections.
    description = db.Column(db.JSON, nullable=False, default=list)

    # Eligibility is the one area every opportunity genuinely differs on, so
    # it stays free text rather than a fixed set of demographic columns —
    # this records what is actually true for THIS opportunity (which may
    # mention age, gender, education, or experience only when the poster
    # says so) instead of assuming a discriminatory classification applies
    # to every listing.
    eligibility = db.Column(db.Text)  # short, scannable eligibility summary
    eligibility_notes = db.Column(db.Text)  # any further eligibility detail specific to this opportunity
    career_stage = db.Column(db.String(60))  # free text, e.g. "Early-career", "Founders" — not a fixed taxonomy

    location = db.Column(db.String(300))

    funding_type = db.Column(db.String(30))  # fully_funded / partially_funded / stipend / unpaid / not_applicable
    funding_min = db.Column(db.Integer)
    funding_max = db.Column(db.Integer)
    currency = db.Column(db.String(3))
    funding_value = db.Column(db.String(200))  # free-text summary, e.g. "$10,000 grant + mentorship"

    application_url = db.Column(db.String(500))
    application_instructions = db.Column(db.Text)

    opening_date = db.Column(db.Date)
    deadline = db.Column(db.Date)
    published_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)

    featured = db.Column(db.Boolean, nullable=False, default=False)
    sponsored = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="published")
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    organization = db.relationship("Organization", foreign_keys=[organization_id])
    logo = db.relationship("Media", foreign_keys=[logo_media_id])
    countries_eligible = db.relationship("Country", secondary=opportunity_countries)
    topics = db.relationship("Topic", secondary=opportunity_topics, backref="opportunities")


EVENT_TYPES = (
    "Conference",
    "Summit",
    "Workshop",
    "Webinar",
    "Networking Event",
    "Panel",
    "Masterclass",
    "Training",
    "Community Event",
    "Career Event",
    "Leadership Event",
    "Founder Event",
    "Mentorship Event",
    "Awards Event",
    "Other",
)
_EVENT_TYPE_CHECK_SQL = "type IS NULL OR type IN (" + ", ".join(f"'{t}'" for t in EVENT_TYPES) + ")"

EVENT_FORMATS = ("in-person", "virtual", "hybrid")
_EVENT_FORMAT_CHECK_SQL = "format IS NULL OR format IN (" + ", ".join(f"'{f}'" for f in EVENT_FORMATS) + ")"

# draft: incomplete/unpublished. review: submitted, awaiting editorial
# approval. scheduled: approved, with published_date set in the future —
# becomes publicly visible automatically once that date arrives (computed
# at read time, no scheduler needed), mirroring Job's identical pattern.
# published: live and publicly listed. postponed: publicly visible but
# clearly marked as postponed (a new date TBD) rather than cancelled
# outright. cancelled: still publicly visible (clearly marked) so
# registrants can see it was called off. archived: retained for record but
# no longer shown in any public listing.
#
# "ongoing"/"completed" are NEVER stored here — like upcoming/past, they're
# computed from `date`/`end_date` at read time (see EventSchema), so an
# editor never has to manually flip a second, redundant status as an event
# starts or ends.
EVENT_STATUSES = ("draft", "review", "scheduled", "published", "postponed", "cancelled", "archived")
_EVENT_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in EVENT_STATUSES) + ")"


class Event(db.Model):
    __tablename__ = "events"
    __table_args__ = (
        db.CheckConstraint(_EVENT_TYPE_CHECK_SQL, name="ck_events_type"),
        db.CheckConstraint(_EVENT_FORMAT_CHECK_SQL, name="ck_events_format"),
        db.CheckConstraint(_EVENT_STATUS_CHECK_SQL, name="ck_events_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)

    short_description = db.Column(db.Text)  # one or two sentences, for cards
    # Ordered content-block list — same shape/sanitizer/editor as
    # Job.description/Opportunity.description. The editor structures
    # "About"/"Who should attend"/"What attendees will gain" etc.
    # themselves rather than the app hard-coding those headings.
    description = db.Column(db.JSON, nullable=False, default=list)

    type = db.Column(db.String(50))  # see EVENT_TYPES
    format = db.Column(db.String(20))  # in-person / virtual / hybrid — see EVENT_FORMATS

    date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)  # set only for multi-day events; single-day events leave this null
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    timezone = db.Column(db.String(50))  # IANA tz name, e.g. Africa/Nairobi, America/New_York

    location = db.Column(db.String(300))
    address = db.Column(db.String(300))
    city = db.Column(db.String(120))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    venue = db.Column(db.String(200))
    virtual_link = db.Column(db.String(500))
    # virtual_link is meant for registered attendees, not the open web —
    # only rendered on the public page when this is explicitly true.
    virtual_link_public = db.Column(db.Boolean, nullable=False, default=False)

    organizer_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    organizer_name = db.Column(db.String(200))  # denormalized fallback when no Organization is linked

    registration_url = db.Column(db.String(500))
    registration_required = db.Column(db.Boolean, nullable=False, default=True)
    registration_deadline = db.Column(db.Date)
    registration_instructions = db.Column(db.Text)
    sold_out = db.Column(db.Boolean, nullable=False, default=False)

    ticket_price = db.Column(db.Integer)  # whole currency units, paired with `currency`; absent = free
    currency = db.Column(db.String(3))
    capacity = db.Column(db.Integer)

    agenda = db.Column(db.JSON)  # list[{time, title}]
    status = db.Column(db.String(20), nullable=False, default="published")
    published_date = db.Column(db.Date)
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}
    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    featured = db.Column(db.Boolean, nullable=False, default=False)
    sponsored = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])
    organizer = db.relationship("Organization", foreign_keys=[organizer_id])
    speakers = db.relationship(
        "EventSpeaker", order_by="EventSpeaker.position", cascade="all, delete-orphan", backref="event"
    )
    sponsors = db.relationship(
        "EventSponsor", order_by="EventSponsor.position", cascade="all, delete-orphan", backref="event"
    )


class EventSpeaker(db.Model):
    """An ordered speaker slot on an Event. Links to an existing Person
    profile where one exists (`person_id`) — never duplicating their name/
    bio/headshot — but every field also has a fallback so an event can list
    a speaker who doesn't (yet) have a People profile, without blocking on
    editorial onboarding.
    """

    __tablename__ = "event_speakers"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True)

    name = db.Column(db.String(200))  # fallback when person_id is unset
    title = db.Column(db.String(200))  # job title, e.g. "CEO"
    organization_name = db.Column(db.String(200))
    bio = db.Column(db.Text)
    headshot_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    person = db.relationship("Person", foreign_keys=[person_id])
    headshot = db.relationship("Media", foreign_keys=[headshot_media_id])


class EventSponsor(db.Model):
    """An ordered sponsor slot on an Event. Links to an existing
    Organization where one exists — never duplicating its name/logo — with
    a fallback name/logo/url for a sponsor that isn't (yet) an Organization
    record. Distinct from commerce.Sponsor, which tracks a standing,
    possibly multi-event sponsorship deal rather than a single event's
    sponsor list.
    """

    __tablename__ = "event_sponsors"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)

    name = db.Column(db.String(200))  # fallback when organization_id is unset
    logo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)  # fallback logo
    url = db.Column(db.String(500))  # fallback link
    tier = db.Column(db.String(50))  # see SPONSOR_TIERS — free text, not enforced by CHECK (editorial nuance)
    position = db.Column(db.Integer, nullable=False, default=0)

    organization = db.relationship("Organization", foreign_keys=[organization_id])
    logo = db.relationship("Media", foreign_keys=[logo_media_id])
