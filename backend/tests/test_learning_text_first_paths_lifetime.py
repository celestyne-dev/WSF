"""Text-first WSF Learning, Learning Paths and WSF Lifetime (this phase):
derived course facts, learning blocks + knowledge checks (answers never
leak), the optional final assessment and its completion/certificate rule,
Learning Paths (order, visibility, derived progress, goals), the Lifetime
eligibility override and its forced exclusions, and the server shell
(paths, lesson pages, /lifetime, Course/ItemList structured data)."""
import json
import os
import re
import uuid

import pytest

from app.extensions import db
from tests.conftest import auth_headers
from tests.test_learning_circle_access import _make_program
from tests.test_lifetime_digital_access import _enroll, _member, _orders, _product

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")

KC_BLOCK = {
    "type": "knowledgeCheck",
    "title": "Check yourself",
    "questions": [
        {"id": "q1", "prompt": "Pick B", "kind": "single", "explanation": "B is right.",
         "options": [{"id": "a", "text": "A", "correct": False}, {"id": "b", "text": "B", "correct": True}]},
        {"id": "q2", "prompt": "Pick A and C", "kind": "multiple",
         "options": [{"id": "a", "text": "A", "correct": True}, {"id": "b", "text": "B"}, {"id": "c", "text": "C", "correct": True}]},
    ],
}
ASSESSMENT = [
    {"id": "f1", "prompt": "Yes?", "kind": "true_false", "options": [{"id": "true", "text": "True", "correct": True}]},
    {"id": "f2", "prompt": "Pick B", "kind": "single", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B", "correct": True}]},
]


def _set(app, model, row_id, **fields):
    # Uses the fixture's own app context/session — the one test-client
    # requests share — so later requests never see a stale cached row.
    row = db.session.get(model, row_id)
    for k, v in fields.items():
        setattr(row, k, v)
    db.session.commit()


def _program(app, **kw):
    from app.models.learning import LearningProgram

    pid, lessons = _make_program(app, **kw)
    return pid, lessons, LearningProgram


def _lessons(app, program_id, specs):
    """Replace a program's lessons with (lesson_type, minutes, content) specs."""
    from app.models.learning import LearningLesson, LearningModule

    with app.app_context():
        module = LearningModule.query.filter_by(learning_program_id=program_id).first()
        for lesson in list(module.lessons):
            db.session.delete(lesson)
        db.session.flush()
        ids = []
        for i, (ltype, minutes, content) in enumerate(specs):
            lesson = LearningLesson(module_id=module.id, title=f"L{i + 1}", lesson_type=ltype, content=content or [],
                                    duration_minutes=minutes, sort_order=i,
                                    external_url="https://www.youtube.com/watch?v=abc" if ltype in ("video", "recording") else None)
            db.session.add(lesson)
            db.session.flush()
            ids.append(lesson.id)
        db.session.commit()
        return ids


def _slug_of(app, program_id):
    from app.models.learning import LearningProgram

    with app.app_context():
        return db.session.get(LearningProgram, program_id).slug


@pytest.fixture()
def admin_headers(client, app):
    from app.models.user import Role, User

    payload = {"email": "lp-admin@example.com", "password": "supersecret1", "first_name": "A", "last_name": "D"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="admin").first())
        db.session.commit()
    token = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]
    return auth_headers(token)


def _learner(client, n=1):
    payload = {"email": f"learner{n}-{uuid.uuid4().hex[:6]}@example.com", "password": "supersecret1", "first_name": "L", "last_name": "N"}
    client.post("/api/v1/auth/register", json=payload)
    return client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]


# --- derived course facts ------------------------------------------------------------


class TestDerivedFacts:
    @pytest.mark.parametrize(
        "types, expected, label",
        [
            (["text", "text", "activity", "article"], "text", "Text-based"),
            (["text", "text", "text", "video"], "mixed", "Mixed format"),
            (["video", "video", "recording", "text"], "video_led", "Video-led"),
        ],
    )
    def test_format_counts_and_minutes(self, client, app, types, expected, label):
        pid, _, _ = _program(app, lesson_count=1)
        _lessons(app, pid, [(t, 10, []) for t in types])
        data = client.get(f"/api/v1/learning/{_slug_of(app, pid)}").get_json()["data"]
        assert data["stats"]["format"] == expected and data["stats"]["formatLabel"] == label
        assert data["stats"]["lessonCount"] == 4 and data["stats"]["moduleCount"] == 1 and data["stats"]["totalMinutes"] == 40

    def test_text_only_course_has_no_video_fields(self, client, app):
        pid, _, _ = _program(app, lesson_count=1)
        _lessons(app, pid, [("text", None, [{"type": "paragraph", "text": "Hi"}])])
        data = client.get(f"/api/v1/learning/{_slug_of(app, pid)}").get_json()["data"]
        assert data["stats"]["videoLessonCount"] == 0 and data["stats"]["totalMinutes"] is None
        lesson = data["modules"][0]["lessons"][0]
        assert lesson["embed_url"] is None and lesson["video_provider"] is None

    def test_list_uses_batched_stats_and_filters_by_format_and_goal(self, client, app):
        from app.models.taxonomy import Topic

        text_id, _, _ = _program(app, lesson_count=2)
        mixed_id, _, _ = _program(app, lesson_count=1)
        _lessons(app, mixed_id, [("text", 5, []), ("video", 5, [])])
        with app.app_context():
            topic = Topic(slug="promo-topic", name="Promotion", status="published", career_goal="get_promoted")
            db.session.add(topic)
            from app.models.learning import LearningProgram

            program = db.session.get(LearningProgram, text_id)
            program.topics.append(topic)
            db.session.commit()
        items = client.get("/api/v1/learning?format=text").get_json()["data"]
        ids = {i["id"] for i in items}
        assert text_id in ids and mixed_id not in ids
        assert all("stats" in i and i["stats"]["lessonCount"] >= 1 for i in items)
        assert {i["id"] for i in client.get("/api/v1/learning?format=mixed").get_json()["data"]} == {mixed_id}
        assert {i["id"] for i in client.get("/api/v1/learning?goal=get-promoted").get_json()["data"]} == {text_id}
        facets = client.get("/api/v1/learning/meta/facets").get_json()["data"]
        assert facets["careerGoals"] == ["get_promoted"] and set(facets["formats"]) == {"text", "mixed"}

    def test_outcomes_and_skills_round_trip(self, client, app, admin_headers):
        pid, _, _ = _program(app, lesson_count=1)
        body = client.get(f"/api/v1/learning/admin/programs/{pid}", headers=admin_headers).get_json()["data"]
        payload = {"title": body["title"], "status": "draft", "accessType": "free",
                   "learningOutcomes": ["Set boundaries", "  "], "skills": ["Self-advocacy", "Boundary setting"],
                   "primaryInstructorSlug": body["primary_instructor"]["slug"]}
        resp = client.patch(f"/api/v1/learning/admin/programs/{pid}", json=payload, headers=admin_headers)
        assert resp.status_code == 200, resp.get_json()
        _set(app, __import__("app.models.learning", fromlist=["LearningProgram"]).LearningProgram, pid, status="published")
        data = client.get(f"/api/v1/learning/{_slug_of(app, pid)}").get_json()["data"]
        assert data["learning_outcomes"] == ["Set boundaries"] and data["skills"] == ["Self-advocacy", "Boundary setting"]


# --- learning blocks + knowledge checks --------------------------------------------------


class TestKnowledgeChecks:
    def _program_with_check(self, app, access="free"):
        pid, _, _ = _program(app, lesson_count=1, access_type=access)
        ids = _lessons(app, pid, [("text", 5, [{"type": "paragraph", "text": "Read"}, KC_BLOCK])])
        from app.services.content_blocks import sanitize_content_blocks
        from app.models.learning import LearningLesson

        with app.app_context():
            lesson = db.session.get(LearningLesson, ids[0])
            lesson.content = sanitize_content_blocks(lesson.content)
            db.session.commit()
        return pid, ids[0]

    def test_public_and_protected_payloads_never_carry_answers(self, client, app):
        pid, _lid = self._program_with_check(app)
        raw = json.dumps(client.get(f"/api/v1/learning/{_slug_of(app, pid)}").get_json()["data"])
        assert "Pick B" in raw and '"correct"' not in raw and "B is right." not in raw

    def test_check_endpoint_gives_feedback_after_answering(self, client, app):
        _pid, lid = self._program_with_check(app)
        resp = client.post(f"/api/v1/learning/lessons/{lid}/knowledge-check", json={"answers": {"q1": ["a"], "q2": ["a", "c"]}})
        assert resp.status_code == 200
        results = {r["questionId"]: r for r in resp.get_json()["data"]["results"]}
        assert results["q1"]["correct"] is False and results["q1"]["correctOptionIds"] == ["b"] and results["q1"]["explanation"] == "B is right."
        assert results["q2"]["correct"] is True
        # Only answered questions are revealed.
        only = client.post(f"/api/v1/learning/lessons/{lid}/knowledge-check", json={"answers": {"q1": "b"}}).get_json()["data"]["results"]
        assert [r["questionId"] for r in only] == ["q1"] and only[0]["correct"] is True
        assert client.post(f"/api/v1/learning/lessons/{lid}/knowledge-check", json={"answers": {}}).status_code == 422

    def test_check_respects_program_access(self, client, app):
        from app.models.learning import LearningProgram

        pid, lid = self._program_with_check(app, access="circle_only")
        assert client.post(f"/api/v1/learning/lessons/{lid}/knowledge-check", json={"answers": {"q1": ["b"]}}).status_code == 403
        _set(app, LearningProgram, pid, status="draft", access_type="free")
        assert client.post(f"/api/v1/learning/lessons/{lid}/knowledge-check", json={"answers": {"q1": ["b"]}}).status_code == 404

    def test_learning_blocks_are_sanitized(self):
        from app.services.content_blocks import sanitize_content_blocks

        blocks = sanitize_content_blocks([
            {"type": "keyTakeaways", "items": ["<b>One</b>", "<script>x</script>Two", ""], "evil": 1},
            {"type": "reflection", "prompts": ["<i>Why?</i>"] * 7},
            {"type": "furtherReading", "links": [{"label": "ok", "url": "/learning"}, {"label": "bad", "url": "javascript:alert(1)"}]},
            {"type": "resourceLink", "resourceSlug": "Not A Slug"},
            {"type": "knowledgeCheck", "questions": [{"prompt": "x", "options": [{"text": "a", "correct": True}, {"text": "b", "correct": True}]}] * 9},
        ])
        assert blocks[0] == {"type": "keyTakeaways", "title": "", "items": ["<b>One</b>", "xTwo"]}
        assert blocks[1]["prompts"] == ["Why?"] * 5
        assert blocks[2]["links"] == [{"label": "ok", "url": "/learning"}]
        assert blocks[3]["resourceSlug"] == ""
        assert len(blocks[4]["questions"]) == 5
        assert [o["correct"] for o in blocks[4]["questions"][0]["options"]] == [True, False]


# --- final assessment, completion and certificates --------------------------------------


class TestFinalAssessment:
    def _course(self, app, required=True, certificate=True):
        from app.models.learning import LearningProgram

        pid, lessons, _ = _program(app, lesson_count=2)
        _set(app, LearningProgram, pid, final_assessment=ASSESSMENT, final_assessment_required=required,
             final_assessment_passing_score=70, certificate_enabled=certificate)
        return pid, lessons

    def _complete_lessons(self, client, token, enrollment_id, lessons):
        for lid in lessons:
            assert client.post(f"/api/v1/learning-enrollments/{enrollment_id}/lessons/{lid}/complete", headers=auth_headers(token)).status_code == 200

    def test_required_assessment_gates_completion_and_certificate(self, client, app):
        pid, lessons = self._course(app)
        token = _learner(client)
        enrollment = _enroll(client, token, pid).get_json()["data"]["enrollment"]
        assert enrollment["next_lesson_id"] == lessons[0]
        assert enrollment["final_assessment"] == {"required": True, "passingScore": 70, "questionCount": 2}
        self._complete_lessons(client, token, enrollment["id"], lessons)
        state = client.get(f"/api/v1/learning-enrollments/check?program_id={pid}", headers=auth_headers(token)).get_json()["data"]["enrollment"]
        assert state["completed_at"] is None and state["certificate"] is None and state["next_lesson_id"] is None

        questions = client.get(f"/api/v1/learning-enrollments/{enrollment['id']}/assessment", headers=auth_headers(token)).get_json()["data"]
        assert '"correct"' not in json.dumps(questions) and len(questions["questions"]) == 2

        failed = client.post(f"/api/v1/learning-enrollments/{enrollment['id']}/assessment", json={"answers": {"f1": ["true"], "f2": ["a"]}}, headers=auth_headers(token)).get_json()["data"]
        assert failed["result"]["score"] == 50 and failed["result"]["passed"] is False and failed["enrollment"]["completed_at"] is None
        assert "correctOptionIds" not in json.dumps(failed["result"])

        passed = client.post(f"/api/v1/learning-enrollments/{enrollment['id']}/assessment", json={"answers": {"f1": "true", "f2": ["b"]}}, headers=auth_headers(token)).get_json()["data"]
        assert passed["result"]["passed"] is True and passed["result"]["completed"] is True
        assert passed["enrollment"]["completed_at"] and passed["enrollment"]["certificate"]["status"] == "active"
        assert passed["enrollment"]["final_assessment_best_score"] == 100

        worse = client.post(f"/api/v1/learning-enrollments/{enrollment['id']}/assessment", json={"answers": {}}, headers=auth_headers(token)).get_json()["data"]
        assert worse["result"]["score"] == 0 and worse["enrollment"]["final_assessment_best_score"] == 100 and worse["enrollment"]["completed_at"]

    def test_optional_assessment_does_not_gate(self, client, app):
        pid, lessons = self._course(app, required=False)
        token = _learner(client)
        enrollment = _enroll(client, token, pid).get_json()["data"]["enrollment"]
        self._complete_lessons(client, token, enrollment["id"], lessons)
        state = client.get(f"/api/v1/learning-enrollments/check?program_id={pid}", headers=auth_headers(token)).get_json()["data"]["enrollment"]
        assert state["completed_at"] is not None

    def test_no_assessment_keeps_existing_rule_and_404s(self, client, app):
        pid, lessons, _ = _program(app, lesson_count=1)
        token = _learner(client)
        enrollment = _enroll(client, token, pid).get_json()["data"]["enrollment"]
        assert enrollment["final_assessment"] is None
        assert client.get(f"/api/v1/learning-enrollments/{enrollment['id']}/assessment", headers=auth_headers(token)).status_code == 404
        self._complete_lessons(client, token, enrollment["id"], lessons)
        assert client.get(f"/api/v1/learning-enrollments/check?program_id={pid}", headers=auth_headers(token)).get_json()["data"]["enrollment"]["completed_at"]

    def test_assessment_is_owner_only(self, client, app):
        pid, _lessons = self._course(app)
        owner = _learner(client, 1)
        other = _learner(client, 2)
        enrollment = _enroll(client, owner, pid).get_json()["data"]["enrollment"]
        assert client.get(f"/api/v1/learning-enrollments/{enrollment['id']}/assessment", headers=auth_headers(other)).status_code == 404
        assert client.post(f"/api/v1/learning-enrollments/{enrollment['id']}/assessment", json={"answers": {}}, headers=auth_headers(other)).status_code == 404

    def test_public_payload_has_summary_not_questions_and_admin_has_answers(self, client, app, admin_headers):
        pid, _lessons = self._course(app)
        public = client.get(f"/api/v1/learning/{_slug_of(app, pid)}").get_json()["data"]
        assert public["finalAssessment"] == {"required": True, "passingScore": 70, "questionCount": 2}
        assert public["final_assessment"] is None and "Pick B" not in json.dumps(public)
        admin = client.get(f"/api/v1/learning/admin/programs/{pid}", headers=admin_headers).get_json()["data"]
        assert admin["final_assessment"][1]["options"][1]["correct"] is True


# --- Learning Paths ---------------------------------------------------------------------------


def _path(client, admin_headers, program_ids, **fields):
    payload = {"title": fields.pop("title", f"Path {uuid.uuid4().hex[:5]}"), "programIds": program_ids, "status": fields.pop("status", "published"), **fields}
    resp = client.post("/api/v1/learning-paths/admin", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["data"]


class TestLearningPaths:
    def test_order_visibility_and_derived_facts(self, client, app, admin_headers):
        from app.models.learning import LearningProgram

        a, _, _ = _program(app, lesson_count=2, title="First")
        b, _, _ = _program(app, lesson_count=1, title="Second")
        draft, _, _ = _program(app, lesson_count=1, title="Draft one", status="draft")
        path = _path(client, admin_headers, [b, draft, a], careerGoal="get_promoted", shortDescription="Go up")
        assert [p["id"] for p in path["programs"]] == [b, draft, a]

        detail = client.get(f"/api/v1/learning-paths/{path['slug']}").get_json()["data"]
        assert [c["title"] for c in detail["courses"]] == ["Second", "First"]  # draft hidden, order kept
        assert detail["courseCount"] == 2 and detail["lessonCount"] == 3 and detail["totalMinutes"] == 15
        assert detail["careerGoal"]["key"] == "get_promoted" and detail["viewerProgress"] is None
        assert all("modules" not in c for c in detail["courses"])  # catalog summaries only
        assert detail["lifetimeIncluded"] is True
        listed = client.get("/api/v1/learning-paths").get_json()["data"]
        assert [p["slug"] for p in listed] == [path["slug"]] and listed[0]["courseTitles"] == ["Second", "First"]

        # Unpublishing every course hides the path entirely.
        _set(app, LearningProgram, a, status="archived")
        _set(app, LearningProgram, b, status="archived")
        assert client.get(f"/api/v1/learning-paths/{path['slug']}").status_code == 404
        assert client.get("/api/v1/learning-paths").get_json()["data"] == []

    def test_draft_path_is_private_and_publish_needs_a_course(self, client, app, admin_headers):
        a, _, _ = _program(app, lesson_count=1)
        draft = _path(client, admin_headers, [a], status="draft")
        assert client.get(f"/api/v1/learning-paths/{draft['slug']}").status_code == 404
        empty = client.post("/api/v1/learning-paths/admin", json={"title": "Empty", "programIds": [], "status": "published"}, headers=admin_headers)
        assert empty.status_code == 422
        assert client.post("/api/v1/learning-paths/admin", json={"title": "X", "slug": "admin"}, headers=admin_headers).status_code == 400
        assert client.get("/api/v1/learning-paths/admin").status_code in (401, 403)

    def test_viewer_progress_is_derived_from_her_enrollments(self, client, app, admin_headers):
        a, a_lessons, _ = _program(app, lesson_count=1, title="A")
        b, _b_lessons, _ = _program(app, lesson_count=2, title="B")
        path = _path(client, admin_headers, [a, b])
        token = _learner(client)
        enrollment = _enroll(client, token, a).get_json()["data"]["enrollment"]
        client.post(f"/api/v1/learning-enrollments/{enrollment['id']}/lessons/{a_lessons[0]}/complete", headers=auth_headers(token))
        _enroll(client, token, b)
        progress = client.get(f"/api/v1/learning-paths/{path['slug']}", headers=auth_headers(token)).get_json()["data"]["viewerProgress"]
        assert progress["completedCourses"] == 1 and progress["inProgressCourses"] == 1 and progress["totalCourses"] == 2
        assert progress["progressPercent"] == 33 and progress["nextProgramSlug"] == _slug_of(app, b)
        other = _learner(client, 2)
        fresh = client.get(f"/api/v1/learning-paths/{path['slug']}", headers=auth_headers(other)).get_json()["data"]["viewerProgress"]
        assert fresh["completedCourses"] == 0 and fresh["nextProgramSlug"] == _slug_of(app, a)

    def test_goal_recommendations_are_deterministic(self, client, app, admin_headers):
        from app.models.user import User

        a, _, _ = _program(app, lesson_count=1)
        promoted = _path(client, admin_headers, [a], careerGoal="get_promoted", title="Get Promoted")
        _path(client, admin_headers, [a], careerGoal="return_to_work", title="Return to Work")
        token = _learner(client)
        with app.app_context():
            user = User.query.order_by(User.id.desc()).first()
            user.career_goals = ["get_promoted"]
            db.session.commit()
        rec = client.get("/api/v1/learning-paths/recommended", headers=auth_headers(token)).get_json()["data"]
        assert [p["slug"] for p in rec["items"]] == [promoted["slug"]] and rec["goals"][0]["key"] == "get_promoted"
        assert client.get("/api/v1/learning-paths/recommended").get_json()["data"]["items"] == []
        assert [p["slug"] for p in client.get("/api/v1/learning-paths?goal=get-promoted").get_json()["data"]] == [promoted["slug"]]

    def test_program_page_lists_its_published_paths(self, client, app, admin_headers):
        a, _, _ = _program(app, lesson_count=1)
        published = _path(client, admin_headers, [a], title="Visible path")
        _path(client, admin_headers, [a], title="Hidden path", status="draft")
        data = client.get(f"/api/v1/learning/{_slug_of(app, a)}").get_json()["data"]
        assert data["learningPaths"] == [{"slug": published["slug"], "title": "Visible path"}]

    def test_path_lifetime_inclusion_requires_every_course_eligible(self, client, app, admin_headers):
        a, _, _ = _program(app, lesson_count=1)
        ext, _, _ = _program(app, lesson_count=1, access_type="external", external_url="https://partner.example.org")
        path = _path(client, admin_headers, [a, ext])
        assert client.get(f"/api/v1/learning-paths/{path['slug']}").get_json()["data"]["lifetimeIncluded"] is False

    def test_reserved_learning_slug(self, client, app, admin_headers):
        a, _, _ = _program(app, lesson_count=1)
        body = client.get(f"/api/v1/learning/admin/programs/{a}", headers=admin_headers).get_json()["data"]
        resp = client.patch(f"/api/v1/learning/admin/programs/{a}", json={"title": body["title"], "slug": "paths", "accessType": "free"}, headers=admin_headers)
        assert resp.status_code == 400 and resp.get_json()["error"]["code"] == "reserved_slug"


# --- WSF Lifetime eligibility ---------------------------------------------------------------


class TestLifetimeEligibility:
    def test_override_excludes_a_premium_course(self, client, app):
        from app.models.learning import LearningProgram

        token, _uid = _member(app, client, "lifetime")
        pid, _, _ = _program(app, lesson_count=1, access_type="product", product_id=_product(app))
        slug = _slug_of(app, pid)
        assert client.get(f"/api/v1/learning/{slug}", headers=auth_headers(token)).get_json()["data"]["lifetimeIncluded"] is True
        _set(app, LearningProgram, pid, lifetime_access="excluded")
        data = client.get(f"/api/v1/learning/{slug}", headers=auth_headers(token)).get_json()["data"]
        assert data["lifetimeIncluded"] is False and data["viewerCanAccess"] is False
        assert _enroll(client, token, pid).status_code == 422

    @pytest.mark.parametrize("case", ["partner", "external", "service", "physical"])
    def test_forced_exclusions_beat_an_included_override(self, client, app, case):
        from app.models.people import Organization

        token, _uid = _member(app, client, "lifetime")
        extra = {"lifetime_access": "included"}
        if case == "partner":
            with app.app_context():
                org = Organization(slug=f"partner-{uuid.uuid4().hex[:5]}", name="Partner", status="published")
                db.session.add(org)
                db.session.commit()
                extra.update(provider_organization_id=org.id, access_type="product", product_id=_product(app))
        elif case == "external":
            extra.update(access_type="external", external_url="https://partner.example.org/course")
        else:
            extra.update(access_type="product", product_id=_product(app, type=case))
        pid, _, _ = _program(app, lesson_count=1, **extra)
        data = client.get(f"/api/v1/learning/{_slug_of(app, pid)}", headers=auth_headers(token)).get_json()["data"]
        assert data["lifetimeIncluded"] is False and data["viewerCanAccess"] is False

    def test_circle_course_ignores_excluded_override(self, client, app):
        token, _uid = _member(app, client, "lifetime")
        pid, _, _ = _program(app, lesson_count=1, access_type="circle_only", lifetime_access="excluded")
        data = client.get(f"/api/v1/learning/{_slug_of(app, pid)}", headers=auth_headers(token)).get_json()["data"]
        assert data["lifetimeIncluded"] is True and data["viewerCanAccess"] is True

    def test_lifetime_course_needs_completion_for_certificate_and_creates_no_order(self, client, app):
        from app.models.learning import LearningProgram as Program

        token, _uid = _member(app, client, "lifetime")
        pid, lessons, _ = _program(app, lesson_count=2, access_type="product", product_id=_product(app))
        _set(app, Program, pid, certificate_enabled=True)
        orders_before = _orders(app)
        enrollment = _enroll(client, token, pid).get_json()["data"]["enrollment"]
        assert enrollment["certificate"] is None and enrollment["completed_at"] is None
        client.post(f"/api/v1/learning-enrollments/{enrollment['id']}/lessons/{lessons[0]}/complete", headers=auth_headers(token))
        half = client.get(f"/api/v1/learning-enrollments/check?program_id={pid}", headers=auth_headers(token)).get_json()["data"]["enrollment"]
        assert half["certificate"] is None
        client.post(f"/api/v1/learning-enrollments/{enrollment['id']}/lessons/{lessons[1]}/complete", headers=auth_headers(token))
        done = client.get(f"/api/v1/learning-enrollments/check?program_id={pid}", headers=auth_headers(token)).get_json()["data"]["enrollment"]
        assert done["certificate"]["status"] == "active"
        assert _orders(app) == orders_before

    def test_path_page_reports_lifetime_viewer(self, client, app, admin_headers):
        a, _, _ = _program(app, lesson_count=1)
        path = _path(client, admin_headers, [a])
        token, _uid = _member(app, client, "lifetime")
        assert client.get(f"/api/v1/learning-paths/{path['slug']}", headers=auth_headers(token)).get_json()["data"]["viewerIsLifetime"] is True
        assert client.get(f"/api/v1/learning-paths/{path['slug']}").get_json()["data"]["viewerIsLifetime"] is False


# --- server shell / SEO --------------------------------------------------------------------------


def _json_ld(html, attr):
    match = re.search(rf'<script type="application/ld\+json" {attr}[^>]*>(.*?)</script>', html, re.S)
    return json.loads(match.group(1)) if match else None


class TestShell:
    def test_course_page_outline_and_accurate_course_json_ld(self, client, app):
        from app.models.learning import LearningProgram

        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        pid, _, _ = _program(app, lesson_count=2, skills=["Boundary setting"], difficulty_level="intermediate")
        html = client.get(f"/learning/{_slug_of(app, pid)}").get_data(as_text=True)
        # Counts and catalog facts only — never module/lesson titles.
        assert "Lesson 1" not in html and "Module 1" not in html and "Skills you&#x27;ll build" in html
        assert "Self-paced · Text-based · Intermediate" in html and "Approx. 10 min" in html
        assert "Secret lesson body." not in html and "video.example.org" not in html
        course = _json_ld(html, "data-course-structured-data")
        assert course["@type"] == "Course" and course["teaches"] == ["Boundary setting"] and course["isAccessibleForFree"] is True
        assert course["hasCourseInstance"][0]["courseWorkload"] == "PT10M"
        for fabricated in ("aggregateRating", "offers", "educationalCredentialAwarded", "accreditation"):
            assert fabricated not in json.dumps(course)

    def test_path_page_prerender_and_item_list(self, client, app, admin_headers):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        a, _, _ = _program(app, lesson_count=1, title="Course A")
        path = _path(client, admin_headers, [a], title="Get Promoted", shortDescription="Four steps")
        html = client.get(f"/learning/paths/{path['slug']}").get_data(as_text=True)
        assert '<main data-wsf-prerender="learning-path"' in html and "Course A" in html
        item_list = _json_ld(html, "data-learning-path-structured-data")
        assert item_list["@type"] == "CollectionPage" and item_list["mainEntity"]["itemListElement"][0]["name"] == "Course A"
        assert client.get("/learning/paths/nope").status_code == 404
        listing = client.get("/learning/paths").get_data(as_text=True)
        assert "Get Promoted" in listing and "<title>Learning Paths | WSF Learning</title>" in listing

    def test_lesson_route_is_noindex_and_leaks_nothing(self, client, app):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        pid, lessons, _ = _program(app, lesson_count=1, access_type="circle_only")
        resp = client.get(f"/learning/{_slug_of(app, pid)}/lessons/{lessons[0]}")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200 and 'content="noindex, follow"' in html
        assert "Secret lesson body." not in html and "Lesson 1" not in html
        assert client.get(f"/learning/missing-course/lessons/{lessons[0]}").status_code == 404

    def test_lifetime_page_prerender_uses_real_plans(self, client, app):
        from tests.test_circle_lifetime import _plan

        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        html = client.get("/lifetime").get_data(as_text=True)
        assert "not open for new members right now" in html and "Everything you need to keep growing your career" in html
        _plan(app, interval="lifetime", prices=(("KES", 1234500),))
        html = client.get("/lifetime").get_data(as_text=True)
        assert "one-time" in html and "One payment. No membership renewal." in html
        assert "eligible" in html


def test_lifetime_copy_matches_frontend():
    from app.services import spa_shell

    source = open(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "constants", "lifetime.js"), encoding="utf-8").read()
    for text in (spa_shell.LIFETIME_TITLE, spa_shell.LIFETIME_LEAD, spa_shell.LIFETIME_EXCLUDED_NOTE, *spa_shell.LIFETIME_INCLUDED):
        assert text.replace("'", "\\'") in source or text in source, text


def test_reserved_lifetime_slug_matches_frontend():
    from app.utils.slugs import RESERVED_SLUGS

    source = open(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "constants", "routes.js"), encoding="utf-8").read()
    assert "lifetime" in RESERVED_SLUGS and "'lifetime'" in source


@pytest.mark.parametrize("access", ["free", "circle_only"])
def test_course_shell_lists_counts_not_titles(client, app, access):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    pid, _, _ = _program(app, lesson_count=2, access_type=access)
    html = client.get(f"/learning/{_slug_of(app, pid)}").get_data(as_text=True)
    assert "1 module · 2 lessons" in html and "Lesson 1" not in html and "Module 1" not in html
