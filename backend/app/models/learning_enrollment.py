"""First-party WSF learner enrollment for a `free`- or `circle_only`-
access LearningProgram (see app/services/learning_enrollments.py). An
`external` or `product` program never gets a row here — see that
module's own docstring for why.

One lifecycle row per (program, user): withdrawing and later
re-enrolling reactivates the SAME row rather than creating a new one, so
a learner's lesson progress is preserved across a withdrawal. Unlike
EventRegistration's three-state `status`, completion is NOT a stored
lifecycle status — it is represented by `completed_at != null` so an
enrollment is never in an ambiguous "active and completed" vs
"completed but somehow also withdrawn" double-state; the only stored
`status` values are `active`/`withdrawn`, and completion layers on top
of `active` via the timestamp alone.
"""
from app.extensions import db

LEARNING_ENROLLMENT_STATUSES = ("active", "withdrawn")
_LEARNING_ENROLLMENT_STATUS_CHECK_SQL = (
    "status IN (" + ", ".join(f"'{s}'" for s in LEARNING_ENROLLMENT_STATUSES) + ")"
)


class LearningEnrollment(db.Model):
    __tablename__ = "learning_enrollments"
    __table_args__ = (
        db.CheckConstraint(_LEARNING_ENROLLMENT_STATUS_CHECK_SQL, name="ck_learning_enrollments_status"),
        # One lifecycle row per (program, user) — see module docstring.
        db.UniqueConstraint("learning_program_id", "user_id", name="uq_learning_enrollments_program_user"),
        # "This user's enrollments" (GET /learning-enrollments/me, /check).
        db.Index("ix_learning_enrollments_user_status", "user_id", "status"),
        # "This program's learners" (admin enrollments list).
        db.Index("ix_learning_enrollments_program_status", "learning_program_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    learning_program_id = db.Column(
        db.Integer, db.ForeignKey("learning_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    enrolled_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    withdrawn_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    learning_program = db.relationship("LearningProgram", foreign_keys=[learning_program_id])
    user = db.relationship("User", foreign_keys=[user_id])
    lesson_progress = db.relationship(
        "LearningLessonProgress", cascade="all, delete-orphan", backref="enrollment"
    )


class LearningLessonProgress(db.Model):
    """A row means "this lesson is currently marked complete" — presence
    alone is the signal (spec: "do not store duplicate booleans and
    completion rows"). Deleting the row (rather than storing a boolean
    `completed=False`) is how "mark incomplete" is represented.
    """

    __tablename__ = "learning_lesson_progress"
    __table_args__ = (
        # One completion row per (enrollment, lesson) — also the
        # idempotency/race-safety net behind POST .../complete.
        db.UniqueConstraint("enrollment_id", "lesson_id", name="uq_learning_lesson_progress_enrollment_lesson"),
    )

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey("learning_enrollments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id = db.Column(
        db.Integer, db.ForeignKey("learning_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    completed_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    lesson = db.relationship("LearningLesson", foreign_keys=[lesson_id])
