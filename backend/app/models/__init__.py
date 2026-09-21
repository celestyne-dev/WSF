# SQLAlchemy models live here, one module per domain area. Every module is
# imported below so Flask-Migrate's autogenerate sees the full metadata.
# Planned modules beyond Phase 1 (added progressively, phase by phase):
#
#   article.py       Article, ArticleRevision, Redirect
#   taxonomy.py       Topic, Category, Tag, Series
#   people.py        Person, Author, Organization
#   opportunity.py   Job, Opportunity, Event
#   resource.py      Resource, Course
#   community.py     MentorshipApplication, StorySubmission, Nomination
#   newsletter.py    NewsletterSubscriber, NewsletterIssue
#   commerce.py      Partner, PartnershipInquiry, Sponsor, Product, Order,
#                    OrderItem, Transaction
#   advertising.py   Advertisement, AdCampaign, AdPlacement
#   cms.py           Page, PageSection, Menu, MenuItem, SiteSetting
#   analytics.py     AnalyticsEvent
#
# Each model carries created_at/updated_at timestamps, a status/audit trail
# where relevant, and slugs + SEO fields on public-facing content types.
from app.models.geography import Country  # noqa: F401
from app.models.media import Media, MediaVariant  # noqa: F401
from app.models.user import Permission, Role, User  # noqa: F401
from app.models.token_blocklist import TokenBlocklist  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401

__all__ = [
    "Country",
    "Media",
    "MediaVariant",
    "Permission",
    "Role",
    "User",
    "TokenBlocklist",
    "AuditLog",
]
