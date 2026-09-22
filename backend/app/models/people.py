from app.extensions import db

# draft: incomplete/unpublished. published: live on the public profile.
# archived: previously published, pulled from public view but kept for
# editorial record — mirrors Article's draft/.../published/archived shape,
# scoped down since Person doesn't need a review pipeline.
PERSON_STATUSES = ("draft", "published", "archived")
_PERSON_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{status}'" for status in PERSON_STATUSES) + ")"

# draft: incomplete/unpublished. active: contributing, publicly listed.
# archived: no longer active but kept so historical article bylines keep
# resolving — mirrors Person's status shape with editorial-contributor
# terminology instead of a profile's publish state.
AUTHOR_STATUSES = ("draft", "active", "archived")
_AUTHOR_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{status}'" for status in AUTHOR_STATUSES) + ")"

# draft: incomplete/unpublished. published: live in the public directory.
# archived: no longer active but kept so historical relationships (People,
# Jobs, Opportunities, Articles, Series sponsorship) keep resolving.
ORGANIZATION_STATUSES = ("draft", "published", "archived")
_ORGANIZATION_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in ORGANIZATION_STATUSES) + ")"

# Deliberately includes "other" as a catch-all so this never blocks an
# editor from saving — see AdminOrganizationEditor's Organization Type field.
ORGANIZATION_TYPES = (
    "company",
    "nonprofit",
    "foundation",
    "government",
    "educational_institution",
    "media_organization",
    "professional_association",
    "social_enterprise",
    "community_organization",
    "other",
)
_ORGANIZATION_TYPE_CHECK_SQL = "org_type IS NULL OR org_type IN (" + ", ".join(f"'{t}'" for t in ORGANIZATION_TYPES) + ")"

person_series = db.Table(
    "person_series",
    db.Column("person_id", db.Integer, db.ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
    db.Column("series_id", db.Integer, db.ForeignKey("series.id", ondelete="CASCADE"), primary_key=True),
)

author_topics = db.Table(
    "author_topics",
    db.Column("author_id", db.Integer, db.ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)


class Organization(db.Model):
    __tablename__ = "organizations"
    __table_args__ = (
        db.CheckConstraint(_ORGANIZATION_STATUS_CHECK_SQL, name="ck_organizations_status"),
        db.CheckConstraint(_ORGANIZATION_TYPE_CHECK_SQL, name="ck_organizations_org_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    logo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    industry = db.Column(db.String(140))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    location = db.Column(db.String(200))  # headquarters city, e.g. "Nairobi, Kenya"
    founded_year = db.Column(db.Integer)
    org_type = db.Column(db.String(40))
    short_description = db.Column(db.Text)
    # Ordered content-block list — same shape/sanitizer/editor as
    # Person.bio/Author.bio/Article.content.
    description = db.Column(db.JSON, nullable=False, default=list)
    website = db.Column(db.String(300))
    social = db.Column(db.JSON)
    status = db.Column(db.String(20), nullable=False, default="draft")
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}
    featured = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    logo = db.relationship("Media", foreign_keys=[logo_media_id])
    country = db.relationship("Country", foreign_keys=[country_code])


class Person(db.Model):
    """A profile subject (interviewee, honoree, mentor) — distinct from
    Author, which is a byline that writes for the publication.
    """

    __tablename__ = "people"
    __table_args__ = (db.CheckConstraint(_PERSON_STATUS_CHECK_SQL, name="ck_people_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    pronouns = db.Column(db.String(40))
    photo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    title = db.Column(db.String(200))
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    location = db.Column(db.String(200))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    industry = db.Column(db.String(140))
    profession = db.Column(db.String(140))
    expertise = db.Column(db.JSON)  # list[str]
    featured_quote = db.Column(db.Text)
    short_bio = db.Column(db.Text)
    # Ordered block list — same shape/vocabulary as Article.content
    # (paragraph/heading/list/blockquote/pullquote/image/divider/highlight),
    # sanitized through the same sanitize_content_blocks() service and
    # edited/rendered by the same ArticleBlockEditor/ArticleContent
    # components. Not article-specific despite the name: the block types are
    # a generic editorial vocabulary.
    bio = db.Column(db.JSON, nullable=False, default=list)
    achievements = db.Column(db.JSON)  # list[str]
    career_timeline = db.Column(db.JSON)  # list[{year, title}]
    awards = db.Column(db.JSON)  # list[str]
    website = db.Column(db.String(300))
    social = db.Column(db.JSON)
    status = db.Column(db.String(20), nullable=False, default="draft")
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}
    featured = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    photo = db.relationship("Media", foreign_keys=[photo_media_id])
    organization = db.relationship("Organization", foreign_keys=[organization_id])
    country = db.relationship("Country", foreign_keys=[country_code])
    series = db.relationship("Series", secondary=person_series, backref="people")


class Author(db.Model):
    """A byline that writes for Women Shaping Futures — optionally linked
    to a User account (for staff who log in to draft their own articles)
    and, separately, optionally linked to a Person (when the same human is
    also profiled editorially). Distinct from Person: an Author is a
    contributor identity, not a profile subject — most Authors never have
    a Person, and most People never write for WSF.
    """

    __tablename__ = "authors"
    __table_args__ = (db.CheckConstraint(_AUTHOR_STATUS_CHECK_SQL, name="ck_authors_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200))
    photo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    # Ordered content-block list — same shape/sanitizer/editor as
    # Person.bio and Article.content. short_bio stays plain text for
    # bylines/cards.
    bio = db.Column(db.JSON, nullable=False, default=list)
    short_bio = db.Column(db.Text)
    expertise = db.Column(db.JSON)  # list[str] — legacy freeform tags; the
    # CMS now prefers the `topics` relationship below (existing Topic
    # taxonomy) for structured, filterable subject-matter classification.
    location = db.Column(db.String(200))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    social = db.Column(db.JSON)
    website = db.Column(db.String(300))
    status = db.Column(db.String(20), nullable=False, default="draft")
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    photo = db.relationship("Media", foreign_keys=[photo_media_id])
    country = db.relationship("Country", foreign_keys=[country_code])
    person = db.relationship("Person", foreign_keys=[person_id])
    user = db.relationship("User", foreign_keys=[user_id])
    topics = db.relationship("Topic", secondary=author_topics, backref="authors")
