from app.extensions import db

# Shared status/visibility convention for all four taxonomy types — same
# values as Organization/Author/Article-adjacent content types elsewhere
# in the CMS. "draft" is never returned by any public endpoint; "archived"
# stops appearing in new public navigation/selectors but existing content
# relationships (an Article that already carries an archived Topic, say)
# remain intact — see TAXONOMY_STATUSES usage in api/v1/taxonomy.py and
# api/v1/admin_taxonomy.py.
TAXONOMY_STATUSES = ("draft", "published", "archived")
_TAXONOMY_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in TAXONOMY_STATUSES) + ")"


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (db.CheckConstraint(_TAXONOMY_STATUS_CHECK_SQL, name="ck_categories_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text)
    # Categories have no public detail page (Article's sole classification
    # value, admin/filtering use only) — no SEO or hero-image fields, per
    # CATEGORY HIERARCHY / section 40's "appropriately simpler" editor.
    status = db.Column(db.String(20), nullable=False, default="published")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


class Tag(db.Model):
    __tablename__ = "tags"
    __table_args__ = (db.CheckConstraint(_TAXONOMY_STATUS_CHECK_SQL, name="ck_tags_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    # Lightweight secondary metadata — no SEO/media/hierarchy (section 17).
    status = db.Column(db.String(20), nullable=False, default="published")
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


class Topic(db.Model):
    """Editorial topic taxonomy (Leadership, Career, Business, ...). The
    CMS can add/rename/retire topics without a frontend code change — this
    table is what frontend/src/mock/topics.js stands in for pre-Phase-8.
    """

    __tablename__ = "topics"
    __table_args__ = (db.CheckConstraint(_TAXONOMY_STATUS_CHECK_SQL, name="ck_topics_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text)
    hero_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots} — same shape as Article.seo
    status = db.Column(db.String(20), nullable=False, default="published")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    hero_media = db.relationship("Media", foreign_keys=[hero_media_id])


class Series(db.Model):
    __tablename__ = "series"
    __table_args__ = (db.CheckConstraint(_TAXONOMY_STATUS_CHECK_SQL, name="ck_series_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(300))
    description = db.Column(db.Text)
    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    sponsor_organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots} — same shape as Article.seo
    featured = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="published")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])
    sponsor_organization = db.relationship("Organization", foreign_keys=[sponsor_organization_id])
