"""Career Outcomes (on Story Submissions: consent + approval gated,
privacy-safe attribution) and Organization workplace practices (claim
source, never a certification)."""
import os

from tests.conftest import auth_headers
from tests.test_organizations import _base_payload as _org_payload
from tests.test_story_submissions_cms import _base_payload as _story_payload
from tests.test_story_submissions_cms import _get_submission_by_email, admin_token  # noqa: F401  (fixture)


def _submit(client, **kw):
    resp = client.post("/api/v1/submissions", json=_story_payload(**kw))
    assert resp.status_code == 201, resp.get_json()
    return resp


def _patch(client, app, token, email, body):
    sub_id = _get_submission_by_email(app, email).id
    return client.patch(f"/api/v1/submissions/{sub_id}", json=body, headers=auth_headers(token))


class TestCareerOutcomes:
    def test_submission_without_outcome_has_none(self, client, app):
        _submit(client, outcomePublishConsent=True, outcomeAttribution="first_name")
        sub = _get_submission_by_email(app, "amara@example.com")
        assert sub.outcome_status == "none" and sub.outcome_publish_consent is False
        assert sub.outcome_attribution == "anonymous"

    def test_outcome_is_pending_then_public_only_after_approval(self, client, app, admin_token):  # noqa: F811
        _submit(client, outcomeType="promotion", outcomePublishConsent=True, outcomeAttribution="first_name")
        assert _get_submission_by_email(app, "amara@example.com").outcome_status == "pending"
        assert client.get("/api/v1/career-outcomes").get_json()["data"] == []
        missing = _patch(client, app, admin_token, "amara@example.com", {"outcomeStatus": "approved"})
        assert missing.status_code == 422  # summary required
        ok = _patch(client, app, admin_token, "amara@example.com",
                    {"outcomeStatus": "approved", "outcomeSummary": "Promoted to engineering manager."})
        assert ok.status_code == 200, ok.get_json()
        items = client.get("/api/v1/career-outcomes").get_json()["data"]
        assert items == [{"type": "promotion", "label": "Got promoted", "summary": "Promoted to engineering manager.",
                          "attribution": "Amara D."}]
        body = client.get("/api/v1/career-outcomes").get_data(as_text=True)
        for leak in ("amara@example.com", "Diallo", "KE", "How I Rebuilt", "id"):
            assert leak not in body.replace('"summary"', "")

    def test_no_consent_never_published(self, client, app, admin_token):  # noqa: F811
        _submit(client, outcomeType="new_job", outcomePublishConsent=False)
        resp = _patch(client, app, admin_token, "amara@example.com",
                      {"outcomeStatus": "approved", "outcomeSummary": "Started a new role."})
        assert resp.status_code == 422
        assert client.get("/api/v1/career-outcomes").get_json()["data"] == []

    def test_anonymous_and_staff_cannot_unmask(self, client, app, admin_token):  # noqa: F811
        _submit(client, outcomeType="pay_increase", outcomePublishConsent=True)
        unmask = _patch(client, app, admin_token, "amara@example.com", {"outcomeAttribution": "first_name"})
        assert unmask.status_code == 422
        _patch(client, app, admin_token, "amara@example.com", {"outcomeStatus": "approved", "outcomeSummary": "Negotiated a raise."})
        assert client.get("/api/v1/career-outcomes").get_json()["data"][0]["attribution"] == "A WSF community member"
        _patch(client, app, admin_token, "amara@example.com", {"outcomeStatus": "rejected"})
        assert client.get("/api/v1/career-outcomes").get_json()["data"] == []

    def test_invalid_outcome_type_rejected(self, client):
        assert client.post("/api/v1/submissions", json=_story_payload(outcomeType="won_lottery")).status_code == 422


def _org_admin(client, app):
    from app.extensions import db
    from app.models.user import Role, User

    payload = {"email": "org-admin@example.com", "password": "supersecret1", "first_name": "O", "last_name": "A"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="admin").first())
        db.session.commit()
    token = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]
    return auth_headers(token)


class TestWorkplacePractices:
    def test_save_dump_and_omission_keeps(self, client, app):
        headers = _org_admin(client, app)
        practices = [
            {"practice": "paid_parental_leave", "claimSource": "publicly_documented", "sourceUrl": "https://example.com/policy"},
            {"practice": "flexible_work", "claimSource": "self_reported", "note": " Hybrid by default "},
        ]
        created = client.post("/api/v1/organizations", json=_org_payload(status="published", workplacePractices=practices), headers=headers)
        assert created.status_code == 201, created.get_json()
        slug = created.get_json()["data"]["slug"]
        public = client.get(f"/api/v1/organizations/{slug}").get_json()["data"]["workplacePractices"]
        assert public[1] == {"practice": "flexible_work", "claimSource": "self_reported", "sourceUrl": None, "note": "Hybrid by default"}
        client.put(f"/api/v1/organizations/{slug}", json=_org_payload(status="published"), headers=headers)
        assert len(client.get(f"/api/v1/organizations/{slug}").get_json()["data"]["workplacePractices"]) == 2
        client.put(f"/api/v1/organizations/{slug}", json=_org_payload(status="published", workplacePractices=[]), headers=headers)
        assert client.get(f"/api/v1/organizations/{slug}").get_json()["data"]["workplacePractices"] == []

    def test_validation(self, client, app):
        headers = _org_admin(client, app)

        def post(practices):
            return client.post("/api/v1/organizations", json=_org_payload(workplacePractices=practices), headers=headers).status_code

        assert post([{"practice": "free_lunch", "claimSource": "self_reported"}]) == 422
        assert post([{"practice": "flexible_work", "claimSource": "wsf_certified"}]) == 422
        assert post([{"practice": "flexible_work", "claimSource": "wsf_reviewed"}]) == 422  # needs a source link
        assert post([{"practice": "flexible_work", "claimSource": "self_reported", "sourceUrl": "javascript:alert(1)"}]) == 422
        dup = [{"practice": "flexible_work", "claimSource": "self_reported"}] * 2
        assert post(dup) == 422

    def test_migration_chain(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config()
        config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
        script = ScriptDirectory.from_config(config)
        assert len(script.get_heads()) == 1
        assert script.get_revision("e5b8d0f2a4c6").down_revision == "d4a7c9e1f3b5"
        assert script.get_revision("f6c9e1a3b5d7").down_revision == "e5b8d0f2a4c6"
