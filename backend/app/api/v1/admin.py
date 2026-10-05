from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.api.v1.analytics import _last_six_month_boundaries
from app.auth.decorators import permission_required
from app.extensions import db
from app.models.analytics import AnalyticsEvent
from app.models.article import Article
from app.models.cms import HomepageModule, Menu, SiteSetting, SocialLink
from app.models.newsletter import NewsletterSubscriber
from app.models.commerce import Sponsor
from app.models.nominations import Nomination
from app.models.opportunity import Event, Job, Opportunity
from app.models.people import Author
from app.models.submissions import StorySubmission
from app.schemas.article import admin_article_summary_schema
from app.schemas.cms import (
    FooterGroupSchema,
    FooterInputSchema,
    HomepageInputSchema,
    HomepageModuleSchema,
    MenuSchema,
    NavigationInputSchema,
    SiteIdentityInputSchema,
    SiteIdentitySchema,
    SocialLinkSchema,
)
from app.schemas.commerce import SponsorSchema
from app.services.audit import log_action
from app.services.cms import (
    replace_footer_groups,
    replace_homepage_modules,
    replace_menu,
    replace_social_links,
    upsert_site_settings,
)
from app.services.footer import FOOTER_MENU_KEY_PREFIX, FOOTER_SETTINGS_KEY, get_footer_menus, get_footer_settings
from app.services.homepage import modules_with_warnings
from app.services.navigation import find_duplicate_top_level_destinations
from app.services.site_settings import SITE_IDENTITY_KEY, get_site_identity_resolved, save_site_identity
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

admin_bp = Blueprint("admin", __name__)
api = Api(admin_bp)

homepage_module_schema = HomepageModuleSchema()
menu_schema = MenuSchema()
footer_group_schema = FooterGroupSchema()
social_link_schema = SocialLinkSchema()
site_identity_schema = SiteIdentitySchema()


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
        if request.args.get("author"):
            query = query.join(Author).filter(Author.slug == request.args["author"])
        if request.args.get("topic"):
            query = query.filter(Article.topics.any(slug=request.args["topic"]))
        query = apply_search(query, Article, request.args, ["title", "excerpt"], param="query")
        query = query.order_by(Article.updated_at.desc())
        result = paginate(query, None)
        # admin_article_summary_schema (not the public article_summary_schema)
        # — this pipeline view needs scheduled_at/approved_at/approved_by
        # visible so the list can show real workflow state (see that
        # schema's own docstring in app/schemas/article.py).
        items = admin_article_summary_schema(many=True).dump(result["items"])
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
        # "upcoming" is never a stored Event.status (see EVENT_STATUSES) —
        # it's computed from date, exactly like EventSchema.get_is_upcoming.
        # Filtering by status="upcoming" here always matched zero rows.
        today = now.date()
        upcoming_events = Event.query.filter(
            Event.status == "published",
            db.func.coalesce(Event.end_date, Event.date) >= today,
        ).count()
        pending_submissions = StorySubmission.query.filter_by(status="submitted").count()
        pending_nominations = Nomination.query.filter_by(status="submitted").count()

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


class AdminHomepageResource(Resource):
    """The homepage builder always reads/writes the full ordered module
    list — see app/services/cms.py:replace_homepage_modules. Gated by its
    own homepage.manage/homepage.publish permissions (not settings.manage,
    which Navigation/Site Settings keep using unchanged) so Editors — who
    have no reason to touch Navigation or global Settings — can still run
    the homepage day to day, matching how Article/Pages split .manage from
    .publish. There's no separate draft copy: PUT is the save action *and*
    the publish action in one atomic replace, so `homepage.manage` alone
    already implies "can publish" (same OR-semantics as pages.publish).
    """

    @permission_required("homepage.manage")
    def get(self):
        modules = HomepageModule.query.order_by(HomepageModule.sort_order).all()
        warnings = modules_with_warnings(modules)
        data = homepage_module_schema.dump(modules, many=True)
        for row in data:
            row["warnings"] = warnings.get(row["id"], [])
        return success_response(data)

    @permission_required("homepage.publish", "homepage.manage")
    def put(self):
        data = HomepageInputSchema().load(request.get_json(silent=True) or {})
        replace_homepage_modules(data["modules"])
        log_action(
            current_user,
            "homepage.publish",
            "HomepageModule",
            changes={"module_count": len(data["modules"]), "types": [m["type"] for m in data["modules"]]},
        )
        db.session.commit()
        modules = HomepageModule.query.order_by(HomepageModule.sort_order).all()
        return success_response(homepage_module_schema.dump(modules, many=True))


def _dump_menus_with_duplicate_warnings():
    menus = Menu.query.all()
    dumped = menu_schema.dump(menus, many=True)
    for menu, menu_data in zip(menus, dumped):
        duplicates = find_duplicate_top_level_destinations(menu.top_level_items())
        for item_data in menu_data["items"]:
            item_data["warnings"] = list(item_data.get("warnings") or []) + duplicates.get(item_data["id"], [])
    return dumped


class AdminNavigationResource(Resource):
    """Gated by its own navigation.manage/navigation.publish permissions
    (not settings.manage, which Site Settings keeps using unchanged) —
    same reasoning as Homepage's split: Editors have a real reason to
    reorder/relabel navigation day to day, but no reason to touch global
    Settings. PUT replaces whichever menu keys are included in the
    payload (existing behavior, unchanged) — an omitted menu key is left
    exactly as it was, so a save that only touches "primary" can never
    wipe the footer menus.

    Any footer_* key (see app/services/footer.py's FOOTER_MENU_KEY_PREFIX)
    is a Menu row Footer CMS owns and gates behind its own footer.manage/
    footer.publish permissions (see AdminFooterResource below) — a caller
    who holds only navigation.manage must not be able to reach that same
    row through this endpoint instead. Enforced here, server-side, not
    just by the admin UI omitting footer_* from its editable menu list
    (see frontend's EDITABLE_MENUS): the whole request is rejected before
    anything is written whenever it touches a footer_* key the caller
    isn't authorized for, so a payload can never partially save (e.g. a
    legitimate "primary" update bundled with a footer_* key the caller
    can't touch never silently applies the primary half).
    """

    @permission_required("navigation.manage")
    def get(self):
        return success_response(_dump_menus_with_duplicate_warnings())

    @permission_required("navigation.publish", "navigation.manage")
    def put(self):
        data = NavigationInputSchema().load(request.get_json(silent=True) or {})
        footer_keys = [m["key"] for m in data["menus"] if m["key"].startswith(FOOTER_MENU_KEY_PREFIX)]
        if footer_keys and not current_user.has_permission("footer.manage", "footer.publish"):
            raise ApiError(
                "You do not have permission to modify footer menu groups. Use Footer CMS instead.",
                403,
                code="forbidden",
            )
        for menu_data in data["menus"]:
            replace_menu(menu_data["key"], menu_data.get("heading"), menu_data.get("items", []))
        if data.get("social_links"):
            replace_social_links(data["social_links"])
        log_action(
            current_user,
            "navigation.publish",
            "Menu",
            changes={"menu_keys": [m["key"] for m in data["menus"]]},
        )
        db.session.commit()

        return success_response(_dump_menus_with_duplicate_warnings())


def _dump_footer_groups_with_warnings():
    menus = get_footer_menus()
    dumped = footer_group_schema.dump(menus, many=True)
    for menu, menu_data in zip(menus, dumped):
        duplicates = find_duplicate_top_level_destinations(menu.top_level_items())
        for item_data in menu_data["items"]:
            item_data["warnings"] = list(item_data.get("warnings") or []) + duplicates.get(item_data["id"], [])
    return dumped


def _dump_footer():
    social_links = SocialLink.query.order_by(SocialLink.sort_order).all()
    return {
        "groups": _dump_footer_groups_with_warnings(),
        "socialLinks": social_link_schema.dump(social_links, many=True),
        "settings": get_footer_settings(),
    }


class AdminFooterResource(Resource):
    """Footer CMS's own dedicated endpoint — gated by footer.manage/
    footer.publish (not settings.manage, which global Site Settings keeps
    using unchanged, or navigation.manage, even though footer groups are
    Menu/MenuItem rows under the hood — see Menu's docstring). GET/PUT
    cover groups + social links + the small branding/newsletter/contact/
    copyright settings blob as one atomic save (see FooterInputSchema's
    docstring for why this differs from Navigation's per-menu-key partial
    save): the whole footer is one page with one "Save & publish" action,
    so there's no partial-key ambiguity to preserve.
    """

    @permission_required("footer.manage")
    def get(self):
        return success_response(_dump_footer())

    @permission_required("footer.publish", "footer.manage")
    def put(self):
        data = FooterInputSchema().load(request.get_json(silent=True) or {})
        replace_footer_groups(data["groups"])
        replace_social_links(data["social_links"])
        # FooterSettingsInputSchema.load() returns snake_case keys (its
        # Python attribute names) — re-keyed to camelCase before storage
        # so the "footer" SiteSetting blob matches get_footer_settings()'s
        # DEFAULT_FOOTER_SETTINGS and every consumer's expected shape
        # (same camelCase convention every other SiteSetting blob, e.g.
        # "site_identity"/"audience_stats", already uses).
        settings_data = data["settings"]
        footer_settings = {
            "brandDescription": settings_data.get("brand_description", ""),
            "newsletterHeading": settings_data.get("newsletter_heading", ""),
            "newsletterDescription": settings_data.get("newsletter_description", ""),
            "newsletterVisible": settings_data.get("newsletter_visible", True),
            "contactEmail": settings_data.get("contact_email", ""),
            "copyrightText": settings_data.get("copyright_text", ""),
        }
        upsert_site_settings({FOOTER_SETTINGS_KEY: footer_settings})
        log_action(
            current_user,
            "footer.publish",
            "Menu",
            changes={"group_count": len(data["groups"]), "social_link_count": len(data["social_links"])},
        )
        db.session.commit()

        return success_response(_dump_footer())


ADMIN_SETTINGS_KEYS = {"audience_stats", SITE_IDENTITY_KEY}


class AdminSettingsResource(Resource):
    """Site Settings / Global Configuration — see
    app/services/site_settings.py for what this does and does not own.

    Only two controlled SiteSetting keys are ever read/written here:
    "site_identity" (this module — validated against SiteIdentityInputSchema,
    never a raw dict) and the pre-existing "audience_stats" (Partnerships'
    media-kit numbers; passed through unvalidated exactly as before this
    module existed — that shape belongs to Partnerships, not here). Any
    other key is rejected outright: the old fields.Dict(required=True)
    passthrough this replaces let any string become a permanent, unused
    row from a single typo (e.g. "site_nmae").
    """

    @permission_required("settings.manage")
    def get(self):
        return success_response(self._dump())

    @permission_required("settings.manage")
    def put(self):
        payload = request.get_json(silent=True) or {}
        settings_data = payload.get("settings")
        if not isinstance(settings_data, dict):
            raise ApiError("settings must be an object.", 422, code="validation_error")

        unknown_keys = set(settings_data) - ADMIN_SETTINGS_KEYS
        if unknown_keys:
            raise ApiError(
                f"Unknown settings key(s): {', '.join(sorted(unknown_keys))}.",
                422,
                code="validation_error",
            )

        if SITE_IDENTITY_KEY in settings_data:
            identity_data = SiteIdentityInputSchema().load(settings_data[SITE_IDENTITY_KEY])
            save_site_identity(identity_data)
            log_action(
                current_user,
                "settings.update",
                "SiteSetting",
                entity_id=SITE_IDENTITY_KEY,
                changes={"site_name": identity_data["site_name"]},
            )

        if "audience_stats" in settings_data:
            audience_value = settings_data["audience_stats"]
            if not isinstance(audience_value, dict):
                raise ApiError("audience_stats must be an object.", 422, code="validation_error")
            upsert_site_settings({"audience_stats": audience_value})

        db.session.commit()
        return success_response(self._dump())

    def _dump(self):
        audience_setting = db.session.get(SiteSetting, "audience_stats")
        return {
            "audience_stats": audience_setting.value if audience_setting else None,
            SITE_IDENTITY_KEY: site_identity_schema.dump(get_site_identity_resolved()),
        }


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


api.add_resource(AdminHomepageResource, "/homepage")
api.add_resource(AdminNavigationResource, "/navigation")
api.add_resource(AdminFooterResource, "/footer")
api.add_resource(AdminSettingsResource, "/settings")
api.add_resource(AdminArticleListResource, "/articles")
api.add_resource(AdminDashboardResource, "/dashboard")
api.add_resource(AdminSponsorListResource, "/sponsors")
