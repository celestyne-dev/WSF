import uuid as uuid_lib

from app.extensions import db


class Media(db.Model):
    """Metadata + filesystem paths only — never binary image data — for
    files the Flask upload service (app/services/media.py) has written to
    MEDIA_ROOT on the Hostinger VPS. Every content type that carries
    imagery references Media by foreign key, so a single upload can be
    reused and a delete can first check for inbound references.
    """

    __tablename__ = "media"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    public_url = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    original_format = db.Column(db.String(20))
    delivered_format = db.Column(db.String(20))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    file_size = db.Column(db.Integer)
    alt_text = db.Column(db.String(255))
    caption = db.Column(db.String(500))
    credit = db.Column(db.String(255))
    copyright_source = db.Column(db.String(255))
    # `use_alter` breaks the media<->users circular FK (users.avatar_media_id
    # -> media.id) so both tables can be created in a single migration.
    uploaded_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", use_alter=True, name="fk_media_uploaded_by_id"), nullable=True
    )
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])
    variants = db.relationship("MediaVariant", backref="media", cascade="all, delete-orphan")

    def is_referenced(self):
        """Checked before allowing a delete. Each phase that adds a new
        content type carrying a Media FK (Event covers, Resource covers,
        Job/Opportunity logos, Product images, ...) must add its own
        existence check here.
        """
        from app.models.article import Article
        from app.models.commerce import Product
        from app.models.opportunity import Event, EventSpeaker, EventSponsor, Job, Opportunity
        from app.models.page import Page
        from app.models.people import Author, Organization, Person
        from app.models.resource import Resource
        from app.models.taxonomy import Series, Topic
        from app.models.user import User

        checks = (
            (User, "avatar_media_id"),
            (Article, "hero_media_id"),
            (Person, "photo_media_id"),
            (Author, "photo_media_id"),
            (Organization, "logo_media_id"),
            (Series, "cover_media_id"),
            (Topic, "hero_media_id"),
            (Page, "hero_media_id"),
            (Job, "logo_media_id"),
            (Opportunity, "logo_media_id"),
            (Event, "cover_media_id"),
            (EventSpeaker, "headshot_media_id"),
            (EventSponsor, "logo_media_id"),
            (Resource, "cover_media_id"),
            (Product, "cover_media_id"),
        )
        return any(model.query.filter_by(**{field: self.id}).first() is not None for model, field in checks)

    def variant_url(self, name):
        for variant in self.variants:
            if variant.variant == name:
                return variant.public_url
        return None


class MediaVariant(db.Model):
    __tablename__ = "media_variants"

    id = db.Column(db.Integer, primary_key=True)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id", ondelete="CASCADE"), nullable=False)
    variant = db.Column(db.String(20), nullable=False)  # thumbnail/card/medium/large/hero
    file_path = db.Column(db.String(500), nullable=False)
    public_url = db.Column(db.String(500), nullable=False)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    file_size = db.Column(db.Integer)

    __table_args__ = (db.UniqueConstraint("media_id", "variant", name="uq_media_variant"),)
