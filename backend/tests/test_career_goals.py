"""Private user career goals and the deterministic "Recommended for your
goals" Career Hub strip."""
import os

from tests.conftest import auth_headers
from tests.test_career_hub import _program, _resource, _topic
from tests.test_learning_certificates import _register


def _user(client, email="goals@example.com"):
    return auth_headers(_register(client, {"email": email, "password": "supersecret1", "first_name": "Grace", "last_name": "G"}))


class TestCareerGoals:
    def test_requires_login(self, client):
        assert client.get("/api/v1/career-hub/me/goals").status_code == 401
        assert client.put("/api/v1/career-hub/me/goals", json={"goals": []}).status_code == 401
        assert client.get("/api/v1/career-hub/me/recommended").status_code == 401

    def test_default_state_then_skip(self, client):
        headers = _user(client)
        assert client.get("/api/v1/career-hub/me/goals", headers=headers).get_json()["data"] == {"goals": [], "prompted": False}
        skipped = client.post("/api/v1/career-hub/me/goals/skip", headers=headers).get_json()["data"]
        assert skipped == {"goals": [], "prompted": True}

    def test_save_validates_and_dedupes(self, client):
        headers = _user(client)
        saved = client.put("/api/v1/career-hub/me/goals", json={"goals": ["get-promoted", "earn_more", "get_promoted"]}, headers=headers)
        assert saved.status_code == 200
        data = saved.get_json()["data"]
        assert [g["key"] for g in data["goals"]] == ["get_promoted", "earn_more"] and data["prompted"] is True
        assert client.put("/api/v1/career-hub/me/goals", json={"goals": ["astrology"]}, headers=headers).status_code == 422
        too_many = ["find_a_job", "get_promoted", "earn_more", "leadership"]
        assert client.put("/api/v1/career-hub/me/goals", json={"goals": too_many}, headers=headers).status_code == 422
        assert client.put("/api/v1/career-hub/me/goals", json={"goals": "earn_more"}, headers=headers).status_code == 422
        cleared = client.put("/api/v1/career-hub/me/goals", json={"goals": []}, headers=headers).get_json()["data"]
        assert cleared["goals"] == [] and cleared["prompted"] is True

    def test_goals_never_in_user_payloads(self, client):
        headers = _user(client)
        client.put("/api/v1/career-hub/me/goals", json={"goals": ["earn_more"]}, headers=headers)
        me = client.get("/api/v1/auth/me", headers=headers).get_data(as_text=True)
        assert "career_goals" not in me and "earn_more" not in me

    def test_distinct_user_queries_still_work_with_goals(self, client, app):
        # Staff notifications run SELECT DISTINCT over users; a plain json
        # column would make Postgres fail with "no equality operator".
        from app.services.notifications import _active_recipients_with_permission

        headers = _user(client)
        client.put("/api/v1/career-hub/me/goals", json={"goals": ["earn_more"]}, headers=headers)
        with app.app_context():
            assert isinstance(_active_recipients_with_permission("submissions.manage"), list)

    def test_recommendations_are_deterministic_and_goal_scoped(self, client, app):
        headers = _user(client)
        assert client.get("/api/v1/career-hub/me/recommended", headers=headers).get_json()["data"]["items"] == []
        promo = _topic(app, "promotion", goal="get_promoted")
        pay = _topic(app, "pay", goal="earn_more")
        other = _topic(app, "jobs", goal="find_a_job")
        draft_topic = _topic(app, "draft-promo", goal="get_promoted", status="draft")
        _resource(app, "promo-guide", topics=(promo,))
        _resource(app, "pay-kit", topics=(pay,), featured=True)
        _resource(app, "job-guide", topics=(other,))
        _resource(app, "hidden", topics=(draft_topic,))
        _resource(app, "draft-res", topics=(promo,), status="draft")
        _program(app, "promo-course", topics=(promo,))
        client.put("/api/v1/career-hub/me/goals", json={"goals": ["get_promoted", "earn_more"]}, headers=headers)
        first = client.get("/api/v1/career-hub/me/recommended", headers=headers).get_json()["data"]
        slugs = [c["slug"] for c in first["items"]]
        assert slugs[0] == "pay-kit"  # featured first
        assert set(slugs) == {"pay-kit", "promo-guide", "promo-course"}
        again = client.get("/api/v1/career-hub/me/recommended", headers=headers).get_json()["data"]
        assert [c["slug"] for c in again["items"]] == slugs
        body = client.get("/api/v1/career-hub/me/recommended", headers=headers).get_data(as_text=True)
        assert "secret/path.pdf" not in body

    def test_migration_chain(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config()
        config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
        script = ScriptDirectory.from_config(config)
        assert len(script.get_heads()) == 1
        assert script.get_revision("d4a7c9e1f3b5").down_revision == "c3f5d8a0b2e7"
