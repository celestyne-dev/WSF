"""Learning: Learning Paths, skills, final assessment, Lifetime override.

learning_programs
  * skills (JSON list[str], nullable) - "Skills you'll build".
  * lifetime_access (varchar, default 'default') - Studio override for WSF
    Lifetime inclusion: default | included | excluded. Forced exclusions
    (partner provider, external, non-digital product) always win; see
    app/services/learning_access.py.
  * final_assessment (JSON list, nullable), final_assessment_required
    (bool, default false), final_assessment_passing_score (int, default
    70, 1..100). With no questions or required=false the existing
    completion rule (all lessons complete) is unchanged.
learning_enrollments
  * final_assessment_best_score (int, nullable), final_assessment_passed_at
    (timestamptz, nullable) - the learner's own best result; attempts are
    not stored individually.
learning_paths + learning_path_programs (new)
  * A Learning Path is an ordered, curated set of existing Learning
    Programs (a guided career journey). Duration and progress are derived,
    never stored. career_goal reuses the Topic career-goal vocabulary.

Every new column is nullable or has a server default, so existing rows
need no backfill and nothing is rewritten. Downgrade drops exactly what
upgrade adds.

Revision ID: a7d3c9e1f5b2
Revises: f6c9e1a3b5d7
"""
from alembic import op
import sqlalchemy as sa

revision = "a7d3c9e1f5b2"
down_revision = "f6c9e1a3b5d7"
branch_labels = None
depends_on = None

_GOALS = ("find_a_job", "get_promoted", "earn_more", "build_visibility", "leadership", "career_change",
          "return_to_work", "networking", "workplace_challenges", "productivity", "confidence",
          "ai_at_work", "entrepreneurship")
_DIFFICULTY = ("beginner", "intermediate", "advanced", "all_levels")
_STATUSES = ("draft", "review", "published", "archived")


def _in(column, values, nullable=False):
    listed = ", ".join(f"'{v}'" for v in values)
    return f"{column} IS NULL OR {column} IN ({listed})" if nullable else f"{column} IN ({listed})"


def upgrade():
    op.add_column("learning_programs", sa.Column("skills", sa.JSON(), nullable=True))
    op.add_column("learning_programs", sa.Column("lifetime_access", sa.String(10), nullable=False, server_default="default"))
    op.add_column("learning_programs", sa.Column("final_assessment", sa.JSON(), nullable=True))
    op.add_column("learning_programs", sa.Column("final_assessment_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("learning_programs", sa.Column("final_assessment_passing_score", sa.Integer(), nullable=False, server_default="70"))
    op.create_check_constraint("ck_learning_programs_lifetime_access", "learning_programs",
                               _in("lifetime_access", ("default", "included", "excluded")))
    op.create_check_constraint("ck_learning_programs_passing_score", "learning_programs",
                               "final_assessment_passing_score BETWEEN 1 AND 100")

    op.add_column("learning_enrollments", sa.Column("final_assessment_best_score", sa.Integer(), nullable=True))
    op.add_column("learning_enrollments", sa.Column("final_assessment_passed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "learning_paths",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subtitle", sa.String(300), nullable=True),
        sa.Column("description", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("career_goal", sa.String(30), nullable=True),
        sa.Column("difficulty_level", sa.String(20), nullable=True),
        sa.Column("hero_media_id", sa.Integer(), sa.ForeignKey("media.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seo", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(_in("career_goal", _GOALS, nullable=True), name="ck_learning_paths_career_goal"),
        sa.CheckConstraint(_in("difficulty_level", _DIFFICULTY, nullable=True), name="ck_learning_paths_difficulty"),
        sa.CheckConstraint(_in("status", _STATUSES), name="ck_learning_paths_status"),
    )
    op.create_index("ix_learning_paths_slug", "learning_paths", ["slug"], unique=True)
    op.create_index("ix_learning_paths_status", "learning_paths", ["status"])
    op.create_index("ix_learning_paths_career_goal", "learning_paths", ["career_goal"])

    op.create_table(
        "learning_path_programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("learning_path_id", sa.Integer(), sa.ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learning_program_id", sa.Integer(), sa.ForeignKey("learning_programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("learning_path_id", "learning_program_id", name="uq_learning_path_programs_path_program"),
    )
    op.create_index("ix_learning_path_programs_learning_path_id", "learning_path_programs", ["learning_path_id"])
    op.create_index("ix_learning_path_programs_learning_program_id", "learning_path_programs", ["learning_program_id"])


def downgrade():
    op.drop_index("ix_learning_path_programs_learning_program_id", table_name="learning_path_programs")
    op.drop_index("ix_learning_path_programs_learning_path_id", table_name="learning_path_programs")
    op.drop_table("learning_path_programs")
    op.drop_index("ix_learning_paths_career_goal", table_name="learning_paths")
    op.drop_index("ix_learning_paths_status", table_name="learning_paths")
    op.drop_index("ix_learning_paths_slug", table_name="learning_paths")
    op.drop_table("learning_paths")
    op.drop_column("learning_enrollments", "final_assessment_passed_at")
    op.drop_column("learning_enrollments", "final_assessment_best_score")
    op.drop_constraint("ck_learning_programs_passing_score", "learning_programs", type_="check")
    op.drop_constraint("ck_learning_programs_lifetime_access", "learning_programs", type_="check")
    op.drop_column("learning_programs", "final_assessment_passing_score")
    op.drop_column("learning_programs", "final_assessment_required")
    op.drop_column("learning_programs", "final_assessment")
    op.drop_column("learning_programs", "lifetime_access")
    op.drop_column("learning_programs", "skills")
