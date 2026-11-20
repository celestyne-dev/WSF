"""Derived, never-stored facts about a Learning Program's curriculum,
shared by the public list, the detail page, Learning Paths and the
server prerender:

  * moduleCount / lessonCount
  * totalMinutes — the sum of lesson duration_minutes where editors set
    them (null when no lesson has a duration; the Program's own
    duration_value/unit stays the editor-facing "estimated time")
  * format — derived from lesson types, so editors never maintain a
    second, manual truth:
        no lessons                         -> None (no label shown)
        no video/recording lessons         -> "text"      ("Text-based")
        video/recording >= 75% of lessons  -> "video_led" ("Video-led")
        otherwise                          -> "mixed"     ("Mixed format")
    text, activity, article, resource and external_link lessons all count
    as reading/doing (non-video) lessons.

`catalog_stats(ids)` is ONE grouped query for any number of programs (list
pages never load lesson bodies); `program_stats(program)` reuses the
already-loaded modules on a detail page.
"""
from sqlalchemy import case, func

from app.extensions import db
from app.models.learning import VIDEO_LESSON_TYPES, LearningLesson, LearningModule

FORMAT_LABELS = {"text": "Text-based", "mixed": "Mixed format", "video_led": "Video-led"}
VIDEO_LED_SHARE = 0.75


def derive_format(lesson_count, video_count):
    if not lesson_count:
        return None
    if not video_count:
        return "text"
    if video_count / lesson_count >= VIDEO_LED_SHARE:
        return "video_led"
    return "mixed"


def _stats(module_count, lesson_count, video_count, minutes):
    fmt = derive_format(lesson_count, video_count)
    return {
        "moduleCount": module_count,
        "lessonCount": lesson_count,
        "videoLessonCount": video_count,
        "totalMinutes": minutes or None,
        "format": fmt,
        "formatLabel": FORMAT_LABELS.get(fmt),
    }


EMPTY_STATS = _stats(0, 0, 0, None)


def catalog_stats(program_ids):
    """{program_id: stats} for many programs in one grouped query."""
    ids = [i for i in set(program_ids or []) if i is not None]
    if not ids:
        return {}
    is_video = case((LearningLesson.lesson_type.in_(VIDEO_LESSON_TYPES), 1), else_=0)
    rows = (
        db.session.query(
            LearningModule.learning_program_id,
            func.count(func.distinct(LearningModule.id)),
            func.count(LearningLesson.id),
            func.coalesce(func.sum(is_video), 0),
            func.sum(LearningLesson.duration_minutes),
        )
        .outerjoin(LearningLesson, LearningLesson.module_id == LearningModule.id)
        .filter(LearningModule.learning_program_id.in_(ids))
        .group_by(LearningModule.learning_program_id)
        .all()
    )
    out = {i: dict(EMPTY_STATS) for i in ids}
    for program_id, modules, lessons, videos, minutes in rows:
        out[program_id] = _stats(int(modules), int(lessons), int(videos), int(minutes) if minutes else None)
    return out


def program_stats(program):
    lessons = [lesson for module in program.modules for lesson in module.lessons]
    videos = sum(1 for lesson in lessons if lesson.lesson_type in VIDEO_LESSON_TYPES)
    minutes = sum(lesson.duration_minutes or 0 for lesson in lessons)
    return _stats(len(program.modules), len(lessons), videos, minutes or None)


def module_stats(module):
    return {
        "lessonCount": len(module.lessons),
        "totalMinutes": sum(lesson.duration_minutes or 0 for lesson in module.lessons) or None,
    }


def ordered_lesson_ids(program):
    return [lesson.id for module in program.modules for lesson in module.lessons]


def next_lesson_id(program, completed_ids):
    """The first lesson (curriculum order) not yet completed, or None."""
    done = set(completed_ids or [])
    return next((lesson_id for lesson_id in ordered_lesson_ids(program) if lesson_id not in done), None)


def program_ids_with_format(fmt):
    """Subquery of program ids whose DERIVED format is `fmt` (same rule as
    derive_format), for the public "Format" filter."""
    is_video = case((LearningLesson.lesson_type.in_(VIDEO_LESSON_TYPES), 1), else_=0)
    lessons = func.count(LearningLesson.id)
    videos = func.coalesce(func.sum(is_video), 0)
    query = (
        db.session.query(LearningModule.learning_program_id)
        .join(LearningLesson, LearningLesson.module_id == LearningModule.id)
        .group_by(LearningModule.learning_program_id)
    )
    if fmt == "text":
        return query.having(videos == 0)
    if fmt == "video_led":
        return query.having(videos >= lessons * VIDEO_LED_SHARE)
    if fmt == "mixed":
        return query.having(videos > 0, videos < lessons * VIDEO_LED_SHARE)
    return None
