"""Lightweight learning checks — deliberately not an LMS assessment engine.

Knowledge checks live INSIDE lesson content (a `knowledgeCheck` block, up
to 5 questions: single choice, multiple choice or true/false). They give
immediate feedback and NEVER block progress or completion.

The optional final assessment lives on the Program (`final_assessment`, up
to 25 questions of the same shape). It only gates course completion — and
so a Certificate of Completion — when the Program has
`final_assessment_required` AND at least one question. The learner's best
score and first pass time are stored on her enrollment; individual
attempts are not.

Answers never leave the server inside lesson/assessment content (see
content_blocks.public_lesson_content / public_question). A knowledge check
reveals the correct options and explanation for a question only after it
has been answered; the final assessment reveals only right/wrong per
question and the score, never the correct options.
"""
from datetime import datetime, timezone

from app.services.content_blocks import public_question
from app.utils.responses import ApiError


def _selected(answers, question_id):
    value = (answers or {}).get(question_id)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return set()
    return {v for v in value if isinstance(v, str)}


def grade_question(question, answers):
    correct_ids = {o["id"] for o in question.get("options") or [] if o.get("correct")}
    chosen = _selected(answers, question.get("id"))
    return bool(chosen) and chosen == correct_ids, correct_ids, chosen


def lesson_questions(lesson):
    """{question_id: question} across a lesson's knowledgeCheck blocks
    (first occurrence wins if an id repeats)."""
    found = {}
    for block in lesson.content or []:
        if isinstance(block, dict) and block.get("type") == "knowledgeCheck":
            for question in block.get("questions") or []:
                if isinstance(question, dict) and question.get("id") and question["id"] not in found:
                    found[question["id"]] = question
    return found


def check_knowledge_answers(lesson, answers):
    """Immediate feedback for the questions the learner answered (only
    those): correctness, the correct option ids and the explanation."""
    if not isinstance(answers, dict) or not answers:
        raise ApiError("Choose an answer first.", 422, code="validation_error")
    questions = lesson_questions(lesson)
    results = []
    for question_id in answers:
        question = questions.get(question_id)
        if question is None:
            continue
        correct, correct_ids, _ = grade_question(question, answers)
        results.append({
            "questionId": question_id,
            "correct": correct,
            "correctOptionIds": sorted(correct_ids),
            "explanation": question.get("explanation") or None,
        })
    if not results:
        raise ApiError("Those questions are not part of this lesson.", 422, code="validation_error")
    return results


def assessment_gates_completion(program):
    return bool(program.final_assessment_required and program.final_assessment)


def assessment_summary(program):
    """Public facts only (no questions)."""
    questions = program.final_assessment or []
    if not questions:
        return None
    return {
        "required": bool(program.final_assessment_required),
        "passingScore": program.final_assessment_passing_score,
        "questionCount": len(questions),
    }


def learner_assessment_payload(enrollment):
    program = enrollment.learning_program
    summary = assessment_summary(program)
    if summary is None:
        raise ApiError("This course has no final assessment.", 404, code="not_found")
    return {
        **summary,
        "questions": [public_question(q) for q in program.final_assessment],
        "bestScore": enrollment.final_assessment_best_score,
        "passed": enrollment.final_assessment_passed_at is not None,
        "passedAt": enrollment.final_assessment_passed_at.isoformat() if enrollment.final_assessment_passed_at else None,
    }


def grade_assessment(enrollment, answers):
    """Scores a submission (every question counts; unanswered = wrong),
    keeps the best score and first pass time. Returns the result without
    revealing correct options."""
    program = enrollment.learning_program
    questions = program.final_assessment or []
    if not questions:
        raise ApiError("This course has no final assessment.", 404, code="not_found")
    if not isinstance(answers, dict):
        raise ApiError("answers must be an object.", 422, code="validation_error")
    results = []
    for question in questions:
        correct, _, _ = grade_question(question, answers)
        results.append({"questionId": question.get("id"), "correct": correct})
    score = round(100 * sum(1 for r in results if r["correct"]) / len(questions))
    passed = score >= program.final_assessment_passing_score
    if enrollment.final_assessment_best_score is None or score > enrollment.final_assessment_best_score:
        enrollment.final_assessment_best_score = score
    if passed and enrollment.final_assessment_passed_at is None:
        enrollment.final_assessment_passed_at = datetime.now(timezone.utc)
    return {"score": score, "passed": passed, "passingScore": program.final_assessment_passing_score, "results": results}
