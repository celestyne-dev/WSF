from app.extensions import db


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")  # active / unsubscribed
    # Where on the site they subscribed (footer/homepage/article-inline/...)
    # plus first-touch UTM + LinkedIn-referral attribution — see
    # frontend/src/utils/analytics.js withAcquisitionMetadata, which this
    # column's shape mirrors: {source, utmSource, utmMedium, utmCampaign,
    # referrer, isFromLinkedIn}.
    placement = db.Column(db.String(50))
    acquisition = db.Column(db.JSON)
    subscribed_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    unsubscribed_at = db.Column(db.DateTime(timezone=True))

    country = db.relationship("Country", foreign_keys=[country_code])


class NewsletterIssue(db.Model):
    __tablename__ = "newsletter_issues"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    issue_number = db.Column(db.Integer, nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    send_date = db.Column(db.Date, nullable=False)
    featured_article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=True)
    summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    featured_article = db.relationship("Article", foreign_keys=[featured_article_id])
