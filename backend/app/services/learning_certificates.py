"""WSF Learning certificates of completion — the ONE place certificates are
issued, revoked, reissued and rendered.

Issuance is backend-only and automatic: app/services/learning_enrollments.py
calls issue_certificate_if_eligible() inside the same transaction that sets
LearningEnrollment.completed_at from real lesson progress. Clients never
trigger issuance and their progress numbers are never trusted.

Eligibility (all required):
  * the program has certificate_enabled (explicit opt-in);
  * the program is WSF-owned: no partner provider Organization and not an
    external-enrollment program (WSF never certifies third-party learning);
  * the enrollment is active and has completed_at.

Idempotency/concurrency: at most one ACTIVE certificate per enrollment is
enforced by a partial unique index; an insert that loses a race is rolled
back to a SAVEPOINT and the existing certificate is returned.

Snapshot rule: recipient, program title, instructors, issuer, signatory and
completion date are copied at issue time and never re-derived, so renames,
instructor changes and new lessons never alter or revoke an issued
certificate. Corrections are revoke + reissue (new row, linked to the old).
"""
import io
import secrets
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.learning_certificate import (
    CERTIFICATE_TEMPLATE_VERSION,
    DEFAULT_CERTIFICATE_TITLE,
    LearningCertificate,
)
from app.utils.responses import ApiError

ISSUER_NAME = "Women Shaping Futures"
_NUMBER_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I ambiguity


def program_issues_certificates(program):
    """Whether this program issues WSF certificates at all (display + issue)."""
    return bool(
        program is not None
        and program.certificate_enabled
        and program.provider_organization_id is None
        and program.access_type != "external"
    )


def _program_code(program):
    letters = "".join(ch for ch in (program.slug or "").split("-")[0].upper() if ch.isalnum())
    return (letters[:4] or "WSF").ljust(3, "X")


def _new_certificate_number(program, year):
    suffix = "".join(secrets.choice(_NUMBER_ALPHABET) for _ in range(6))
    return f"WSF-{_program_code(program)}-{year}-{suffix}"


def _instructor_names(program):
    names = []
    if program.primary_instructor is not None:
        names.append(program.primary_instructor.name)
    names += [a.name for a in program.co_instructors or [] if a.name not in names]
    return names


def _recipient_name(user):
    full = getattr(user, "full_name", None) or " ".join(p for p in (user.first_name, user.last_name) if p)
    return (full or user.email.split("@")[0]).strip()


def active_certificate_for(enrollment):
    return LearningCertificate.query.filter_by(enrollment_id=enrollment.id, status="active").first()


def _build_certificate(enrollment, replaces=None):
    program = enrollment.learning_program
    completed_at = enrollment.completed_at or (replaces.completed_at if replaces else None)
    return LearningCertificate(
        certificate_number=_new_certificate_number(program, (completed_at or datetime.now(timezone.utc)).year),
        learning_program_id=program.id,
        enrollment_id=enrollment.id,
        user_id=enrollment.user_id,
        recipient_name=_recipient_name(enrollment.user),
        program_title=program.title,
        instructor_names=_instructor_names(program),
        issuer_name=ISSUER_NAME,
        certificate_title=(program.certificate_title or "").strip() or DEFAULT_CERTIFICATE_TITLE,
        signatory_name=program.certificate_signatory_name,
        signatory_title=program.certificate_signatory_title,
        completed_at=completed_at,
        template_version=CERTIFICATE_TEMPLATE_VERSION,
        status="active",
        replaces_certificate_id=replaces.id if replaces else None,
    )


def _insert(certificate):
    """Insert under a SAVEPOINT; on a lost race (another active certificate
    for this enrollment) roll back only the savepoint and return the winner;
    on a rare certificate-number collision, retry with a new number."""
    from app.models.learning import LearningProgram

    program = certificate.learning_program or db.session.get(LearningProgram, certificate.learning_program_id)
    for _attempt in range(3):
        try:
            with db.session.begin_nested():
                db.session.add(certificate)
            return certificate
        except IntegrityError:
            existing = LearningCertificate.query.filter_by(enrollment_id=certificate.enrollment_id, status="active").first()
            if existing is not None:
                return existing
            certificate.certificate_number = _new_certificate_number(program, certificate.completed_at.year)
    raise ApiError("Could not issue a certificate right now.", 503, code="certificate_issue_failed")


def issue_certificate_if_eligible(enrollment):
    """Called (uncommitted) from the completion flow. Returns the active
    certificate, newly created or pre-existing, or None when not eligible."""
    program = enrollment.learning_program
    if enrollment.status != "active" or enrollment.completed_at is None or not program_issues_certificates(program):
        return None
    existing = active_certificate_for(enrollment)
    if existing is not None:
        return existing
    certificate = _insert(_build_certificate(enrollment))
    _log("learning_certificate.issued", certificate, None)
    return certificate


def revoke_certificate(certificate, reason, actor):
    if certificate.status == "revoked":
        return certificate
    certificate.status = "revoked"
    certificate.revoked_at = datetime.now(timezone.utc)
    certificate.revocation_reason = (reason or "").strip()[:500] or None
    db.session.commit()
    _log("learning_certificate.revoked", certificate, actor, {"reason": certificate.revocation_reason})
    return certificate


def reissue_certificate(certificate, reason, actor):
    """Correction path: revoke the current certificate and issue a new one
    from the program/learner's CURRENT details (e.g. a corrected name),
    linked to the old one. The old certificate's facts are never edited."""
    if certificate.status == "active":
        certificate.status = "revoked"
        certificate.revoked_at = datetime.now(timezone.utc)
        certificate.revocation_reason = (reason or "Reissued with corrected details.").strip()[:500]
        db.session.flush()
    replacement = _insert(_build_certificate(certificate.enrollment, replaces=certificate))
    db.session.commit()
    _log("learning_certificate.reissued", replacement, actor, {"replaces": certificate.certificate_number})
    return replacement


def _log(action, certificate, actor, changes=None):
    from app.services.audit import log_action

    log_action(actor, action, "LearningCertificate", certificate.id, changes=changes or {"number": certificate.certificate_number})


# --- serialization --------------------------------------------------------------


def verification_url(certificate):
    base = (current_app.config.get("PUBLIC_SITE_URL") or current_app.config.get("FRONTEND_URL") or "").rstrip("/")
    return f"{base}/certificates/verify/{certificate.public_id}"


def linkedin_add_url(certificate):
    """LinkedIn's public "add licence/certification to profile" link —
    a plain URL, no API or connector."""
    from urllib.parse import urlencode

    issued = certificate.issued_at or datetime.now(timezone.utc)
    params = {
        "startTask": "CERTIFICATION_NAME",
        "name": f"{certificate.certificate_title}: {certificate.program_title}",
        "organizationName": certificate.issuer_name,
        "issueYear": issued.year,
        "issueMonth": issued.month,
        "certUrl": verification_url(certificate),
        "certId": certificate.certificate_number,
    }
    return "https://www.linkedin.com/profile/add?" + urlencode(params)


# --- public name display (Step 20) -------------------------------------------
# The certificate's recipient_name is part of its immutable issue-time
# snapshot. Whether PUBLIC verification shows it in full or as initials is
# the learner's own, live preference (users.certificate_public_name): it is
# applied at display time and never edits a certificate, so switching back
# and forth is always safe and needs no reissue. Owner and staff views, and
# the PDF, keep the full snapshot name.
CERTIFICATE_NAME_MODES = ("full", "initials")
DEFAULT_CERTIFICATE_NAME_MODE = "full"


def initials_of(name):
    """"Ada King-Lovelace" -> "A. K-L."; "Ada" -> "A."; never empty."""
    parts = []
    for word in (name or "").split():
        pieces = [p for p in word.split("-") if p]
        letters = [next((ch for ch in p if ch.isalpha()), "") for p in pieces]
        letters = [ch.upper() for ch in letters if ch]
        if letters:
            parts.append("-".join(letters) + ".")
    return " ".join(parts) or "—"


def certificate_name_mode(user):
    mode = getattr(user, "certificate_public_name", None)
    return mode if mode in CERTIFICATE_NAME_MODES else DEFAULT_CERTIFICATE_NAME_MODE


def public_recipient_name(certificate):
    if certificate_name_mode(certificate.user) == "initials":
        return initials_of(certificate.recipient_name)
    return certificate.recipient_name


def set_certificate_name_mode(user, mode):
    from app.services.audit import log_action

    if mode not in CERTIFICATE_NAME_MODES:
        raise ApiError("Choose how your name appears: full or initials.", 422, code="validation_error")
    previous = certificate_name_mode(user)
    user.certificate_public_name = mode
    db.session.commit()
    if previous != mode:
        log_action(user, "learning_certificate.name_display_changed", "User", user.id,
                   changes={"from": previous, "to": mode})
    return mode


def public_certificate_payload(certificate):
    """Public verification — safe credential facts only: no email, user id,
    enrollment id or internal ids. The name is shown in full or as initials,
    as the learner chose."""
    return {
        "publicId": certificate.public_id,
        "certificateNumber": certificate.certificate_number,
        "status": certificate.status,
        "certificateTitle": certificate.certificate_title,
        "recipientName": public_recipient_name(certificate),
        "recipientNameDisplay": certificate_name_mode(certificate.user),
        "programTitle": certificate.program_title,
        "instructorNames": list(certificate.instructor_names or []),
        "issuerName": certificate.issuer_name,
        "completedAt": certificate.completed_at.isoformat() if certificate.completed_at else None,
        "issuedAt": certificate.issued_at.isoformat() if certificate.issued_at else None,
        "revokedAt": certificate.revoked_at.isoformat() if certificate.revoked_at else None,
    }


def owner_certificate_payload(certificate):
    program = certificate.learning_program
    return {
        **public_certificate_payload(certificate),
        # The owner sees the full issued name and what the public sees.
        "recipientName": certificate.recipient_name,
        "publicRecipientName": public_recipient_name(certificate),
        "programSlug": program.slug if program is not None and program.status == "published" else None,
        "verificationUrl": verification_url(certificate),
        "linkedinUrl": linkedin_add_url(certificate) if certificate.status == "active" else None,
    }


def admin_certificate_payload(certificate):
    user = certificate.user
    return {
        **owner_certificate_payload(certificate),
        "id": certificate.id,
        "learnerEmail": user.email if user is not None else None,
        "learningProgramId": certificate.learning_program_id,
        "revocationReason": certificate.revocation_reason,
        "replacesCertificateId": certificate.replaces_certificate_id,
    }


# --- PDF ----------------------------------------------------------------------------

_CREAM = (0.953, 0.925, 0.882)
_PLUM = (0.278, 0.173, 0.239)
_BURGUNDY = (0.38, 0.106, 0.169)
_CHARCOAL = (0.141, 0.122, 0.129)


def _date_text(value):
    return f"{value.day} {value.strftime('%B %Y')}" if value else ""


def render_certificate_pdf(certificate):
    """Server-side PDF (reportlab), rendered on demand from the snapshot —
    deterministic for a given certificate, nothing stored on disk."""
    import qrcode
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    width, height = landscape(A4)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdf.setTitle(f"{certificate.certificate_title} — {certificate.program_title}")
    pdf.setAuthor(certificate.issuer_name)

    pdf.setFillColorRGB(*_CREAM)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.setStrokeColorRGB(*_PLUM)
    pdf.setLineWidth(2)
    pdf.rect(28, 28, width - 56, height - 56, stroke=1, fill=0)
    pdf.setLineWidth(0.6)
    pdf.rect(36, 36, width - 72, height - 72, stroke=1, fill=0)

    center = width / 2
    pdf.setFillColorRGB(*_PLUM)
    pdf.setFont("Times-Bold", 22)
    pdf.drawCentredString(center, height - 95, "Women Shaping Futures")
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColorRGB(*_BURGUNDY)
    pdf.drawCentredString(center, height - 110, "STORIES  ·  OPPORTUNITY  ·  GROWTH")

    pdf.setFillColorRGB(*_CHARCOAL)
    pdf.setFont("Times-Italic", 30)
    pdf.drawCentredString(center, height - 170, certificate.certificate_title)
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(center, height - 205, "This certifies that")
    pdf.setFont("Times-Bold", 34)
    pdf.setFillColorRGB(*_PLUM)
    pdf.drawCentredString(center, height - 248, certificate.recipient_name)
    pdf.setFillColorRGB(*_CHARCOAL)
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(center, height - 280, "has successfully completed")
    pdf.setFont("Times-Bold", 20)
    pdf.drawCentredString(center, height - 310, certificate.program_title[:90])
    if certificate.instructor_names:
        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(center, height - 332, "Taught by " + ", ".join(certificate.instructor_names)[:120])
    pdf.setFont("Helvetica", 10.5)
    pdf.drawCentredString(center, height - 356, f"Completed {_date_text(certificate.completed_at)}")

    left = 90
    if certificate.signatory_name:
        pdf.setLineWidth(0.8)
        pdf.line(left, 118, left + 200, 118)
        pdf.setFont("Times-Bold", 12)
        pdf.drawString(left, 102, certificate.signatory_name)
        if certificate.signatory_title:
            pdf.setFont("Helvetica", 9.5)
            pdf.drawString(left, 88, certificate.signatory_title)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(left, 66, f"Issued by {certificate.issuer_name} · {_date_text(certificate.issued_at)}")
    pdf.drawString(left, 54, f"Credential ID: {certificate.certificate_number}")

    url = verification_url(certificate)
    qr = qrcode.QRCode(border=1, box_size=4)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#472C3D", back_color="#F3ECE1").convert("RGB")
    qr_size = 82
    pdf.drawImage(ImageReader(image), width - 90 - qr_size, 62, qr_size, qr_size)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawRightString(width - 90, 52, "Verify: " + url[:90])
    if certificate.status == "revoked":
        pdf.setFont("Helvetica-Bold", 28)
        pdf.setFillColorRGB(*_BURGUNDY)
        pdf.drawCentredString(center, height / 2 + 120, "REVOKED")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
