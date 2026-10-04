from datetime import date

from app.extensions import db

RESOURCE_TYPES = (
    "Guide",
    "Workbook",
    "Template",
    "Checklist",
    "Planner",
    "Toolkit",
    "Ebook",
    "Worksheet",
    "Report",
    "Download",
    "Video Resource",
    "External Resource",
)
_RESOURCE_TYPE_CHECK_SQL = "type IS NULL OR type IN (" + ", ".join(f"'{t}'" for t in RESOURCE_TYPES) + ")"

# draft: incomplete/unpublished. review: submitted, awaiting editorial
# approval. scheduled: approved, with published_date set in the future —
# becomes publicly visible automatically once that date arrives (same
# pattern as Job/Event). published: live and publicly listed. archived:
# retained for record, hidden from any public listing.
RESOURCE_STATUSES = ("draft", "review", "scheduled", "published", "archived")
_RESOURCE_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in RESOURCE_STATUSES) + ")"

# The single field that actually drives how a visitor gets the resource.
# is_premium/is_downloadable/is_external (kept below for the handful of
# existing call sites built against them) are derived from this at write
# time rather than being independently editable — one status an editor
# sets, not several that could disagree. See app/services/resource_access.py
# for the one place every one of these rules is actually enforced — this
# module only declares the allowed values.
#   direct_download: free, no gate — the button just works.
#   email_gate: free, but first name/email (+ consent) is captured before
#     the file is handed over — the lead-magnet flow.
#   member_only: any valid authenticated WSF account (User) — not a
#     Community membership, not WSF Circle. WSF accounts exist now, so
#     this is a real gate, not a placeholder.
#   circle_only: requires an active WSF Circle entitlement (see
#     app/services/circle.py's has_circle_access — the one authoritative
#     check; never re-derived here).
#   premium: has a real price; no payment processing exists yet, so the
#     public CTA is an honest "coming soon" rather than a working
#     checkout (same posture the Shop's Product model already takes). A
#     WSF Circle membership does NOT unlock a premium resource — Circle
#     and one-off resource purchase are deliberately separate commercial
#     concepts.
#   external_link: hosted elsewhere — the CTA sends the visitor off-site.
ACCESS_TYPES = ("direct_download", "email_gate", "member_only", "circle_only", "premium", "external_link")
_ACCESS_TYPE_CHECK_SQL = "access_type IN (" + ", ".join(f"'{a}'" for a in ACCESS_TYPES) + ")"

FILE_FORMATS = ("PDF", "DOCX", "XLSX", "PPTX", "ZIP", "Image", "Video", "Other")
_FILE_FORMAT_CHECK_SQL = "file_format IS NULL OR file_format IN (" + ", ".join(f"'{f}'" for f in FILE_FORMATS) + ")"

resource_topics = db.Table(
    "resource_topics",
    db.Column("resource_id", db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)

resource_tags = db.Table(
    "resource_tags",
    db.Column("resource_id", db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class ResourceImage(db.Model):
    """An ordered supplementary preview image for a Resource, beyond its
    single `cover_media` — same association-object pattern as
    commerce.ProductImage.
    """

    __tablename__ = "resource_images"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    media = db.relationship("Media", foreign_keys=[media_id])


class Resource(db.Model):
    """A downloadable/accessible piece of content — the free-lead-magnet
    and (eventually) paid-digital-product side of WSF's editorial output.
    `resource_id` on commerce.Product already lets a Product wrap a
    Resource for an actual Shop listing/checkout later; nothing new is
    needed here to "prepare" that relationship — it already exists.
    """

    __tablename__ = "resources"
    __table_args__ = (
        db.CheckConstraint(_RESOURCE_TYPE_CHECK_SQL, name="ck_resources_type"),
        db.CheckConstraint(_RESOURCE_STATUS_CHECK_SQL, name="ck_resources_status"),
        db.CheckConstraint(_ACCESS_TYPE_CHECK_SQL, name="ck_resources_access_type"),
        db.CheckConstraint(_FILE_FORMAT_CHECK_SQL, name="ck_resources_file_format"),
        db.CheckConstraint("price >= 0", name="ck_resources_price_nonnegative"),
        db.CheckConstraint("download_count >= 0", name="ck_resources_download_count_nonnegative"),
        db.CheckConstraint("page_count IS NULL OR page_count >= 0", name="ck_resources_page_count_nonnegative"),
        db.CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_resources_file_size_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(300))
    short_description = db.Column(db.Text)  # one or two sentences, for cards
    # Ordered content-block list — same shape/sanitizer/editor as every
    # other content type in this app. The editor structures "What's
    # included", "Who it's for", "Benefits", "How to use it" etc.
    # themselves rather than the app hard-coding those sections.
    description = db.Column(db.JSON, nullable=False, default=list)

    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    type = db.Column(db.String(50))  # see RESOURCE_TYPES
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=True)
    author_name = db.Column(db.String(200))  # denormalized fallback when no Author is linked

    price = db.Column(db.Integer, nullable=False, default=0)  # whole currency units, paired with `currency`
    currency = db.Column(db.String(3), nullable=False, default="USD")
    is_premium = db.Column(db.Boolean, nullable=False, default=False)
    is_downloadable = db.Column(db.Boolean, nullable=False, default=True)
    is_external = db.Column(db.Boolean, nullable=False, default=False)

    access_type = db.Column(db.String(20), nullable=False, default="direct_download")
    # The downloadable asset itself isn't run through the image Media
    # pipeline (it's usually a PDF/doc, not an image) — just this app's
    # own MEDIA_URL-rooted path or an http(s) URL, whichever `is_external`
    # says to use (see app/utils/urls.py's is_safe_resource_target, the
    # one place both are validated — never a raw filesystem path, never
    # javascript:/data:/file:). No generic binary-file upload/storage
    # pipeline exists yet (Media only handles images); building one is out
    # of this task's scope — see the final report. Never serialized to an
    # anonymous/public caller directly (see app/schemas/resource.py's
    # build_public_resource_payload) — only POST /resources/{slug}/access,
    # after the resource's access_type rule succeeds, ever hands this back.
    file_url = db.Column(db.String(500))
    external_url = db.Column(db.String(500))
    file_format = db.Column(db.String(20))  # see FILE_FORMATS
    file_size = db.Column(db.Integer)  # bytes
    page_count = db.Column(db.Integer)

    sponsor_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    sponsored = db.Column(db.Boolean, nullable=False, default=False)

    download_count = db.Column(db.Integer, nullable=False, default=0)

    featured = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    published_date = db.Column(db.Date)
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])
    author = db.relationship("Author", foreign_keys=[author_id])
    sponsor = db.relationship("Organization", foreign_keys=[sponsor_id])
    topics = db.relationship("Topic", secondary=resource_topics, backref="resources")
    tags = db.relationship("Tag", secondary=resource_tags, backref="resources")
    images = db.relationship(
        "ResourceImage", order_by="ResourceImage.position", cascade="all, delete-orphan", backref="resource"
    )

    def is_publicly_visible(self):
        """The ONE rule for whether an anonymous/ordinary visitor may see
        this resource at all — reused by the public list, public detail,
        and /access endpoints so a future-dated scheduled resource can
        never be reached early through any of the three. A resource whose
        `published_date` is None is never treated as "past due" — it's
        simply not eligible via the scheduled branch (status must be
        flipped to "published" directly for it to become visible).
        """
        if self.status == "published":
            return True
        return self.status == "scheduled" and self.published_date is not None and self.published_date <= date.today()


class ResourceLead(db.Model):
    """One email-gate submission — the record a "Download Free Guide ->
    enter your email" flow produces. Kept separate from the general
    AnalyticsEvent stream (trackEvent) because this genuinely is a
    business record (a lead, with consent), not an ephemeral interaction
    event; view/click tracking for Resources still goes through the
    existing analytics architecture, not this table.
    """

    __tablename__ = "resource_leads"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    # Consent to be added to the newsletter list — a download is never
    # forced to also become a subscription.
    newsletter_consent = db.Column(db.Boolean, nullable=False, default=False)
    acquisition = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    resource = db.relationship("Resource", foreign_keys=[resource_id])
    country = db.relationship("Country", foreign_keys=[country_code])
