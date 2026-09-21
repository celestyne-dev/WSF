from app.extensions import db

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

event_speakers = db.Table(
    "event_speakers",
    db.Column("event_id", db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    db.Column("person_id", db.Integer, db.ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
)

event_sponsors = db.Table(
    "event_sponsors",
    db.Column("event_id", db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    db.Column("organization_id", db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
)


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)

    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    company_name = db.Column(db.String(200), nullable=False)
    logo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    location = db.Column(db.String(200))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    work_mode = db.Column(db.String(30))  # Remote / Hybrid / On-site
    employment_type = db.Column(db.String(30))  # Full-time / Part-time / Contract
    career_level = db.Column(db.String(30))
    industry = db.Column(db.String(140))

    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    currency = db.Column(db.String(3))
    salary_period = db.Column(db.String(10))  # year / month / hour

    description = db.Column(db.Text)
    responsibilities = db.Column(db.JSON)  # list[str]
    requirements = db.Column(db.JSON)  # list[str]
    benefits = db.Column(db.JSON)  # list[str]

    application_url = db.Column(db.String(500))
    application_instructions = db.Column(db.Text)

    deadline = db.Column(db.Date)
    published_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)

    featured = db.Column(db.Boolean, nullable=False, default=False)
    sponsored = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="published")  # draft/published/expired/closed

    posted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    organization = db.relationship("Organization", foreign_keys=[organization_id])
    logo = db.relationship("Media", foreign_keys=[logo_media_id])
    country = db.relationship("Country", foreign_keys=[country_code])
    posted_by = db.relationship("User", foreign_keys=[posted_by_id])


class Opportunity(db.Model):
    __tablename__ = "opportunities"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)

    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    organization_name = db.Column(db.String(200))
    logo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    type = db.Column(db.String(50))  # Fellowship / Grant / Scholarship / Accelerator / Competition
    description = db.Column(db.Text)
    eligibility = db.Column(db.Text)
    location = db.Column(db.String(300))
    deadline = db.Column(db.Date)
    funding_value = db.Column(db.String(200))
    application_url = db.Column(db.String(500))

    featured = db.Column(db.Boolean, nullable=False, default=False)
    sponsored = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="published")

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    organization = db.relationship("Organization", foreign_keys=[organization_id])
    logo = db.relationship("Media", foreign_keys=[logo_media_id])
    countries_eligible = db.relationship("Country", secondary=opportunity_countries)
    topics = db.relationship("Topic", secondary=opportunity_topics, backref="opportunities")


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    type = db.Column(db.String(50))  # Conference / Workshop / Webinar / Networking
    format = db.Column(db.String(20))  # in-person / virtual / hybrid
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    timezone = db.Column(db.String(50))  # IANA tz name

    location = db.Column(db.String(300))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    venue = db.Column(db.String(200))
    virtual_link = db.Column(db.String(500))

    registration_url = db.Column(db.String(500))
    ticket_price = db.Column(db.Integer)  # whole currency units, paired with `currency`
    currency = db.Column(db.String(3))
    capacity = db.Column(db.Integer)

    agenda = db.Column(db.JSON)  # list[{time, title}]
    status = db.Column(db.String(20), nullable=False, default="upcoming")  # upcoming/past/cancelled
    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    featured = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])
    speakers = db.relationship("Person", secondary=event_speakers)
    sponsors = db.relationship("Organization", secondary=event_sponsors)
