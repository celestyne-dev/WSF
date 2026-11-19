"""WSF Learning certificates API.

  GET  /certificates/verify/<public_id>     public verification (safe facts only)
  GET  /certificates/me                     the learner's own certificates
  GET  /certificates/<public_id>/pdf        PDF — owner or learning.manage staff
  GET  /certificates/admin                  staff list (search/status/program)
  POST /certificates/admin/<id>/revoke      staff revoke
  POST /certificates/admin/<id>/reissue     staff revoke + reissue (correction)

Issuance itself is never an endpoint: certificates are created only by the
backend completion flow (app/services/learning_certificates.py).
"""
from flask import Blueprint, make_response, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.auth.decorators import active_user_required, permission_required
from app.extensions import db, limiter
from app.models.learning_certificate import CERTIFICATE_STATUSES, LearningCertificate
from app.models.user import User
from app.services.learning_certificates import (
    admin_certificate_payload,
    owner_certificate_payload,
    public_certificate_payload,
    reissue_certificate,
    render_certificate_pdf,
    revoke_certificate,
)
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

certificates_bp = Blueprint("certificates", __name__)
api = Api(certificates_bp)


def _by_public_id_or_404(public_id):
    certificate = LearningCertificate.query.filter_by(public_id=(public_id or "").strip()).first()
    if certificate is None:
        raise ApiError("Certificate not found.", 404, code="not_found")
    return certificate


def _viewer_or_none():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    return current_user if current_user and current_user.is_active else None


class CertificateVerifyResource(Resource):
    decorators = [limiter.limit("60 per minute")]

    def get(self, public_id):
        return success_response(public_certificate_payload(_by_public_id_or_404(public_id)))


class CertificateMeResource(Resource):
    @active_user_required
    def get(self):
        rows = (
            LearningCertificate.query.options(selectinload(LearningCertificate.learning_program))
            .filter_by(user_id=current_user.id)
            .order_by(LearningCertificate.issued_at.desc(), LearningCertificate.id.desc())
            .all()
        )
        return success_response([owner_certificate_payload(c) for c in rows])


class CertificatePdfResource(Resource):
    def get(self, public_id):
        certificate = _by_public_id_or_404(public_id)
        viewer = _viewer_or_none()
        if viewer is None:
            raise ApiError("Sign in to download this certificate.", 401, code="authorization_required")
        if viewer.id != certificate.user_id and not viewer.has_permission("learning.manage"):
            # Same 404 as an unknown id — never confirms someone else's certificate.
            raise ApiError("Certificate not found.", 404, code="not_found")
        response = make_response(render_certificate_pdf(certificate))
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{certificate.certificate_number}.pdf"'
        response.headers["Cache-Control"] = "private, no-store"
        return response


class CertificateAdminListResource(Resource):
    @permission_required("learning.manage")
    def get(self):
        query = LearningCertificate.query.options(
            selectinload(LearningCertificate.user), selectinload(LearningCertificate.learning_program)
        ).order_by(LearningCertificate.issued_at.desc(), LearningCertificate.id.desc())
        status = request.args.get("status")
        if status:
            if status not in CERTIFICATE_STATUSES:
                raise ApiError("Unknown status filter.", 422, code="invalid_filter")
            query = query.filter(LearningCertificate.status == status)
        program_id = request.args.get("programId", type=int)
        if program_id:
            query = query.filter(LearningCertificate.learning_program_id == program_id)
        q = (request.args.get("q") or "").strip()
        if q:
            like = f"%{q}%"
            query = query.join(User, LearningCertificate.user_id == User.id).filter(or_(
                LearningCertificate.recipient_name.ilike(like), LearningCertificate.certificate_number.ilike(like),
                LearningCertificate.program_title.ilike(like), User.email.ilike(like),
            ))
        result = paginate(query, None)
        return success_response([admin_certificate_payload(c) for c in result["items"]], meta=result["meta"])


def _admin_certificate_or_404(certificate_id):
    certificate = db.session.get(LearningCertificate, certificate_id)
    if certificate is None:
        raise ApiError("Certificate not found.", 404, code="not_found")
    return certificate


class CertificateAdminRevokeResource(Resource):
    @permission_required("learning.manage")
    def post(self, certificate_id):
        reason = (request.get_json(silent=True) or {}).get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ApiError("Give a reason for revoking this certificate.", 422, code="validation_error")
        certificate = revoke_certificate(_admin_certificate_or_404(certificate_id), reason, current_user)
        return success_response(admin_certificate_payload(certificate))


class CertificateAdminReissueResource(Resource):
    @permission_required("learning.manage")
    def post(self, certificate_id):
        reason = (request.get_json(silent=True) or {}).get("reason")
        replacement = reissue_certificate(_admin_certificate_or_404(certificate_id), reason, current_user)
        return success_response(admin_certificate_payload(replacement), status=201)


api.add_resource(CertificateVerifyResource, "/verify/<string:public_id>")
api.add_resource(CertificateMeResource, "/me")
api.add_resource(CertificatePdfResource, "/<string:public_id>/pdf")
api.add_resource(CertificateAdminListResource, "/admin")
api.add_resource(CertificateAdminRevokeResource, "/admin/<int:certificate_id>/revoke")
api.add_resource(CertificateAdminReissueResource, "/admin/<int:certificate_id>/reissue")
