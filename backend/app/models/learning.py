"""WSF Learning: structured educational offerings (short courses,
masterclasses, guided programs, learning series) — deliberately NOT a
full LMS. See the final report for the exhaustive out-of-scope list
(no accounts, entitlement, progress tracking, quizzes, certificates).

One controlled LearningProgram model (rather than separate Course/
Masterclass/Program models) — `program_type` classifies it, matching how
Resource already uses one model + a controlled `type` for a similarly
varied catalog. A LearningProgram owns curriculum/outcomes/instructor
structure only; it never duplicates what Product (pricing), Event
(scheduling/venue), Article (editorial body), or Resource (downloads)
already own — see each relationship's own comment below.
"""
from app.extensions import db

LEARNING_PROGRAM_TYPES = ("course", "masterclass", "program", "learning_series")
_PROGRAM_TYPE_CHECK_SQL = "program_type IN (" + ", ".join(f"'{t}'" for t in LEARNING_PROGRAM_TYPES) + ")"

DIFFICULTY_LEVELS = ("beginner", "intermediate", "advanced", "all_levels")
_DIFFICULTY_CHECK_SQL = "difficulty_level IS NULL OR difficulty_level IN (" + ", ".join(
    f"'{d}'" for d in DIFFICULTY_LEVELS
) + ")"

DELIVERY_MODES = ("self_paced", "live_online", "in_person", "hybrid")
_DELIVERY_MODE_CHECK_SQL = "delivery_mode IN (" + ", ".join(f"'{d}'" for d in DELIVERY_MODES) + ")"

# A small controlled vocabulary (spec: "do not create dozens of hard-coded
# audience types") stored as a JSON list — a program may target more than
# one audience (e.g. both "founders" and "entrepreneurs").
AUDIENCE_TYPES = (
    "aspiring_leaders",
    "professionals",
    "entrepreneurs",
    "founders",
    "career_changers",
    "students",
    "general",
)

# free: publicly accessible, no login/checkout — login is only needed to
# enroll/track progress, never to read the curriculum itself.
# circle_only: full curriculum/lesson content requires an authenticated
# active User with an active WSF Circle entitlement (see
# app/services/circle.py's has_circle_access — the one authoritative
# check, never re-derived here) AND an active LearningEnrollment; the
# catalog/detail metadata and a safe curriculum OUTLINE (titles/summaries/
# duration, no lesson content/external_url/article+resource target
# details) remain public (see app/services/learning_access.py and
# app/schemas/learning.py's LearningProgramOutlineSchema). external: CTA
# sends the visitor to a safe external enrollment URL; no first-party
# enrollment or protected content exists. product: linked to an existing
# Product for commercial access — Product stays the source of truth for
# price/currency (see product relationship below); Learning never stores
# a duplicate price, and WSF Circle membership never unlocks a product
# program (Circle and one-off/commercial purchase are separate concepts).
ACCESS_TYPES = ("free", "circle_only", "external", "product")
_ACCESS_TYPE_CHECK_SQL = "access_type IN (" + ", ".join(f"'{a}'" for a in ACCESS_TYPES) + ")"

DURATION_UNITS = ("minutes", "hours", "days", "weeks")
_DURATION_UNIT_CHECK_SQL = "duration_unit IS NULL OR duration_unit IN (" + ", ".join(
    f"'{u}'" for u in DURATION_UNITS
) + ")"

# Same simple 4-state shape as Resource (draft -> review -> published,
# archived retains the record but hides it publicly) rather than
# Article's full review/approve/schedule workflow — a Learning Program is
# closer to a catalog entry (like Resource/Product) than to time-
# sensitive editorial content, and spec explicitly allows reusing
# "approved" only if the project-wide workflow architecture makes it
# appropriate; it doesn't here; scheduled publishing is not requested.
LEARNING_STATUSES = ("draft", "review", "published", "archived")
_LEARNING_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in LEARNING_STATUSES) + ")"

learning_program_topics = db.Table(
    "learning_program_topics",
    db.Column("learning_program_id", db.Integer, db.ForeignKey("learning_programs.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)

# Co-instructors — the primary instructor is its own FK column below
# (matching Article.author/co_authors' primary-vs-secondary split).
learning_program_instructors = db.Table(
    "learning_program_instructors",
    db.Column("learning_program_id", db.Integer, db.ForeignKey("learning_programs.id", ondelete="CASCADE"), primary_key=True),
    db.Column("author_id", db.Integer, db.ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)

learning_program_related_resources = db.Table(
    "learning_program_related_resources",
    db.Column("learning_program_id", db.Integer, db.ForeignKey("learning_programs.id", ondelete="CASCADE"), primary_key=True),
    db.Column("resource_id", db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
)


class LearningProgramRelatedArticle(db.Model):
    """Ordered link to an existing Article an editor explicitly chose to
    surface on a program's detail page — never a copy of its content, and
    never auto-related by keyword (spec: "allow editors to link relevant
    Articles ... do not auto-relate").
    """

    __tablename__ = "learning_program_related_articles"

    id = db.Column(db.Integer, primary_key=True)
    learning_program_id = db.Column(db.Integer, db.ForeignKey("learning_programs.id", ondelete="CASCADE"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    article = db.relationship("Article", foreign_keys=[article_id])


class LearningProgramEvent(db.Model):
    """Ordered link to an Event representing an upcoming live session/
    cohort. Event remains the sole source of truth for date/time/
    timezone/venue/registration — this table only records which Events
    belong to which Program and in what order (spec section 22/23:
    "do not duplicate dates into both").
    """

    __tablename__ = "learning_program_events"

    id = db.Column(db.Integer, primary_key=True)
    learning_program_id = db.Column(db.Integer, db.ForeignKey("learning_programs.id", ondelete="CASCADE"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    event = db.relationship("Event", foreign_keys=[event_id])


class LearningProgram(db.Model):
    """A structured educational offering. See module docstring for the
    one-model-with-controlled-type decision and what this deliberately
    does NOT own (pricing, scheduling, editorial body, downloads).
    """

    __tablename__ = "learning_programs"
    __table_args__ = (
        db.CheckConstraint(_PROGRAM_TYPE_CHECK_SQL, name="ck_learning_programs_type"),
        db.CheckConstraint(_DIFFICULTY_CHECK_SQL, name="ck_learning_programs_difficulty"),
        db.CheckConstraint(_DELIVERY_MODE_CHECK_SQL, name="ck_learning_programs_delivery_mode"),
        db.CheckConstraint(_ACCESS_TYPE_CHECK_SQL, name="ck_learning_programs_access_type"),
        db.CheckConstraint(_DURATION_UNIT_CHECK_SQL, name="ck_learning_programs_duration_unit"),
        db.CheckConstraint(_LEARNING_STATUS_CHECK_SQL, name="ck_learning_programs_status"),
        db.CheckConstraint("duration_value IS NULL OR duration_value > 0", name="ck_learning_programs_duration_positive"),
    )

    # IDENTITY
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    # Learning has its own slug namespace (spec section 53: "do not
    # needlessly impose Article's globally flat slug namespace") — unique
    # only within learning_programs, not across every content type, since
    # its public route is nested (/learning/{slug}), not flat.
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    subtitle = db.Column(db.String(300))
    short_description = db.Column(db.Text)  # one or two sentences, for cards

    # CLASSIFICATION
    program_type = db.Column(db.String(30), nullable=False, default="course", index=True)
    difficulty_level = db.Column(db.String(20))
    audience = db.Column(db.JSON)  # list[str] drawn from AUDIENCE_TYPES

    # CONTENT
    # Ordered content-block list — same shape/sanitizer/editor as every
    # other content type in this app (see app/services/content_blocks.py).
    overview = db.Column(db.JSON, nullable=False, default=list)
    learning_outcomes = db.Column(db.JSON)  # list[str]
    prerequisites = db.Column(db.JSON)  # list[str] — optional, never fabricated
    duration_value = db.Column(db.Integer)
    duration_unit = db.Column(db.String(10))  # see DURATION_UNITS

    # MEDIA
    hero_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    # INSTRUCTOR — reuses Author (the existing public byline/contributor
    # identity), not a new Instructor identity system (spec section 24).
    primary_instructor_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=True)

    # PROVIDER — optional partner Organization; WSF-as-provider is
    # represented by simply leaving this null rather than fabricating a
    # "Women Shaping Futures" Organization row (spec section 26) — the
    # public detail page falls back to the site identity already exposed
    # by Site Settings for that case.
    provider_organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)

    # DELIVERY — self_paced is derived from delivery_mode == "self_paced"
    # rather than a separate boolean (spec: "only add fields supported by
    # actual requirements"); live/cohort sessions are represented via the
    # LearningProgramEvent links, never duplicated date fields here.
    delivery_mode = db.Column(db.String(20), nullable=False, default="self_paced")

    # ACCESS
    access_type = db.Column(db.String(20), nullable=False, default="free")
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    # Only meaningful when access_type == "external" — a safe http(s) URL
    # (validated at the schema layer via services.homepage.validate_cta_url,
    # the same validator every other CMS CTA field already uses).
    external_url = db.Column(db.String(500))

    # WORKFLOW
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    featured = db.Column(db.Boolean, nullable=False, default=False, index=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # SEO
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots} — same shape as Article.seo

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    hero_media = db.relationship("Media", foreign_keys=[hero_media_id])
    primary_instructor = db.relationship("Author", foreign_keys=[primary_instructor_id])
    co_instructors = db.relationship("Author", secondary=learning_program_instructors)
    provider_organization = db.relationship("Organization", foreign_keys=[provider_organization_id])
    product = db.relationship("Product", foreign_keys=[product_id])
    topics = db.relationship("Topic", secondary=learning_program_topics, backref="learning_programs")
    related_resources = db.relationship("Resource", secondary=learning_program_related_resources)

    related_article_links = db.relationship(
        "LearningProgramRelatedArticle",
        order_by="LearningProgramRelatedArticle.position",
        cascade="all, delete-orphan",
        backref="program",
    )
    event_links = db.relationship(
        "LearningProgramEvent",
        order_by="LearningProgramEvent.position",
        cascade="all, delete-orphan",
        backref="program",
    )
    modules = db.relationship(
        "LearningModule",
        order_by="LearningModule.sort_order",
        cascade="all, delete-orphan",
        backref="program",
    )

    def __repr__(self):
        return f"<LearningProgram {self.slug}>"


class LearningModule(db.Model):
    """An ordered organizational container for lessons. Modules are never
    independently public — visibility follows the parent Program entirely
    (spec section 11).
    """

    __tablename__ = "learning_modules"

    id = db.Column(db.Integer, primary_key=True)
    learning_program_id = db.Column(db.Integer, db.ForeignKey("learning_programs.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    lessons = db.relationship(
        "LearningLesson",
        order_by="LearningLesson.sort_order",
        cascade="all, delete-orphan",
        backref="module",
    )


LESSON_TYPES = ("article", "resource", "video", "activity", "external_link", "text")
_LESSON_TYPE_CHECK_SQL = "lesson_type IN (" + ", ".join(f"'{t}'" for t in LESSON_TYPES) + ")"


class LearningLesson(db.Model):
    """One ordered item inside a Module. A lesson referencing an existing
    Article/Resource stores only the reference (article_id/resource_id) —
    never a copy of that content (spec sections 13-14). `content` (the
    same sanitized content-block shape used everywhere else) is only
    meaningful for lesson_type == "text"/"activity"; video/external_link
    use `external_url` (schema-validated to safe http(s) only — no video
    hosting is built, see spec section 15-16).
    """

    __tablename__ = "learning_lessons"
    __table_args__ = (db.CheckConstraint(_LESSON_TYPE_CHECK_SQL, name="ck_learning_lessons_type"),)

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("learning_modules.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    lesson_type = db.Column(db.String(20), nullable=False, default="text")
    summary = db.Column(db.Text)
    # Native lesson content — only used for lesson_type in (text, activity).
    content = db.Column(db.JSON, nullable=False, default=list)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=True)
    external_url = db.Column(db.String(500))
    duration_minutes = db.Column(db.Integer)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    article = db.relationship("Article", foreign_keys=[article_id])
    resource = db.relationship("Resource", foreign_keys=[resource_id])
