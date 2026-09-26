from app.extensions import db

# Controlled homepage module registry — the single source of truth the
# frontend (HomePage.jsx's MODULE_COMPONENTS, AdminHomepageBuilder's "Add
# section" menu) and backend (HomepageModuleInputSchema) both key off of.
# Adding a new module type means adding it here, not accepting arbitrary
# strings from an admin request. "hero" is a singleton — everything else
# may repeat (e.g. two editorial_callout modules in different positions).
HOMEPAGE_MODULE_TYPES = (
    "hero",
    "featured_stories",
    "latest_stories",
    "featured_woman",
    "series_feature",
    "topic_collection",
    "opportunities",
    "jobs",
    "events",
    "resources",
    "newsletter",
    "partners",
    "community_cta",
    "mentorship_cta",
    "editorial_callout",
    "sponsor_placement",
)
_HOMEPAGE_MODULE_TYPE_CHECK_SQL = "type IN (" + ", ".join(f"'{t}'" for t in HOMEPAGE_MODULE_TYPES) + ")"

HOMEPAGE_SINGLETON_TYPES = frozenset({"hero"})

# (min, max) allowed values for config.itemCount, per type — keeps the
# public layout from being asked to render 200 cards. Types absent here
# either don't take an item count (hero/newsletter/partners/*_cta/
# sponsor_placement) or aren't bounded (none, currently).
HOMEPAGE_MODULE_ITEM_COUNT_BOUNDS = {
    "featured_stories": (1, 8),
    "latest_stories": (1, 12),
    "series_feature": (1, 6),
    "topic_collection": (1, 6),
    "opportunities": (1, 6),
    "jobs": (1, 6),
    "events": (1, 6),
    "resources": (1, 6),
}

# The only Sponsors-CMS placement key currently wired up for the homepage
# (see components/sponsors/SponsorPlacementStrip.jsx). A controlled list
# (of one, today) rather than a free-text field — Homepage Builder selects
# an approved placement, it never manages sponsor campaign data itself.
HOMEPAGE_SPONSOR_PLACEMENT_KEYS = ("homepage_featured",)


class HomepageModule(db.Model):
    """One row per homepage section, rendered in `sort_order` by the
    frontend's existing per-type components (HeroModule, FeaturedWomanModule,
    ...) — this table is what frontend/src/mock/homepageModules.js stands
    in for. `config` holds whatever fields that module `type` needs
    (leadArticleSlug, personSlug, seriesSlug, itemCount, partnerSlugs, ...)
    since each type's shape is different enough that a fixed column per
    field would mean most rows leave most columns null. `media_id`/
    `cta_label`/`cta_url`/`secondary_cta_*` are real columns rather than
    JSON because they follow the same dedicated-column convention as every
    other hero/CTA-bearing model in this app (AdvertisePage, Page, Person,
    ...), and because `media_id` needs a real FK for Media.is_referenced()
    delete protection to see it.
    """

    __tablename__ = "homepage_modules"
    __table_args__ = (db.CheckConstraint(_HOMEPAGE_MODULE_TYPE_CHECK_SQL, name="ck_homepage_modules_type"),)

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    heading = db.Column(db.String(200))
    subheading = db.Column(db.Text)
    selection_mode = db.Column(db.String(20))  # manual / automatic
    config = db.Column(db.JSON, nullable=False, default=dict)

    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    cta_label = db.Column(db.String(50))
    cta_url = db.Column(db.String(500))
    secondary_cta_label = db.Column(db.String(50))
    secondary_cta_url = db.Column(db.String(500))

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    media = db.relationship("Media", foreign_keys=[media_id])

    def is_singleton(self):
        return self.type in HOMEPAGE_SINGLETON_TYPES


class Menu(db.Model):
    """A named navigation slot: primary, secondary, or one of the footer
    columns (any key prefixed "footer_" — see FOOTER_MENU_KEY_PREFIX in
    services/footer.py; Footer CMS admins can create additional footer_*
    groups beyond the seeded four, so this is a prefix convention, not a
    fixed enum).

    `visible`/`sort_order` only have real meaning for footer groups today
    (primary/secondary are single unordered lists, not a set of orderable,
    hideable groups) — added here rather than a Footer-only table since a
    footer group *is* a Menu row, and duplicating Menu/MenuItem for Footer
    CMS would violate "don't build a second system" (see final report).
    """

    __tablename__ = "menus"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    heading = db.Column(db.String(100))
    visible = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def top_level_items(self):
        return MenuItem.query.filter_by(menu_id=self.id, parent_id=None).order_by(MenuItem.sort_order).all()


# A navigation item's controlled "what does this point at" type. "route" is
# a plain internal path (the pre-existing behavior — `url` stored as-is);
# "topic"/"series"/"page" are entity-aware links (the item stores a FK, not
# a URL, so a slug rename on that entity is reflected automatically and
# never needs a matching Navigation edit — see MenuItem.effective_url());
# "external" is a validated http(s) link; "group" is a non-clickable
# grouping label that exists only to hold children (see MenuItemInputSchema
# for how "must a destination be present" is enforced per type).
MENU_ITEM_TYPES = ("route", "topic", "series", "page", "external", "group")
_MENU_ITEM_TYPE_CHECK_SQL = "item_type IN (" + ", ".join(f"'{t}'" for t in MENU_ITEM_TYPES) + ")"

MENU_ITEM_STYLES = ("standard", "cta")
_MENU_ITEM_STYLE_CHECK_SQL = "style IN (" + ", ".join(f"'{s}'" for s in MENU_ITEM_STYLES) + ")"

# At most one level of nesting (top-level item -> children) — matches the
# depth the current header/mobile-nav components actually render; see
# spec's "avoid enterprise mega-menu recursion" guidance.
MENU_MAX_DEPTH = 2


class MenuItem(db.Model):
    __tablename__ = "menu_items"
    __table_args__ = (
        db.CheckConstraint(_MENU_ITEM_TYPE_CHECK_SQL, name="ck_menu_items_item_type"),
        db.CheckConstraint(_MENU_ITEM_STYLE_CHECK_SQL, name="ck_menu_items_style"),
    )

    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id", ondelete="CASCADE"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=True)
    label = db.Column(db.String(100), nullable=False)
    item_type = db.Column(db.String(20), nullable=False, default="route")
    # Only meaningful for item_type in ("route", "external") — entity types
    # derive their public URL from the referenced row instead (see
    # effective_url()); "group" never has one.
    url = db.Column(db.String(300), nullable=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    series_id = db.Column(db.Integer, db.ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    page_id = db.Column(db.Integer, db.ForeignKey("pages.id", ondelete="SET NULL"), nullable=True)
    open_new_tab = db.Column(db.Boolean, nullable=False, default=False)
    style = db.Column(db.String(20), nullable=False, default="standard")
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
    topic = db.relationship("Topic", foreign_keys=[topic_id])
    series = db.relationship("Series", foreign_keys=[series_id])
    page = db.relationship("Page", foreign_keys=[page_id])

    def linked_entity(self):
        return {"topic": self.topic, "series": self.series, "page": self.page}.get(self.item_type)

    def is_entity_public(self):
        """Whether the item's linked entity (if any) is currently public.
        Route/external/group items have no entity to check, so they're
        always considered eligible here — safety for those is enforced at
        input-validation time instead (see services/navigation.py).
        """
        entity = self.linked_entity()
        if entity is None:
            return True
        return entity.status == "published"

    def effective_url(self):
        """The real URL this item points to right now. Entity-typed items
        never store their own URL — this always reflects that entity's
        CURRENT slug, so renaming a Topic/Series/Page slug in its own CMS
        automatically repoints every nav item that links to it, with no
        Navigation edit required (see spec's "label/route are separate
        concepts" requirement).
        """
        if self.item_type == "topic":
            return f"/topics/{self.topic.slug}" if self.topic else None
        if self.item_type == "series":
            return f"/series/{self.series.slug}" if self.series else None
        if self.item_type == "page":
            return f"/{self.page.slug}" if self.page else None
        if self.item_type == "group":
            return None
        return self.url


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


# Controlled platform keys, mirrored by the frontend's SocialIcon map — an
# admin picks one of these from a <select>, never types a component name
# or uploads an arbitrary icon (spec: "do not allow admins to type
# arbitrary component names... do not upload social icons as random
# images"). "twitter" is kept alongside the platforms the spec names since
# WSF already has a twitter/X icon and a seeded handle for it.
SOCIAL_PLATFORMS = (
    "linkedin",
    "instagram",
    "facebook",
    "tiktok",
    "threads",
    "pinterest",
    "youtube",
    "whatsapp",
    "twitter",
)
_SOCIAL_LINK_PLATFORM_CHECK_SQL = "platform IN (" + ", ".join(f"'{p}'" for p in SOCIAL_PLATFORMS) + ")"


class SocialLink(db.Model):
    __tablename__ = "social_links"
    __table_args__ = (db.CheckConstraint(_SOCIAL_LINK_PLATFORM_CHECK_SQL, name="ck_social_links_platform"),)

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(30), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    handle = db.Column(db.String(100))
    # Accessible-name override (spec: "Women Shaping Futures on LinkedIn"
    # rather than icon-only ambiguity) — falls back to a computed default
    # from `platform` when blank; see build_public_footer() in
    # services/footer.py.
    label = db.Column(db.String(150))
    visible = db.Column(db.Boolean, nullable=False, default=True)
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
