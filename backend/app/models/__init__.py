# SQLAlchemy models live here, one module per domain area. Every module is
# imported below so Flask-Migrate's autogenerate sees the full metadata.
# Planned modules beyond Phase 6 (added progressively, phase by phase):
#
#   commerce.py additions: Product, Order, OrderItem, Transaction (Phase 7)
#   advertising.py   Advertisement, AdCampaign, AdPlacement
#   analytics.py     AnalyticsEvent
#
# Each model carries created_at/updated_at timestamps, a status/audit trail
# where relevant, and slugs + SEO fields on public-facing content types.
from app.models.geography import Country  # noqa: F401
from app.models.media import Media, MediaVariant  # noqa: F401
from app.models.user import Permission, Role, User  # noqa: F401
from app.models.token_blocklist import TokenBlocklist  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.taxonomy import Category, Series, Tag, Topic  # noqa: F401
from app.models.people import Author, Organization, Person  # noqa: F401
from app.models.article import Article, ArticleRevision, Redirect  # noqa: F401
from app.models.cms import HomepageModule, Menu, MenuItem, SiteSetting, SocialLink  # noqa: F401
from app.models.opportunity import Event, Job, Opportunity  # noqa: F401
from app.models.resource import Resource  # noqa: F401
from app.models.newsletter import NewsletterIssue, NewsletterSubscriber  # noqa: F401
from app.models.community import Nomination, StorySubmission  # noqa: F401
from app.models.commerce import PartnershipInquiry, Sponsor  # noqa: F401

__all__ = [
    "Country",
    "Media",
    "MediaVariant",
    "Permission",
    "Role",
    "User",
    "TokenBlocklist",
    "AuditLog",
    "Category",
    "Series",
    "Tag",
    "Topic",
    "Author",
    "Organization",
    "Person",
    "Article",
    "ArticleRevision",
    "Redirect",
    "HomepageModule",
    "Menu",
    "MenuItem",
    "SiteSetting",
    "SocialLink",
    "Job",
    "Opportunity",
    "Event",
    "Resource",
    "NewsletterIssue",
    "NewsletterSubscriber",
    "Nomination",
    "StorySubmission",
    "PartnershipInquiry",
    "Sponsor",
]
