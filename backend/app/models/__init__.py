# SQLAlchemy models live here, one module per domain area, imported into
# Flask-Migrate's metadata via this package. Planned modules (Phase 1 first):
#
#   user.py          User, Role, Permission
#   article.py       Article, ArticleRevision, Redirect
#   taxonomy.py       Topic, Category, Tag, Series
#   people.py        Person, Author, Organization
#   opportunity.py   Job, Opportunity, Event
#   resource.py      Resource, Course (Phase 2)
#   community.py     Mentor, MentorshipApplication, StorySubmission, Nomination
#   newsletter.py    NewsletterSubscriber, NewsletterIssue
#   commerce.py      Partner, PartnershipInquiry, Sponsor, Product, Order,
#                    OrderItem, Transaction, Membership (Phase 2/3)
#   advertising.py   Advertisement, AdCampaign, AdPlacement
#   media.py         MediaAsset
#   cms.py           Page, PageSection, Menu, MenuItem, SiteSetting
#   analytics.py     AnalyticsEvent
#
# Each model carries created_at/updated_at timestamps, a status/audit trail
# where relevant, and slugs + SEO fields on public-facing content types.
