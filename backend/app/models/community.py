from app.extensions import db

# reviewing -> accepted / declined
REVIEW_STATUSES = ("new", "reviewing", "accepted", "declined")


class StorySubmission(db.Model):
    __tablename__ = "story_submissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    excerpt = db.Column(db.Text)
    body = db.Column(db.Text)  # the full pitch/draft, if provided
    status = db.Column(db.String(20), nullable=False, default="new")
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])


class Nomination(db.Model):
    __tablename__ = "nominations"

    id = db.Column(db.Integer, primary_key=True)
    nominee_name = db.Column(db.String(200), nullable=False)
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    profession = db.Column(db.String(200))
    organization = db.Column(db.String(200))
    achievements = db.Column(db.Text)
    nominator_name = db.Column(db.String(200), nullable=False)
    nominator_email = db.Column(db.String(255), nullable=False)
    relationship_to_nominee = db.Column(db.String(200))
    category = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default="new")
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
