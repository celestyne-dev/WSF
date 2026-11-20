"""WSF Learning Paths: guided career journeys made of existing Programs.

Everything shown about a path is DERIVED from its ordered Programs at read
time — never stored:
  * courses: only the path's PUBLISHED programs are public (a draft or
    archived program silently drops out of the public path);
  * totalMinutes: the sum of the published programs' lesson minutes
    (null when none is known);
  * lifetimeIncluded: true only when every published program is WSF
    Lifetime eligible (app/services/learning_access.py);
  * viewer progress (signed-in learner only, her own enrollments):
    completed / in progress / not started per course, overall percent
    across the courses' lessons, and the next recommended course (the
    first, in path order, that is not complete).
A path never issues its own certificate — certificates stay course-level.

Career goal recommendations are deterministic (not AI): published paths
whose career_goal is one of the learner's saved Career Hub goals, featured
first, then newest.
"""
from app.extensions import db
from app.models.learning import LearningPath, LearningPathProgram, LearningProgram
from app.models.learning_enrollment import LearningEnrollment
from app.services.learning_access import is_lifetime_eligible_program
from app.services.learning_catalog import catalog_stats

PUBLIC_STATUS = "published"


def published_programs(path):
    return [link.program for link in path.program_links if link.program is not None and link.program.status == PUBLIC_STATUS]


def path_facts(path, stats=None):
    programs = published_programs(path)
    stats = stats if stats is not None else catalog_stats([p.id for p in programs])
    minutes = sum((stats.get(p.id) or {}).get("totalMinutes") or 0 for p in programs)
    lessons = sum((stats.get(p.id) or {}).get("lessonCount") or 0 for p in programs)
    return {
        "courseCount": len(programs),
        "lessonCount": lessons,
        "totalMinutes": minutes or None,
        "lifetimeIncluded": bool(programs) and all(is_lifetime_eligible_program(p) for p in programs),
    }


def viewer_path_progress(path, user):
    """The signed-in learner's derived progress through a path, or None
    for an anonymous viewer. Reads only her own enrollments."""
    if user is None:
        return None
    programs = published_programs(path)
    if not programs:
        return None
    from app.services.learning_enrollments import progress_summary

    enrollments = {
        e.learning_program_id: e
        for e in LearningEnrollment.query.filter(
            LearningEnrollment.user_id == user.id,
            LearningEnrollment.learning_program_id.in_([p.id for p in programs]),
        ).all()
    }
    courses, done_lessons, total_lessons = [], 0, 0
    next_program = None
    for program in programs:
        enrollment = enrollments.get(program.id)
        summary = progress_summary(enrollment, program) if enrollment else None
        if enrollment is not None and enrollment.status == "active" and enrollment.completed_at is not None:
            state = "completed"
        elif enrollment is not None and enrollment.status == "active":
            state = "in_progress"
        else:
            state = "not_started"
        lesson_total = summary["total_lessons"] if summary else len([l for m in program.modules for l in m.lessons])
        lesson_done = lesson_total if state == "completed" else (summary["completed_lessons"] if summary and state == "in_progress" else 0)
        total_lessons += lesson_total
        done_lessons += lesson_done
        if next_program is None and state != "completed":
            next_program = program
        courses.append({"programId": program.id, "slug": program.slug, "state": state,
                        "progressPercent": 100 if state == "completed" else (summary["progress_percent"] if summary and state == "in_progress" else 0)})
    completed = sum(1 for c in courses if c["state"] == "completed")
    return {
        "completedCourses": completed,
        "inProgressCourses": sum(1 for c in courses if c["state"] == "in_progress"),
        "totalCourses": len(courses),
        "progressPercent": round(100 * done_lessons / total_lessons) if total_lessons else (100 if completed == len(courses) else 0),
        "nextProgramSlug": next_program.slug if next_program is not None else None,
        "courses": courses,
    }


def public_paths_query():
    return LearningPath.query.filter(LearningPath.status == PUBLIC_STATUS)


def recommended_paths_for_goals(goals, limit=3):
    goals = [g for g in (goals or []) if isinstance(g, str)]
    if not goals:
        return []
    return (
        public_paths_query()
        .filter(LearningPath.career_goal.in_(goals))
        .order_by(LearningPath.featured.desc(), LearningPath.published_at.desc().nullslast(), LearningPath.id.desc())
        .limit(limit)
        .all()
    )


def paths_containing_program(program_id):
    """Published paths that include this program (for its detail page)."""
    return (
        public_paths_query()
        .join(LearningPathProgram, LearningPathProgram.learning_path_id == LearningPath.id)
        .filter(LearningPathProgram.learning_program_id == program_id)
        .order_by(LearningPath.featured.desc(), LearningPath.title)
        .all()
    )


def set_path_programs(path, program_ids):
    """Replaces the ordered program list (de-duplicated, existing programs
    only — any status, so editors can stage a path before courses ship)."""
    seen, ordered = set(), []
    for pid in program_ids or []:
        if isinstance(pid, int) and not isinstance(pid, bool) and pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    found = {p.id: p for p in LearningProgram.query.filter(LearningProgram.id.in_(ordered)).all()} if ordered else {}
    missing = [pid for pid in ordered if pid not in found]
    if missing:
        from app.utils.responses import ApiError

        raise ApiError("One or more courses were not found.", 404, code="not_found")
    path.program_links.clear()
    db.session.flush()
    for position, pid in enumerate(ordered):
        # Attach the loaded Program (not just its id) so publish validation
        # and the response can read it before the next flush.
        path.program_links.append(LearningPathProgram(program=found[pid], position=position))
