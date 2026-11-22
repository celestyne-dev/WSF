"""Editorial platform: article provenance, topic hubs, new homepage modules.

- article_experts: structured Reviewed by / Fact checked by / Expert
  contribution rows, each referencing an existing Author or Person.
- articles.editorial_updated_at: the editor-recorded "Updated" date
  (never derived from updated_at). Nullable; existing rows stay NULL.
- topic_related_topics: explicit related-topic links for Topic hubs.
- topics.hub: Topic hub curation (Start here / Editor's picks slugs).
  Existing rows get {}.
- homepage_modules type check widened for the new module types.

Nothing existing is rewritten. Downgrade refuses to run (and changes
nothing) while any homepage module of a new type exists; it never deletes
or converts editor configuration.

Revision ID: c9f1e3a5b7d2
Revises: b8e4d2f6a1c3
"""
from alembic import op
import sqlalchemy as sa

revision = "c9f1e3a5b7d2"
down_revision = "b8e4d2f6a1c3"
branch_labels = None
depends_on = None

_OLD_TYPES = (
    "hero", "featured_stories", "latest_stories", "featured_woman", "series_feature", "topic_collection",
    "opportunities", "jobs", "events", "resources", "newsletter", "partners", "community_cta", "mentorship_cta",
    "editorial_callout", "sponsor_placement", "career_pathways", "content_collection",
)
_NEW_TYPES = _OLD_TYPES + (
    "career_moves", "right_now", "expert_guidance", "community_stories", "handpicked", "people_spotlight",
    "learning", "mission",
)


def _type_check(types):
    return "type IN (" + ", ".join(f"'{t}'" for t in types) + ")"


def upgrade():
    op.create_table(
        "article_experts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("authors.id", ondelete="CASCADE"), nullable=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("role IN ('reviewed_by', 'fact_checked_by', 'expert_contributor')", name="ck_article_experts_role"),
        sa.CheckConstraint("(author_id IS NULL) <> (person_id IS NULL)", name="ck_article_experts_one_profile"),
    )
    op.create_index("ix_article_experts_article_id", "article_experts", ["article_id"])
    op.add_column("articles", sa.Column("editorial_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "topic_related_topics",
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("related_topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("topic_id <> related_topic_id", name="ck_topic_related_topics_not_self"),
    )
    op.add_column("topics", sa.Column("hub", sa.JSON(), nullable=False, server_default="{}"))
    op.drop_constraint("ck_homepage_modules_type", "homepage_modules", type_="check")
    op.create_check_constraint("ck_homepage_modules_type", "homepage_modules", _type_check(_NEW_TYPES))


class NewHomepageModulesExist(RuntimeError):
    pass


def downgrade():
    # Rollback guard: never delete or rewrite editor configuration. Homepage
    # modules of the new types cannot satisfy the old type check, so while
    # any exist the downgrade stops BEFORE changing anything, and an editor
    # removes or exports them intentionally first.
    new_types = _NEW_TYPES[len(_OLD_TYPES):]
    rows = op.get_bind().execute(
        sa.text("SELECT id, type FROM homepage_modules WHERE type IN :types ORDER BY id").bindparams(
            sa.bindparam("types", expanding=True)),
        {"types": list(new_types)},
    ).fetchall()
    if rows:
        listed = ", ".join(f"#{row.id} ({row.type})" for row in rows)
        raise NewHomepageModulesExist(
            "Downgrade stopped: these homepage modules use types introduced by revision c9f1e3a5b7d2 "
            f"and would violate the older module-type rule: {listed}. Remove or export them in Studio "
            "(Homepage Builder) deliberately, then run the downgrade again. Nothing was changed."
        )
    op.drop_constraint("ck_homepage_modules_type", "homepage_modules", type_="check")
    op.create_check_constraint("ck_homepage_modules_type", "homepage_modules", _type_check(_OLD_TYPES))
    op.drop_column("topics", "hub")
    op.drop_table("topic_related_topics")
    op.drop_column("articles", "editorial_updated_at")
    op.drop_index("ix_article_experts_article_id", table_name="article_experts")
    op.drop_table("article_experts")
