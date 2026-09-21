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
