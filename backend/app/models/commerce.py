from app.extensions import db


class PartnershipInquiry(db.Model):
    __tablename__ = "partnership_inquiries"

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    interest = db.Column(db.String(200))  # e.g. "Newsletter sponsorship"
    message = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="new")  # new/contacted/won/lost
    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


class Sponsor(db.Model):
    """A currently-active (or scheduled) sponsorship deal — distinct from
    Organization, which is just the company's editorial profile. The same
    Organization can be featured editorially without being a paying
    sponsor, and vice versa.
    """

    __tablename__ = "sponsors"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    tier = db.Column(db.String(50))  # Presenting / Gold / Silver / Community
    active = db.Column(db.Boolean, nullable=False, default=True)
    starts_at = db.Column(db.Date)
    ends_at = db.Column(db.Date)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    organization = db.relationship("Organization", foreign_keys=[organization_id])
