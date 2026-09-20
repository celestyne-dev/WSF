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
#   media.py         Media, MediaVariant (see below)
#   cms.py           Page, PageSection, Menu, MenuItem, SiteSetting
#   analytics.py     AnalyticsEvent
#
# Each model carries created_at/updated_at timestamps, a status/audit trail
# where relevant, and slugs + SEO fields on public-facing content types.
#
# Media stores metadata and filesystem paths only — never binary image data
# — for files the Flask upload service (app/services/media.py) has written
# to MEDIA_ROOT on the Hostinger VPS:
#
#   Media
#     id, uuid, original_filename, stored_filename, file_path, public_url,
#     mime_type, original_format, delivered_format, width, height,
#     file_size, alt_text, caption, credit, copyright_source,
#     uploaded_by (FK -> User), created_at, updated_at
#
#   MediaVariant  (one-to-many from Media; one row per generated size)
#     id, media_id (FK -> Media), variant (thumbnail/card/medium/large/hero),
#     file_path, public_url, width, height, file_size
#
# Every content type that carries imagery (Article, Person, Author, Event,
# Resource, Job, Opportunity, Product, Sponsor, SiteSetting, ...)
# references Media by foreign key rather than storing a path string
# directly, so a single upload can be reused and so deleting a Media row
# can first check for inbound references.
