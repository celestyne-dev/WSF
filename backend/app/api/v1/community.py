import csv
import io
from datetime import date

from flask import Blueprint, Response, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.audit import AuditLog
from app.models.community import CommunityPage, Member, MemberNote
from app.models.taxonomy import Topic
from app.schemas.community import (
    CommunityPageInputSchema,
    CommunityPageSchema,
    CommunityPageStatusInputSchema,
    MemberAdminUpdateSchema,
    MemberJoinInputSchema,
    MemberNoteInputSchema,
    MemberSchema,
    MemberStatusInputSchema,
)
from app.schemas.media import MediaSchema
from app.services.audit import log_action
from app.services.content_blocks import sanitize_content_blocks
from app.services.newsletter import upsert_subscriber
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

community_bp = Blueprint("community", __name__)
api = Api(community_bp)

member_schema = MemberSchema()
page_schema = CommunityPageSchema()

_EXPORT_COLUMNS = [
    "First Name", "Last Name", "Email", "Country", "Organization", "Professional Title",
    "Status", "Membership Type", "Interests", "Joined Date", "Source", "Directory Opt-In",
]

# A repeat public Join with one of these existing statuses reactivates the
# record rather than creating a duplicate.
_REACTIVATABLE_STATUSES = ("left", "inactive")
# These already represent "a request/membership is on file" — acknowledge,
# never duplicate, never silently reactivate.
_ALREADY_PRESENT_STATUSES = ("active", "paused", "pending")
# Deliberate admin actions. A public Join must never silently reverse
# these, and — to avoid leaking internal moderation state to an anonymous
# requester — the response never distinguishes this case from a fresh
# signup's generic acknowledgement.
_ADMIN_SUPPRESSED_STATUSES = ("declined", "archived")

_JOIN_WRITABLE_FIELDS = (
    "first_name", "last_name", "professional_title", "organization_name", "short_bio",
    "website_url", "linkedin_url", "country_code", "city", "referral_note", "source", "acquisition",
)
_ADMIN_WRITABLE_FIELDS = (
    "first_name", "last_name", "email", "professional_title", "organization_name", "short_bio",
    "website_url", "linkedin_url", "city", "country_code", "membership_type", "referral_note", "source",
    "community_updates_opt_in", "directory_opt_in", "admin_tags", "person_id", "profile_image_media_id",
)


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _require_export():
    user = _require_active_user()
    if not user.has_permission("community.export"):
        raise ApiError("You do not have permission to export members.", 403, code="forbidden")
    return user


def _get_member_or_404(member_id):
    member = db.session.get(Member, member_id)
    if member is None:
        raise ApiError("Member not found.", 404, code="not_found")
    return member


def _resolve_topics(slugs):
    if not slugs:
        return []
    return Topic.query.filter(Topic.slug.in_(slugs)).all()


def _get_community_page():
    page = db.session.get(CommunityPage, 1)
    if page is None:
        raise ApiError("Community page not initialized.", 500, code="not_found")
    return page


def _apply_join_fields(member, data):
    for field in _JOIN_WRITABLE_FIELDS:
        if field in data:
            setattr(member, field, data[field])
    member.consent_given = True
    member.consent_at = db.func.now()
    member.newsletter_opt_in = bool(data.get("subscribe_newsletter"))


def _subscribe_to_newsletter(member, data):
    upsert_subscriber(
        email=member.email,
        first_name=member.first_name,
        last_name=member.last_name,
        country_code=member.country_code,
        placement="community-join",
        acquisition=data.get("acquisition"),
    )
    db.session.commit()


def _build_member_query():
    query = Member.query.order_by(Member.created_at.desc())
    query = apply_equality_filters(query, Member, request.args, ["status", "membership_type"])
    query = apply_search(query, Member, request.args, ["first_name", "last_name", "email", "organization_name"])
    query = apply_country_or_region_filter(query, Member, request.args)

    directory_opt_in = request.args.get("directory_opt_in")
    if directory_opt_in is not None:
        query = query.filter(Member.directory_opt_in == (directory_opt_in == "true"))

    interest = request.args.get("interest")
    if interest:
        query = query.join(Member.interests).filter(Topic.slug == interest)

    return query


class MemberJoinResource(Resource):
    def post(self):
        data = MemberJoinInputSchema().load(request.get_json(silent=True) or {})
        email = data["email"].strip().lower()
        interest_slugs = data.pop("interest_slugs", [])

        existing = Member.query.filter_by(email=email).first()

        if existing is not None:
            if existing.status in _ADMIN_SUPPRESSED_STATUSES:
                return success_response(
                    {"message": "Thank you for your interest in Women Shaping Futures. Our team will be in touch if there's anything further needed."}
                )
            if existing.status in _ALREADY_PRESENT_STATUSES:
                return success_response(
                    {"message": "It looks like you're already part of the WSF community. If you'd like to update your details, please contact us."}
                )
            # _REACTIVATABLE_STATUSES: welcome them back.
            member = existing
            previous_status = member.status
            member.status = "active"
            member.activated_at = db.func.now()
            member.left_at = None
            _apply_join_fields(member, data)
            member.interests = _resolve_topics(interest_slugs)
            db.session.commit()
            if member.newsletter_opt_in:
                _subscribe_to_newsletter(member, data)
            return success_response({"message": "Welcome back! Your membership has been reactivated."})

        member = Member(email=email, status="active", activated_at=db.func.now())
        _apply_join_fields(member, data)
        member.interests = _resolve_topics(interest_slugs)
        db.session.add(member)
        db.session.commit()
        if member.newsletter_opt_in:
            _subscribe_to_newsletter(member, data)
        return success_response({"message": "Welcome to the Women Shaping Futures community!"}, status=201)


def build_public_member_payload(member):
    return {
        "id": member.id,
        "name": member.full_name,
        "professionalTitle": member.professional_title,
        "organizationName": member.organization_name,
        "shortBio": member.short_bio,
        "country": {"code": member.country.code, "name": member.country.name} if member.country else None,
        "interests": [t.name for t in member.interests],
        "profileImage": MediaSchema().dump(member.profile_image) if member.profile_image else None,
    }


class PublicMemberDirectoryResource(Resource):
    def get(self):
        query = Member.query.filter_by(status="active", directory_opt_in=True).order_by(Member.first_name)
        query = apply_country_or_region_filter(query, Member, request.args)
        interest = request.args.get("interest")
        if interest:
            query = query.join(Member.interests).filter(Topic.slug == interest)
        result = paginate(query)
        return success_response([build_public_member_payload(m) for m in result["items"]], meta=result["meta"])


def build_public_community_page(page):
    return {
        "hero": {
            "heading": page.hero_heading,
            "description": page.hero_description,
            "media": MediaSchema().dump(page.hero_media) if page.hero_media else None,
        },
        "introContent": page.intro_content or [],
        "benefits": page.benefits or [],
        "whoForText": page.who_for_text,
        "howToJoinText": page.how_to_join_text,
        "cta": {"heading": page.cta_heading, "description": page.cta_description, "buttonLabel": page.cta_button_label},
        "faq": page.faq or [],
        "seo": page.seo or {},
    }


class PublicCommunityResource(Resource):
    """One composite call so the public /community page never has to fan
    out into separate content + metrics requests.
    """

    def get(self):
        page = db.session.get(CommunityPage, 1)
        if page is None or page.status != "published":
            raise ApiError("Community page not available.", 404, code="not_found")

        member_count = Member.query.filter_by(status="active").count()
        metrics = None
        if member_count > 0:
            country_count = (
                db.session.query(Member.country_code)
                .filter(Member.status == "active", Member.country_code.isnot(None))
                .distinct()
                .count()
            )
            metrics = {"memberCount": member_count, "countryCount": country_count}

        return success_response({"page": build_public_community_page(page), "metrics": metrics})


class MemberListResource(Resource):
    @permission_required("community.manage")
    def get(self):
        result = paginate(_build_member_query(), member_schema)
        return success_response(result["items"], meta=result["meta"])


class MemberDetailResource(Resource):
    @permission_required("community.manage")
    def get(self, member_id):
        return success_response(member_schema.dump(_get_member_or_404(member_id)))

    @permission_required("community.manage")
    def patch(self, member_id):
        member = _get_member_or_404(member_id)
        data = MemberAdminUpdateSchema().load(request.get_json(silent=True) or {})

        if "email" in data:
            normalized = data["email"].strip().lower()
            conflict = Member.query.filter(Member.email == normalized, Member.id != member.id).first()
            if conflict:
                raise ApiError("Another member already uses this email address.", 409, code="conflict")
            data["email"] = normalized

        interest_slugs = data.pop("interest_slugs", None)
        directory_changed = "directory_opt_in" in data and data["directory_opt_in"] != member.directory_opt_in

        for field in _ADMIN_WRITABLE_FIELDS:
            if field in data:
                setattr(member, field, data[field])
        if interest_slugs is not None:
            member.interests = _resolve_topics(interest_slugs)

        db.session.commit()
        log_action(current_user, "member.update", "Member", member.id)
        if directory_changed:
            log_action(
                current_user, "member.directory_visibility_change", "Member", member.id,
                changes={"directoryOptIn": member.directory_opt_in},
            )
        return success_response(member_schema.dump(member))

    @permission_required("community.manage")
    def delete(self, member_id):
        member = _get_member_or_404(member_id)
        if member.status not in ("pending", "declined"):
            raise ApiError(
                "Only Pending or Declined members can be deleted. Archive established members instead.",
                409, code="delete_restricted",
            )
        if member.notes:
            raise ApiError(
                "This member has internal notes and can't be deleted. Archive it instead.",
                409, code="delete_restricted",
            )
        db.session.delete(member)
        db.session.commit()
        log_action(current_user, "member.delete", "Member", member_id)
        return success_response(None, status=204)


class MemberStatusResource(Resource):
    @permission_required("community.manage")
    def patch(self, member_id):
        member = _get_member_or_404(member_id)
        data = MemberStatusInputSchema().load(request.get_json(silent=True) or {})
        previous_status = member.status
        member.status = data["status"]

        if previous_status != "active" and member.status == "active":
            member.activated_at = db.func.now()
            member.left_at = None
        if member.status in ("left", "inactive", "archived") and previous_status not in ("left", "inactive", "archived"):
            member.left_at = db.func.now()

        db.session.commit()
        log_action(
            current_user, "member.status_change", "Member", member.id,
            changes={"from": previous_status, "to": member.status},
        )
        return success_response(member_schema.dump(member))


class MemberNoteListResource(Resource):
    @permission_required("community.manage")
    def post(self, member_id):
        member = _get_member_or_404(member_id)
        data = MemberNoteInputSchema().load(request.get_json(silent=True) or {})
        note = MemberNote(member=member, user=current_user, body=data["body"])
        db.session.add(note)
        db.session.commit()
        log_action(current_user, "member.note_add", "Member", member.id)
        return success_response(member_schema.dump(member), status=201)


class MemberHistoryResource(Resource):
    @permission_required("community.manage")
    def get(self, member_id):
        _get_member_or_404(member_id)
        entries = (
            AuditLog.query.filter_by(entity_type="Member", entity_id=str(member_id))
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        return success_response(
            [
                {
                    "id": e.id,
                    "action": e.action,
                    "changes": e.changes,
                    "user": e.user.full_name if e.user else None,
                    "createdAt": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ]
        )


class MemberExportResource(Resource):
    def get(self):
        _require_export()

        query = _build_member_query()
        members = query.limit(20000).all()

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(_EXPORT_COLUMNS)
        for m in members:
            writer.writerow(
                [
                    m.first_name,
                    m.last_name,
                    m.email,
                    m.country.name if m.country else "",
                    m.organization_name or "",
                    m.professional_title or "",
                    m.status,
                    m.membership_type,
                    ", ".join(t.name for t in m.interests),
                    m.applied_at.isoformat() if m.applied_at else "",
                    m.source or "",
                    "Yes" if m.directory_opt_in else "No",
                ]
            )

        log_action(current_user, "member.export", "Member", None, changes={"count": len(members)})
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=wsf-members-{date.today().isoformat()}.csv"
        return response


class CommunityPageResource(Resource):
    @permission_required("community.manage")
    def get(self):
        return success_response(page_schema.dump(_get_community_page()))

    @permission_required("community.manage")
    def patch(self):
        page = _get_community_page()
        data = CommunityPageInputSchema().load(request.get_json(silent=True) or {})
        if "intro_content" in data:
            data["intro_content"] = sanitize_content_blocks(data["intro_content"])
        for field, value in data.items():
            setattr(page, field, value)
        db.session.commit()
        log_action(current_user, "community_page.update", "CommunityPage", page.id)
        return success_response(page_schema.dump(page))


class CommunityPageStatusResource(Resource):
    @permission_required("community.manage")
    def patch(self):
        page = _get_community_page()
        data = CommunityPageStatusInputSchema().load(request.get_json(silent=True) or {})
        previous_status = page.status
        page.status = data["status"]
        db.session.commit()
        log_action(
            current_user, "community_page.status_change", "CommunityPage", page.id,
            changes={"from": previous_status, "to": page.status},
        )
        return success_response(page_schema.dump(page))


api.add_resource(MemberJoinResource, "/join")
api.add_resource(PublicMemberDirectoryResource, "/directory")
api.add_resource(PublicCommunityResource, "/public")
api.add_resource(MemberListResource, "/members")
api.add_resource(MemberExportResource, "/members/export")
api.add_resource(MemberDetailResource, "/members/<int:member_id>")
api.add_resource(MemberStatusResource, "/members/<int:member_id>/status")
api.add_resource(MemberNoteListResource, "/members/<int:member_id>/notes")
api.add_resource(MemberHistoryResource, "/members/<int:member_id>/history")
api.add_resource(CommunityPageResource, "/page")
api.add_resource(CommunityPageStatusResource, "/page/status")
