import uuid as uuid_lib

from app.extensions import db

# draft -> in_review -> changes_requested -> approved -> scheduled -> published -> archived
ARTICLE_STATUSES = (
    "draft",
    "in_review",
    "changes_requested",
    "approved",
    "scheduled",
    "published",
    "archived",
)
_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{status}'" for status in ARTICLE_STATUSES) + ")"

# Editorial transparency/governance for generative-AI use, not an AI writing
# feature — see AdminArticleEditor's "AI / Editorial Transparency" section.
# "none": no AI involvement. "ai_assisted": AI helped (research, editing,
# suggestions) but a human wrote/owns the piece. "ai_generated_reviewed": an
# AI-generated draft substantially rewritten/reviewed by a human editor.
AI_INVOLVEMENT_VALUES = ("none", "ai_assisted", "ai_generated_reviewed")
_AI_INVOLVEMENT_CHECK_SQL = "ai_involvement IN (" + ", ".join(f"'{v}'" for v in AI_INVOLVEMENT_VALUES) + ")"

article_topics = db.Table(
    "article_topics",
    db.Column("article_id", db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)

article_tags = db.Table(
    "article_tags",
    db.Column("article_id", db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

article_co_authors = db.Table(
    "article_co_authors",
    db.Column("article_id", db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("author_id", db.Integer, db.ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)

article_related_people = db.Table(
    "article_related_people",
    db.Column("article_id", db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("person_id", db.Integer, db.ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
)

article_related_organizations = db.Table(
    "article_related_organizations",
    db.Column("article_id", db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("organization_id", db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
)

article_related_articles = db.Table(
    "article_related_articles",
    db.Column("article_id", db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    db.Column(
        "related_article_id", db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    ),
    db.Column("position", db.Integer, nullable=False, default=0),
)


class Article(db.Model):
    __tablename__ = "articles"
    __table_args__ = (
        db.CheckConstraint(_STATUS_CHECK_SQL, name="ck_articles_status"),
        db.CheckConstraint(_AI_INVOLVEMENT_CHECK_SQL, name="ck_articles_ai_involvement"),
    )

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    subtitle = db.Column(db.Text)
    excerpt = db.Column(db.Text)

    hero_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    hero_image_caption = db.Column(db.String(400))
    hero_image_credit = db.Column(db.String(200))

    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=False)
    publish_date = db.Column(db.DateTime(timezone=True))
    reading_time = db.Column(db.Integer)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    series_id = db.Column(db.Integer, db.ForeignKey("series.id"), nullable=True)

    featured = db.Column(db.Boolean, nullable=False, default=False)
    promoted = db.Column(db.Boolean, nullable=False, default=False)
    is_sponsored = db.Column(db.Boolean, nullable=False, default=False)
    sponsor = db.Column(db.JSON)  # {name, disclosure}

    status = db.Column(db.String(20), nullable=False, default="draft")
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}
    content = db.Column(db.JSON, nullable=False, default=list)  # ordered block list

    # Generative-AI editorial transparency/governance (see AI_INVOLVEMENT_VALUES
    # above). ai_editorial_notes is internal-only — excluded from the public
    # article schema (see schemas/article.py) and never dumped to anyone but
    # an editor with permission to edit this article.
    ai_involvement = db.Column(db.String(30), nullable=False, default="none")
    human_reviewed = db.Column(db.Boolean, nullable=False, default=False)
    ai_disclosure_required = db.Column(db.Boolean, nullable=False, default=False)
    ai_disclosure_text = db.Column(db.Text)
    ai_editorial_notes = db.Column(db.Text)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    hero_media = db.relationship("Media", foreign_keys=[hero_media_id])
    author = db.relationship("Author", foreign_keys=[author_id])
    category = db.relationship("Category")
    series = db.relationship("Series", backref="articles")
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    topics = db.relationship("Topic", secondary=article_topics, backref="articles")
    tags = db.relationship("Tag", secondary=article_tags, backref="articles")
    co_authors = db.relationship("Author", secondary=article_co_authors)
    related_people = db.relationship(
        "Person", secondary=article_related_people, backref=db.backref("related_articles", lazy="dynamic")
    )
    related_organizations = db.relationship("Organization", secondary=article_related_organizations)

    related_articles = db.relationship(
        "Article",
        secondary=article_related_articles,
        primaryjoin=id == article_related_articles.c.article_id,
        secondaryjoin=id == article_related_articles.c.related_article_id,
        order_by=article_related_articles.c.position,
    )

    def __repr__(self):
        return f"<Article {self.slug}>"


class ArticleRevision(db.Model):
    """A full JSON snapshot taken on every save, newest first. Lets an
    editor see/restore prior drafts without a separate diffing engine.
    """

    __tablename__ = "article_revisions"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    note = db.Column(db.String(300))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    article = db.relationship(
        "Article",
        backref=db.backref(
            "revisions", order_by="ArticleRevision.created_at.desc()", cascade="all, delete-orphan"
        ),
    )
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class Redirect(db.Model):
    """Created automatically whenever a published article's slug changes
    (see app/services/slugs.py:create_redirect_for_slug_change), so an old
    flat URL 301s to the new one instead of 404ing. Chains are collapsed to
    a single hop at write time — nothing here should ever need to be
    followed more than once.
    """

    __tablename__ = "redirects"

    id = db.Column(db.Integer, primary_key=True)
    from_slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    to_slug = db.Column(db.String(220), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    article = db.relationship("Article")
