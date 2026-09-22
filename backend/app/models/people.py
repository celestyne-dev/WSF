from app.extensions import db

# draft: incomplete/unpublished. published: live on the public profile.
# archived: previously published, pulled from public view but kept for
# editorial record — mirrors Article's draft/.../published/archived shape,
# scoped down since Person doesn't need a review pipeline.
PERSON_STATUSES = ("draft", "published", "archived")
_PERSON_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{status}'" for status in PERSON_STATUSES) + ")"

person_series = db.Table(
    "person_series",
    db.Column("person_id", db.Integer, db.ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
    db.Column("series_id", db.Integer, db.ForeignKey("series.id", ondelete="CASCADE"), primary_key=True),
)


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    logo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    industry = db.Column(db.String(140))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    org_type = db.Column(db.String(80))  # Startup / Foundation / Corporate / Nonprofit / ...
    description = db.Column(db.Text)
    website = db.Column(db.String(300))
    social = db.Column(db.JSON)
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
    to a User account (for staff who log in to draft their own articles).
    """

    __tablename__ = "authors"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200))
    photo_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    bio = db.Column(db.Text)
    short_bio = db.Column(db.Text)
    expertise = db.Column(db.JSON)  # list[str]
    location = db.Column(db.String(200))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    social = db.Column(db.JSON)
    website = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    photo = db.relationship("Media", foreign_keys=[photo_media_id])
    country = db.relationship("Country", foreign_keys=[country_code])
    user = db.relationship("User", foreign_keys=[user_id])
