# SQLAlchemy models live here, one module per domain area. Every module is
# imported below so Flask-Migrate's autogenerate sees the full metadata.
# Planned modules beyond Phase 7 (added progressively, phase by phase):
#
#   advertising.py   Advertisement, AdCampaign, AdPlacement
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
from app.models.cms import (  # noqa: F401
    AdvertiseMetric,
    AdvertiseOffering,
    AdvertisePage,
    HomepageModule,
    Menu,
    MenuItem,
    SiteSetting,
    SocialLink,
)
from app.models.opportunity import Event, Job, Opportunity  # noqa: F401
from app.models.resource import Resource  # noqa: F401
from app.models.newsletter import NewsletterIssue, NewsletterSubscriber  # noqa: F401
from app.models.community import CommunityPage, Member, MemberNote  # noqa: F401
from app.models.commerce import Order, OrderItem, PartnershipInquiry, Product, Sponsor, SponsorPlacement  # noqa: F401
from app.models.mentorship import (  # noqa: F401
    MentorshipApplication,
    MentorshipApplicationNote,
    MentorshipMatch,
    MentorshipMatchNote,
    MentorshipProgram,
    MentorshipSession,
)
from app.models.submissions import StorySubmission, SubmissionMedia, SubmissionNote  # noqa: F401
from app.models.nominations import Nomination, NominationNote  # noqa: F401
from app.models.analytics import AnalyticsEvent  # noqa: F401

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
    "AdvertisePage",
    "AdvertiseMetric",
    "AdvertiseOffering",
    "Job",
    "Opportunity",
    "Event",
    "Resource",
    "NewsletterIssue",
    "NewsletterSubscriber",
    "Nomination",
    "NominationNote",
    "StorySubmission",
    "SubmissionNote",
    "SubmissionMedia",
    "Member",
    "MemberNote",
    "CommunityPage",
    "PartnershipInquiry",
    "Sponsor",
    "SponsorPlacement",
    "Product",
    "Order",
    "OrderItem",
    "MentorshipProgram",
    "MentorshipApplication",
    "MentorshipApplicationNote",
    "MentorshipMatch",
    "MentorshipMatchNote",
    "MentorshipSession",
    "AnalyticsEvent",
]
