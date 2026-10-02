"""Private "save for later" bookmarks for a public WSF account (see
app/services/saved_items.py). One polymorphic table across every
supported content type, rather than six separate bookmark tables — the
row never carries the saved entity's own data, only a pointer
(content_type, content_id) that is re-validated against that entity's
own current public visibility rules on every read (see
app/services/saved_items.py's per-type fetchers).

This is entirely separate from, and never creates or touches, a
Community Member record (app/models/community.py) — saving content is a
WSF account feature, not a Community-membership one.
"""
from app.extensions import db

SAVED_CONTENT_TYPES = ("article", "job", "opportunity", "resource", "event", "learning_program")
_CONTENT_TYPE_CHECK_SQL = "content_type IN (" + ", ".join(f"'{t}'" for t in SAVED_CONTENT_TYPES) + ")"


class SavedItem(db.Model):
    __tablename__ = "saved_items"
    __table_args__ = (
        db.CheckConstraint(_CONTENT_TYPE_CHECK_SQL, name="ck_saved_items_content_type"),
        # Prevents a duplicate bookmark outright (also the race-safety net
        # behind the idempotent POST /saved — see api/v1/saved.py, which
        # catches the resulting IntegrityError rather than pre-checking
        # and still racing another request).
        db.UniqueConstraint("user_id", "content_type", "content_id", name="uq_saved_items_user_content"),
        # The one real access pattern this table serves: "this user's
        # saved items, newest first" (GET /saved, optionally filtered by
        # content_type) — a leftmost prefix of this index covers both the
        # filtered and unfiltered case, so no second index is needed.
        db.Index("ix_saved_items_user_type_created", "user_id", "content_type", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content_type = db.Column(db.String(30), nullable=False)
    content_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
