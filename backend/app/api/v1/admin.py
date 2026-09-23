from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.api.v1.analytics import _last_six_month_boundaries
from app.auth.decorators import permission_required
from app.extensions import db
from app.models.analytics import AnalyticsEvent
from app.models.article import Article
from app.models.cms import HomepageModule, Menu, SiteSetting
from app.models.community import Nomination, StorySubmission
from app.models.newsletter import NewsletterSubscriber
from app.models.commerce import Sponsor
from app.models.opportunity import Event, Job, Opportunity
from app.models.user import Role, User
from app.schemas.article import article_summary_schema
from app.schemas.cms import (
    HomepageInputSchema,
    HomepageModuleSchema,
    MenuSchema,
    NavigationInputSchema,
    SiteSettingsInputSchema,
)
from app.schemas.commerce import SponsorSchema
from app.schemas.user import RoleSchema, UserSchema
from app.services.cms import replace_homepage_modules, replace_menu, replace_social_links, upsert_site_settings
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

admin_bp = Blueprint("admin", __name__)
api = Api(admin_bp)

user_schema = UserSchema()
role_schema = RoleSchema()
homepage_module_schema = HomepageModuleSchema()
menu_schema = MenuSchema()


def _require_article_admin_access():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    if not current_user.has_permission("articles.manage", "articles.edit_own"):
        raise ApiError("You do not have permission to view the article pipeline.", 403, code="forbidden")
    return current_user


class AdminArticleListResource(Resource):
    """Unlike the public article list (published only), this returns
    every status so the editorial pipeline (draft/in_review/scheduled/
    published/archived) is visible in the admin UI. A user who can only
    edit their own articles (articles.edit_own, not articles.manage) sees
    only articles they created or are the byline author of.
    """

    def get(self):
        user = _require_article_admin_access()
        query = Article.query
        if not user.has_permission("articles.manage"):
            query = query.filter(
                db.or_(Article.created_by_id == user.id, Article.author.has(user_id=user.id))
            )
        if request.args.get("status"):
            query = query.filter(Article.status == request.args["status"])
        query = apply_search(query, Article, request.args, ["title", "excerpt"], param="query")
        query = query.order_by(Article.updated_at.desc())
        result = paginate(query, None)
        items = article_summary_schema(many=True).dump(result["items"])
        return success_response(items, meta=result["meta"])


class AdminDashboardResource(Resource):
    """Aggregate counts and trends for the admin dashboard landing page.
    Every number here is a real query against existing tables — nothing
    is fabricated or hard-coded.
    """

    @permission_required("analytics.view")
    def get(self):
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        published_articles = Article.query.filter_by(status="published").count()
        drafts = Article.query.filter_by(status="draft").count()
        scheduled = Article.query.filter_by(status="scheduled").count()
        subscribers = NewsletterSubscriber.query.filter_by(status="active").count()
        active_jobs = Job.query.filter_by(status="published").count()
        active_opportunities = Opportunity.query.filter_by(status="published").count()
        upcoming_events = Event.query.filter_by(status="upcoming").count()
        pending_submissions = StorySubmission.query.filter_by(status="new").count()
        pending_nominations = Nomination.query.filter_by(status="new").count()

        boundaries, _ = _last_six_month_boundaries()

        page_views_trend = []
        for idx, start in enumerate(boundaries):
            end = boundaries[idx + 1] if idx + 1 < len(boundaries) else now
            count = AnalyticsEvent.query.filter(
                AnalyticsEvent.event_name == "article_view",
                AnalyticsEvent.created_at >= start,
                AnalyticsEvent.created_at < end,
            ).count()
            page_views_trend.append({"month": start.strftime("%b"), "views": count})

        top_rows = (
            db.session.query(
                AnalyticsEvent.payload.op("->>")("articleSlug").label("slug"),
                db.func.count(AnalyticsEvent.id).label("views"),
            )
            .filter(AnalyticsEvent.event_name == "article_view", AnalyticsEvent.created_at >= month_start)
            .group_by("slug")
            .order_by(db.func.count(AnalyticsEvent.id).desc())
            .limit(5)
            .all()
        )
        slug_to_title = {
            a.slug: a.title for a in Article.query.filter(Article.slug.in_([r.slug for r in top_rows if r.slug])).all()
        }
        top_articles_this_month = [
            {"title": slug_to_title.get(row.slug, row.slug), "views": row.views} for row in top_rows if row.slug
        ]

        return success_response(
            {
                "publishedArticles": published_articles,
                "drafts": drafts,
                "scheduled": scheduled,
                "subscribers": subscribers,
                "activeJobs": active_jobs,
                "activeOpportunities": active_opportunities,
                "upcomingEvents": upcoming_events,
                "pendingSubmissions": pending_submissions,
                "pendingNominations": pending_nominations,
                "pageViewsTrend": page_views_trend,
                "topArticlesThisMonth": top_articles_this_month,
            }
        )


class AdminUserListResource(Resource):
    @permission_required("users.manage")
    def get(self):
        query = User.query.order_by(User.created_at.desc())
        query = apply_search(query, User, request.args, ["email", "first_name", "last_name"])
        result = paginate(query, user_schema)
        return success_response(result["items"], meta=result["meta"])


class AdminRoleListResource(Resource):
    @permission_required("users.manage")
    def get(self):
        roles = Role.query.order_by(Role.name).all()
        return success_response(role_schema.dump(roles, many=True))


class AdminHomepageResource(Resource):
    """The homepage builder always reads/writes the full ordered module
    list — see app/services/cms.py:replace_homepage_modules.
    """

    @permission_required("settings.manage")
    def get(self):
        modules = HomepageModule.query.order_by(HomepageModule.sort_order).all()
        return success_response(homepage_module_schema.dump(modules, many=True))

    @permission_required("settings.manage")
    def put(self):
        data = HomepageInputSchema().load(request.get_json(silent=True) or {})
        replace_homepage_modules(data["modules"])
        db.session.commit()
        modules = HomepageModule.query.order_by(HomepageModule.sort_order).all()
        return success_response(homepage_module_schema.dump(modules, many=True))


class AdminNavigationResource(Resource):
    @permission_required("settings.manage")
    def get(self):
        menus = Menu.query.all()
        return success_response(menu_schema.dump(menus, many=True))

    @permission_required("settings.manage")
    def put(self):
        data = NavigationInputSchema().load(request.get_json(silent=True) or {})
        for menu_data in data["menus"]:
            replace_menu(menu_data["key"], menu_data.get("heading"), menu_data.get("items", []))
        if data.get("social_links"):
            replace_social_links(data["social_links"])
        db.session.commit()

        menus = Menu.query.all()
        return success_response(menu_schema.dump(menus, many=True))


class AdminSettingsResource(Resource):
    @permission_required("settings.manage")
    def get(self):
        settings = SiteSetting.query.all()
        return success_response({setting.key: setting.value for setting in settings})

    @permission_required("settings.manage")
    def put(self):
        data = SiteSettingsInputSchema().load(request.get_json(silent=True) or {})
        upsert_site_settings(data["settings"])
        db.session.commit()

        settings = SiteSetting.query.all()
        return success_response({setting.key: setting.value for setting in settings})


class AdminSponsorListResource(Resource):
    """Read-only list of active sponsorship deals, for the Job editor's
    sponsor selector. Full Sponsor CRUD lives in the dedicated Sponsors
    CMS (api/v1/sponsors.py) — this exists only so a Job can link to a
    real Sponsor record instead of requiring a raw ID.
    """

    @permission_required("jobs.manage")
    def get(self):
        sponsors = Sponsor.query.filter_by(status="active").order_by(Sponsor.created_at.desc()).all()
        return success_response(SponsorSchema(many=True).dump(sponsors))


api.add_resource(AdminUserListResource, "/users")
api.add_resource(AdminRoleListResource, "/roles")
api.add_resource(AdminHomepageResource, "/homepage")
api.add_resource(AdminNavigationResource, "/navigation")
api.add_resource(AdminSettingsResource, "/settings")
api.add_resource(AdminArticleListResource, "/articles")
api.add_resource(AdminDashboardResource, "/dashboard")
api.add_resource(AdminSponsorListResource, "/sponsors")
