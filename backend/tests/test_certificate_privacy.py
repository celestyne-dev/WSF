"""Step 20: certificate privacy — full name or initials on public
verification; never email, user id or internal ids; the issued snapshot is
never rewritten; QR/verify, revoke and reissue keep working."""
from app.extensions import db
from app.models.learning_certificate import LearningCertificate
from app.services.learning_certificates import initials_of, verification_url
from tests.conftest import auth_headers
from tests.test_learning_certificates import LEARNER, _finish, _program, admin, learner  # noqa: F401

FORBIDDEN_KEYS = {"email", "learnerEmail", "userId", "user_id", "id", "enrollmentId", "enrollment_id",
                  "learningProgramId", "replacesCertificateId", "revocationReason"}


def _issue(client, app, token):
    program_id, lessons = _program(app)
    _finish(client, token, program_id, lessons)
    with app.app_context():
        cert = LearningCertificate.query.one()
        return cert.public_id, cert.recipient_name


def _verify(client, public_id):
    res = client.get(f"/api/v1/certificates/verify/{public_id}")
    assert res.status_code == 200
    return res.get_json()["data"]


def _set_mode(client, token, mode):
    return client.put("/api/v1/certificates/me/name-display", json={"publicNameMode": mode}, headers=auth_headers(token))


def test_initials():
    assert initials_of("Amara Okafor") == "A. O."
    assert initials_of("Ada King-Lovelace") == "A. K-L."
    assert initials_of("  zoë  ") == "Z."
    assert initials_of("O'Brien") == "O."
    assert initials_of("") == "—"


def test_full_name_by_default_and_no_identifiers(client, app, learner):
    public_id, name = _issue(client, app, learner)
    data = _verify(client, public_id)
    assert data["recipientName"] == name == "Amara Okafor"
    assert data["recipientNameDisplay"] == "full"
    assert not FORBIDDEN_KEYS & set(data)
    assert LEARNER["email"] not in str(data)
    assert set(data) == {"publicId", "certificateNumber", "status", "certificateTitle", "recipientName",
                         "recipientNameDisplay", "programTitle", "instructorNames", "issuerName",
                         "completedAt", "issuedAt", "revokedAt"}


def test_initials_only_on_public_verification(client, app, learner):
    public_id, _ = _issue(client, app, learner)
    assert _set_mode(client, learner, "initials").get_json()["data"] == {"publicNameMode": "initials"}
    data = _verify(client, public_id)
    assert data["recipientName"] == "A. O."
    assert data["recipientNameDisplay"] == "initials"
    assert "Amara" not in str(data) and "Okafor" not in str(data)
    # The snapshot itself is untouched; the owner still sees the full name.
    with app.app_context():
        assert LearningCertificate.query.one().recipient_name == "Amara Okafor"
    mine = client.get("/api/v1/certificates/me", headers=auth_headers(learner)).get_json()["data"][0]
    assert mine["recipientName"] == "Amara Okafor"
    assert mine["publicRecipientName"] == "A. O."
    # Switching back restores the full name; nothing was rewritten.
    _set_mode(client, learner, "full")
    assert _verify(client, public_id)["recipientName"] == "Amara Okafor"


def test_preference_validation_audit_and_auth(client, app, learner):
    assert client.get("/api/v1/certificates/me/name-display").status_code == 401
    assert client.put("/api/v1/certificates/me/name-display", json={"publicNameMode": "initials"}).status_code == 401
    for bad in ("Initials", "none", None, 1, ""):
        assert _set_mode(client, learner, bad).status_code == 422
    assert client.get("/api/v1/certificates/me/name-display", headers=auth_headers(learner)).get_json()["data"] == {"publicNameMode": "full"}
    _set_mode(client, learner, "initials")
    _set_mode(client, learner, "initials")  # unchanged: not audited twice
    from app.models.audit import AuditLog

    with app.app_context():
        logs = AuditLog.query.filter_by(action="learning_certificate.name_display_changed").all()
        assert len(logs) == 1
        assert logs[0].changes == {"from": "full", "to": "initials"}
    export = client.get("/api/v1/account/export", headers=auth_headers(learner)).get_json()
    account = (export.get("data") or export)["account"]
    assert account["certificate_public_name"] == "initials"
    me = client.get("/api/v1/auth/me", headers=auth_headers(learner)).get_json()["data"]
    assert "certificate_public_name" not in str(me) and "certificatePublicName" not in str(me)


def test_qr_and_pdf_carry_the_verification_link_not_identifiers(client, app, learner):
    public_id, _ = _issue(client, app, learner)
    _set_mode(client, learner, "initials")
    with app.app_context():
        url = verification_url(LearningCertificate.query.one())
    assert url.endswith(f"/certificates/verify/{public_id}")
    pdf = client.get(f"/api/v1/certificates/{public_id}/pdf", headers=auth_headers(learner))
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
    # The PDF is the learner's own document (full issued name); never the email.
    assert LEARNER["email"].encode() not in pdf.data
    # The QR encodes verification_url(); that route still resolves (200 shell).
    assert client.get(f"/certificates/verify/{public_id}").status_code == 200
    assert _verify(client, public_id)["recipientName"] == "A. O."


def test_revoke_and_reissue_follow_the_preference(client, app, learner, admin):  # noqa: F811
    public_id, _ = _issue(client, app, learner)
    _set_mode(client, learner, "initials")
    with app.app_context():
        cert_id = LearningCertificate.query.one().id
    res = client.post(f"/api/v1/certificates/admin/{cert_id}/reissue", json={"reason": "Name fix"}, headers=admin)
    assert res.status_code == 201
    replacement = res.get_json()["data"]
    # Staff see the full name and the learner's email (staff-only view).
    assert replacement["recipientName"] == "Amara Okafor"
    assert replacement["learnerEmail"] == LEARNER["email"]
    old = _verify(client, public_id)
    assert old["status"] == "revoked" and old["recipientName"] == "A. O."
    new = _verify(client, replacement["publicId"])
    assert new["status"] == "active" and new["recipientName"] == "A. O."
    assert client.post(f"/api/v1/certificates/admin/{replacement['id']}/revoke", json={"reason": "x"},
                       headers=admin).status_code == 200
    assert _verify(client, replacement["publicId"])["status"] == "revoked"


def test_legal_audit_reports_certificate_privacy(app):
    from app.services.legal_audit import implementation_facts

    with app.app_context():
        text = " ".join(line for section, line in implementation_facts() if section == "Certificates")
    assert "full name or initials" in text and "Never email" in text
