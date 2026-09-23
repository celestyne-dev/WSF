from app.extensions import db


class HomepageModule(db.Model):
    """One row per homepage section, rendered in `sort_order` by the
    frontend's existing per-type components (HeroModule, FeaturedWomanModule,
    ...) — this table is what frontend/src/mock/homepageModules.js stands
    in for. `config` holds whatever fields that module `type` needs
    (leadArticleSlug, personSlug, seriesSlug, itemCount, partnerSlugs, ...)
    since each type's shape is different enough that a fixed column per
    field would mean most rows leave most columns null.
    """

    __tablename__ = "homepage_modules"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    heading = db.Column(db.String(200))
    subheading = db.Column(db.String(400))
    selection_mode = db.Column(db.String(20))  # manual / automatic
    config = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


class Menu(db.Model):
    """A named navigation slot: primary, secondary, or one of the footer
    columns (footer_explore, footer_opportunity, footer_wsf, footer_legal).
    """

    __tablename__ = "menus"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    heading = db.Column(db.String(100))

    def top_level_items(self):
        return MenuItem.query.filter_by(menu_id=self.id, parent_id=None).order_by(MenuItem.sort_order).all()


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id", ondelete="CASCADE"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=True)
    label = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    visible = db.Column(db.Boolean, nullable=False, default=True)

    children = db.relationship(
        "MenuItem",
        backref=db.backref("parent", remote_side=[id]),
        order_by="MenuItem.sort_order",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    menu = db.relationship("Menu", foreign_keys=[menu_id])


class SiteSetting(db.Model):
    """A flexible key/value store for site-wide settings (name, tagline,
    contact email, footer copy, maintenance mode, ...) so adding a new
    setting is a data change, not a migration.
    """

    __tablename__ = "site_settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.JSON)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


class SocialLink(db.Model):
    __tablename__ = "social_links"

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(30), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    handle = db.Column(db.String(100))
    sort_order = db.Column(db.Integer, nullable=False, default=0)


ADVERTISE_PAGE_STATUSES = ("draft", "published")
_ADVERTISE_PAGE_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in ADVERTISE_PAGE_STATUSES) + ")"

ADVERTISE_OFFERING_STATUSES = ("active", "unavailable", "hidden")
_ADVERTISE_OFFERING_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in ADVERTISE_OFFERING_STATUSES) + ")"

# hidden: no pricing shown at all. contact: "Contact for pricing", no
# amount required. starting_from: `price_amount` shown as a floor
# ("Starting from"). fixed: `price_amount` shown as the exact public
# price. Only `starting_from`/`fixed` actually require `price_amount`;
# validated in the schema, not the DB, since "hidden"/"contact" rows
# legitimately carry no price at all.
ADVERTISE_PRICING_MODES = ("hidden", "contact", "starting_from", "fixed")
_ADVERTISE_PRICING_MODE_CHECK_SQL = "pricing_mode IN (" + ", ".join(f"'{p}'" for p in ADVERTISE_PRICING_MODES) + ")"


class AdvertisePage(db.Model):
    """The single editable /advertise page — hero, introduction, audience
    overview, "why partner" copy, CTA, contact info, an optional Media Kit
    download, a small FAQ, and SEO. One row (id=1); the migration seeds it
    so the public route never 404s just because no admin has opened the
    editor yet. AdvertiseMetric/AdvertiseOffering are separate tables
    (genuinely addable/reorderable lists), not columns here.
    """

    __tablename__ = "advertise_page"
    __table_args__ = (db.CheckConstraint(_ADVERTISE_PAGE_STATUS_CHECK_SQL, name="ck_advertise_page_status"),)

    id = db.Column(db.Integer, primary_key=True)

    hero_heading = db.Column(db.String(200))
    hero_description = db.Column(db.Text)
    hero_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    # Ordered content-block lists — same shape/sanitizer/editor
    # (ArticleBlockEditor + sanitize_content_blocks) as Article/Resource/
    # Job/Event/Organization/Author/Person, not a new block system.
    intro_content = db.Column(db.JSON, nullable=False, default=list)
    audience_overview = db.Column(db.Text)
    why_content = db.Column(db.JSON, nullable=False, default=list)

    cta_heading = db.Column(db.String(200))
    cta_description = db.Column(db.Text)
    cta_button_label = db.Column(db.String(50))
    contact_email = db.Column(db.String(255))
    contact_note = db.Column(db.Text)

    # Media Kit download — a plain hosted URL, the same pattern
    # Resource.file_url already uses for non-image downloadables (the
    # Media Library only pipelines images; no generic binary-upload
    # service exists anywhere in this app to reuse instead — see final
    # report). Never a raw filesystem path.
    media_kit_title = db.Column(db.String(200))
    media_kit_url = db.Column(db.String(500))
    media_kit_updated_at = db.Column(db.Date)

    faq = db.Column(db.JSON, nullable=False, default=list)  # [{question, answer}, ...]

    status = db.Column(db.String(20), nullable=False, default="draft")
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    hero_media = db.relationship("Media", foreign_keys=[hero_media_id])


class AdvertiseMetric(db.Model):
    """One CMS-managed audience/commercial metric shown on the Advertise
    page (e.g. "LinkedIn followers" / "130,000+"). `value` is a free-text
    display string, not a number column — real metrics arrive in wildly
    different shapes ("130,000+", "42 countries", "6.1%") and forcing a
    single numeric type would mean reintroducing formatting logic in the
    frontend for no benefit. `source_note` is internal-only — audits where
    a figure came from, never rendered publicly.
    """

    __tablename__ = "advertise_metrics"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(30))
    source_note = db.Column(db.Text)
    as_of_date = db.Column(db.Date)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    public_visible = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


class AdvertiseOffering(db.Model):
    """A commercial/collaboration offering described on the Advertise page
    (e.g. "Newsletter Sponsorship"). Deliberately not linked to
    commerce.Sponsor — this describes an available opportunity, not a
    live sponsorship deal (see Sponsors CMS for that). Never referenced
    by a foreign key from anywhere else, so a delete here can never break
    another record; a historical advertising inquiry stores the offering
    name it was submitted against as plain text, not a link to this row.
    """

    __tablename__ = "advertise_offerings"
    __table_args__ = (
        db.CheckConstraint(_ADVERTISE_OFFERING_STATUS_CHECK_SQL, name="ck_advertise_offerings_status"),
        db.CheckConstraint(_ADVERTISE_PRICING_MODE_CHECK_SQL, name="ck_advertise_offerings_pricing_mode"),
        db.CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0", name="ck_advertise_offerings_price_nonnegative"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    short_description = db.Column(db.Text)
    full_description = db.Column(db.Text)
    features = db.Column(db.JSON, nullable=False, default=list)  # list[str]
    cta_label = db.Column(db.String(50))
    display_order = db.Column(db.Integer, nullable=False, default=0)
    featured = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="active")

    pricing_mode = db.Column(db.String(20), nullable=False, default="contact")
    price_amount = db.Column(db.Integer)  # whole currency units, paired with `currency`
    currency = db.Column(db.String(3))  # ISO 4217; no default — never assume USD
    pricing_note = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )
