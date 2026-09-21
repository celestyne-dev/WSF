from app.extensions import db


class Resource(db.Model):
    __tablename__ = "resources"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    type = db.Column(db.String(50))  # Guide / Template / Worksheet / Course / Ebook
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=True)

    price = db.Column(db.Integer, nullable=False, default=0)  # whole currency units, paired with `currency`
    currency = db.Column(db.String(3), nullable=False, default="USD")
    is_premium = db.Column(db.Boolean, nullable=False, default=False)
    is_downloadable = db.Column(db.Boolean, nullable=False, default=True)
    is_external = db.Column(db.Boolean, nullable=False, default=False)
    # The downloadable asset itself isn't run through the image Media
    # pipeline (it's usually a PDF/doc, not an image) — just a VPS path or
    # external URL, whichever `is_external` says to use.
    file_url = db.Column(db.String(500))
    external_url = db.Column(db.String(500))

    featured = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="published")

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])
    topic = db.relationship("Topic", foreign_keys=[topic_id])
    author = db.relationship("Author", foreign_keys=[author_id])
