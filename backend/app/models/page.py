from app.extensions import db

# Same draft/published/archived convention as every other CMS content
# type. "draft" is never returned by the public endpoint; "archived" is a
# safety valve for a genuinely retired general page — system pages are
# blocked from ever reaching it (see PageDetailStatusResource).
PAGE_STATUSES = ("draft", "published", "archived")
_PAGE_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in PAGE_STATUSES) + ")"

# "system" pages are the fixed-purpose pages this app already has real
# routes for (About/Contact/Privacy/Terms/Cookies/Editorial Policy) — see
# app/utils/slugs.py RESERVED_SLUGS and frontend/src/routes/AppRoutes.jsx.
# Their `key` is what identifies them to those routes and can never change;
# their `slug` always equals `key` and is not independently editable.
# "general" pages are optional future static pages an admin creates from
# scratch; nothing in this app currently renders them publicly (see the
# Pages CMS final report), but the model, validation, and admin CRUD are
# ready so adding that render path later is a frontend-only change.
PAGE_TYPES = ("system", "general")
_PAGE_TYPE_CHECK_SQL = "page_type IN (" + ", ".join(f"'{t}'" for t in PAGE_TYPES) + ")"

# The stable keys for this app's current system pages, matching the routes
# already registered in AppRoutes.jsx and the reserved-slug list in
# app/utils/slugs.py. Used to seed/identify/protect these rows; a system
# page's `key` must be one of these.
SYSTEM_PAGE_KEYS = ("about", "contact", "privacy", "terms", "cookies", "editorial-policy")


class Page(db.Model):
    """A single static/informational or legal page — About, Contact,
    Privacy Policy, Terms of Use, Cookie Policy, Editorial Policy today,
    plus room for an admin-created general page later. Content is the same
    ordered content-block list (and server-side sanitizer) every other CMS
    content type already uses — see app/services/content_blocks.py — not a
    new editor or a raw-HTML field.
    """

    __tablename__ = "pages"
    __table_args__ = (
        db.CheckConstraint(_PAGE_STATUS_CHECK_SQL, name="ck_pages_status"),
        db.CheckConstraint(_PAGE_TYPE_CHECK_SQL, name="ck_pages_page_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    page_type = db.Column(db.String(20), nullable=False, default="general")

    title = db.Column(db.String(200), nullable=False)
    internal_name = db.Column(db.String(200))  # admin-facing label; falls back to title when blank
    subtitle = db.Column(db.Text)
    content = db.Column(db.JSON, nullable=False, default=list)
    hero_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}
    status = db.Column(db.String(20), nullable=False, default="draft")

    # Explicit, editor-set legal date — never derived from created_at/
    # updated_at, since a re-save that doesn't change the legal substance
    # (fixing a typo, say) must not silently move a Privacy Policy's
    # stated effective date.
    effective_date = db.Column(db.Date)

    last_reviewed_at = db.Column(db.DateTime(timezone=True))
    last_reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    published_at = db.Column(db.DateTime(timezone=True))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    hero_media = db.relationship("Media", foreign_keys=[hero_media_id])
    last_reviewed_by = db.relationship("User", foreign_keys=[last_reviewed_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])

    def is_system(self):
        return self.page_type == "system"


class PageRevision(db.Model):
    """A full JSON snapshot taken on every create/update/status-change —
    same shape and purpose as ArticleRevision (see app/models/article.py):
    lets an admin see who changed a page and when without a diffing
    engine. View-only in this phase; no restore endpoint, matching
    Article's own revision history (see the Pages CMS final report).
    """

    __tablename__ = "page_revisions"

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    note = db.Column(db.String(300))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    page = db.relationship(
        "Page", backref=db.backref("revisions", order_by="PageRevision.created_at.desc()", cascade="all, delete-orphan")
    )
    created_by = db.relationship("User", foreign_keys=[created_by_id])
