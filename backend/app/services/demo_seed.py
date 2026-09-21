"""Seeds a representative slice of realistic content — enough to verify
the real API end-to-end against the frontend, not a full mirror of
frontend/src/mock/*.js. Idempotent: re-running updates existing rows by
slug rather than duplicating them.
"""
from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models.article import Article
from app.models.cms import HomepageModule, SiteSetting
from app.models.opportunity import Event, Job, Opportunity
from app.models.people import Author, Organization, Person
from app.models.resource import Resource
from app.models.taxonomy import Category, Series, Tag, Topic
from app.services.cms import replace_menu, replace_social_links, upsert_site_settings

TOPICS = [
    ("leadership", "Leadership", "Leadership journeys, communication, and managing teams."),
    ("careers", "Career", "Career development, job search, interviews, and career transitions."),
    ("business", "Business", "Running and growing a business."),
    ("entrepreneurship", "Entrepreneurship", "Founders, funding, and building a company from nothing."),
    ("workplace", "Workplace", "Workplace culture and professional relationships."),
    ("personal-growth", "Personal Growth", "Confidence, resilience, and purpose."),
    ("money", "Money", "General career-economics education."),
    ("opportunities", "Opportunities", "Jobs, scholarships, fellowships, and grants."),
    ("women-impact", "Women & Impact", "Founder stories and voices from around the world."),
]


def _get_or_create_topic(slug, name, description):
    topic = Topic.query.filter_by(slug=slug).first()
    if topic is None:
        topic = Topic(slug=slug, name=name, description=description)
        db.session.add(topic)
    else:
        topic.name, topic.description = name, description
    return topic


def _get_or_create_author(slug, **fields):
    author = Author.query.filter_by(slug=slug).first()
    if author is None:
        author = Author(slug=slug, **fields)
        db.session.add(author)
    else:
        for key, value in fields.items():
            setattr(author, key, value)
    return author


def _get_or_create_person(slug, **fields):
    person = Person.query.filter_by(slug=slug).first()
    if person is None:
        person = Person(slug=slug, **fields)
        db.session.add(person)
    else:
        for key, value in fields.items():
            setattr(person, key, value)
    return person


def _get_or_create_organization(slug, **fields):
    org = Organization.query.filter_by(slug=slug).first()
    if org is None:
        org = Organization(slug=slug, **fields)
        db.session.add(org)
    else:
        for key, value in fields.items():
            setattr(org, key, value)
    return org


def seed_demo_content():
    topics = {slug: _get_or_create_topic(slug, name, desc) for slug, name, desc in TOPICS}
    db.session.flush()

    category = Category.query.filter_by(slug="editorial").first()
    if category is None:
        category = Category(slug="editorial", name="Editorial")
        db.session.add(category)

    series = Series.query.filter_by(slug="women-doing-incredible-things").first()
    if series is None:
        series = Series(
            slug="women-doing-incredible-things",
            name="Women Doing Incredible Things",
            description="Our flagship profile series celebrating women whose work deserves a wider audience.",
            featured=True,
        )
        db.session.add(series)

    amara = _get_or_create_author(
        "amara-otieno",
        name="Amara Otieno",
        role="Senior Editor, Leadership & Business",
        bio="Amara covers leadership, workplace culture, and the business of ambition.",
        short_bio="Senior Editor covering leadership, business, and workplace culture.",
        expertise=["Leadership", "Workplace", "Business"],
        location="Nairobi, Kenya",
        country_code="KE",
    )
    jordan = _get_or_create_author(
        "jordan-ellis",
        name="Jordan Ellis",
        role="Senior Writer, Business & Money",
        bio="Jordan covers business strategy, compensation, and the economics of career growth.",
        short_bio="Senior Writer covering business, money, and career economics.",
        expertise=["Business", "Money", "Career"],
        location="New York, United States",
        country_code="US",
    )
    db.session.flush()

    kaziwave = _get_or_create_organization(
        "kaziwave",
        name="Kaziwave",
        industry="Financial Technology",
        country_code="KE",
        org_type="Startup",
        description="Kaziwave builds payroll and benefits infrastructure for small businesses across East Africa.",
        featured=True,
    )
    lumen = _get_or_create_organization(
        "lumen-analytics",
        name="Lumen Analytics",
        industry="Workforce Technology",
        country_code="US",
        org_type="Startup",
        description="Lumen Analytics builds workforce planning software for mid-market employers.",
        featured=True,
    )
    db.session.flush()

    naliaka = _get_or_create_person(
        "naliaka-wafula",
        name="Naliaka Wafula",
        title="Chief Executive Officer",
        organization=kaziwave,
        location="Nairobi, Kenya",
        country_code="KE",
        industry="Financial Technology",
        profession="Founder & CEO",
        expertise=["Fintech", "Leadership", "Fundraising"],
        featured_quote="I stopped waiting to feel ready. Readiness is a story you tell yourself after you've already started.",
        short_bio="Founder and CEO of Kaziwave, building payroll infrastructure for East African small businesses.",
        bio="Naliaka Wafula founded Kaziwave in 2020 after a decade in banking convinced her that small businesses were being failed by outdated payroll systems.",
        achievements=["Raised $6.2M in Series A funding in 2023", "Named to the Africa Fintech 40 Under 40 list"],
        career_timeline=[{"year": "2020", "title": "Founder & CEO, Kaziwave"}],
        awards=["Africa Fintech 40 Under 40 (2023)"],
        featured=True,
    )
    danielle = _get_or_create_person(
        "danielle-reyes",
        name="Danielle Reyes",
        title="Chief Executive Officer",
        organization=lumen,
        location="Austin, Texas, United States",
        country_code="US",
        industry="Workforce Technology",
        profession="Founder & CEO",
        expertise=["SaaS", "Leadership", "Product"],
        short_bio="Founder and CEO of Lumen Analytics, building workforce planning software from Austin.",
        bio="Danielle Reyes founded Lumen Analytics in 2019 to help mid-market employers plan their workforce with real data.",
        featured=True,
    )
    db.session.flush()

    article_specs = [
        {
            "slug": "how-women-are-redefining-leadership",
            "title": "How Women Are Redefining Leadership in 2026",
            "subtitle": "A new generation of executives is rejecting the leadership playbook they inherited.",
            "excerpt": "From boardrooms in Nairobi to founder desks in Lagos, women are trading command-and-control leadership for something more direct and human.",
            "author": amara,
            "topics": ["leadership", "workplace"],
            "tags": ["executive-leadership", "management"],
            "related_people": [naliaka],
            "featured": True,
            "days_ago": 5,
        },
        {
            "slug": "building-a-saas-company-from-austin-not-silicon-valley",
            "title": "Building a SaaS Company From Austin, Not Silicon Valley",
            "subtitle": "Danielle Reyes on why she never moved to the Bay Area.",
            "excerpt": "Lumen Analytics has raised two rounds and grown to 40 employees without a Silicon Valley address.",
            "author": jordan,
            "topics": ["entrepreneurship", "business"],
            "tags": ["saas", "founders"],
            "related_people": [danielle],
            "featured": True,
            "days_ago": 2,
        },
        {
            "slug": "the-negotiation-conversation-nobody-prepares-you-for",
            "title": "The Negotiation Conversation Nobody Prepares You For",
            "subtitle": "What to say when a counteroffer isn't enough.",
            "excerpt": "Career coaches share the exact language that turns a stalled negotiation into a signed offer.",
            "author": amara,
            "topics": ["careers", "money"],
            "tags": ["negotiation"],
            "related_people": [],
            "featured": False,
            "days_ago": 9,
        },
    ]

    articles = {}
    for spec in article_specs:
        article = Article.query.filter_by(slug=spec["slug"]).first()
        if article is None:
            article = Article(slug=spec["slug"])
            db.session.add(article)
        article.title = spec["title"]
        article.subtitle = spec["subtitle"]
        article.excerpt = spec["excerpt"]
        article.author = spec["author"]
        article.category = category
        article.status = "published"
        article.publish_date = datetime.now(timezone.utc) - timedelta(days=spec["days_ago"])
        article.reading_time = 6
        article.featured = spec["featured"]
        article.topics = [topics[slug] for slug in spec["topics"]]
        article.related_people = spec["related_people"]
        article.content = [
            {"type": "paragraph", "text": spec["excerpt"]},
            {"type": "paragraph", "text": "Demo seed content for local verification of the real backend."},
        ]

        tags = []
        for tag_name in spec["tags"]:
            tag = Tag.query.filter_by(slug=tag_name).first()
            if tag is None:
                tag = Tag(slug=tag_name, name=tag_name.replace("-", " ").title())
                db.session.add(tag)
            tags.append(tag)
        article.tags = tags
        articles[spec["slug"]] = article

    db.session.flush()
    articles["how-women-are-redefining-leadership"].related_articles = [
        articles["building-a-saas-company-from-austin-not-silicon-valley"],
        articles["the-negotiation-conversation-nobody-prepares-you-for"],
    ]

    job = Job.query.filter_by(slug="senior-product-manager-lumen-analytics").first()
    if job is None:
        job = Job(slug="senior-product-manager-lumen-analytics")
        db.session.add(job)
    job.title = "Senior Product Manager"
    job.organization = lumen
    job.company_name = "Lumen Analytics"
    job.location = "Austin, Texas, United States"
    job.country_code = "US"
    job.work_mode = "Hybrid"
    job.employment_type = "Full-time"
    job.career_level = "Senior"
    job.industry = "Workforce Technology"
    job.salary_min, job.salary_max, job.currency, job.salary_period = 145000, 175000, "USD", "year"
    job.description = "Own our workforce planning product line as we expand into two new market segments."
    job.responsibilities = ["Own the product roadmap", "Partner with design and engineering"]
    job.requirements = ["6+ years in product management"]
    job.benefits = ["Health insurance", "401(k) match"]
    job.application_url = "https://lumenanalytics.example.com/careers/senior-product-manager"
    job.deadline = date.today() + timedelta(days=30)
    job.published_date = date.today()
    job.featured = True
    job.status = "published"

    opportunity = Opportunity.query.filter_by(slug="rising-leaders-fellowship").first()
    if opportunity is None:
        opportunity = Opportunity(slug="rising-leaders-fellowship")
        db.session.add(opportunity)
    opportunity.title = "Rising Leaders Fellowship"
    opportunity.organization_name = "Foster Capital"
    opportunity.type = "Fellowship"
    opportunity.description = "A six-month fellowship for women in mid-career technology and finance roles."
    opportunity.eligibility = "Women with 5-12 years of professional experience."
    opportunity.location = "Hybrid — quarterly in-person sessions in London and New York"
    opportunity.deadline = date.today() + timedelta(days=60)
    opportunity.funding_value = "$10,000 grant + executive mentorship"
    opportunity.application_url = "https://fostercapital.example.com/rising-leaders"
    opportunity.featured = True
    opportunity.status = "published"
    opportunity.topics = [topics["leadership"], topics["careers"]]
    db.session.flush()

    from app.models.geography import Country

    opportunity.countries_eligible = Country.query.filter(Country.code.in_(["US", "GB", "CA"])).all()

    event = Event.query.filter_by(slug="women-in-leadership-summit").first()
    if event is None:
        event = Event(slug="women-in-leadership-summit")
        db.session.add(event)
    event.title = "Women in Leadership Summit 2026"
    event.description = "Our flagship annual summit bringing together executives, founders, and policymakers."
    event.type = "Conference"
    event.format = "in-person"
    event.date = date.today() + timedelta(days=90)
    event.location = "Nairobi, Kenya"
    event.country_code = "KE"
    event.venue = "Kenyatta International Convention Centre"
    event.registration_url = "/events/women-in-leadership-summit/register"
    event.ticket_price, event.currency = 8500, "KES"
    event.capacity = 450
    event.agenda = [{"time": "08:30", "title": "Registration & Breakfast"}]
    event.status = "upcoming"
    event.featured = True
    event.speakers = [naliaka]

    resource = Resource.query.filter_by(slug="career-planning-guide").first()
    if resource is None:
        resource = Resource(slug="career-planning-guide")
        db.session.add(resource)
    resource.name = "The 5-Year Career Planning Guide"
    resource.description = "A structured, worksheet-driven guide for mapping out your next five years."
    resource.type = "Guide"
    resource.topic = topics["careers"]
    resource.author = amara
    resource.price, resource.currency = 0, "USD"
    resource.is_premium = False
    resource.featured = True
    resource.status = "published"

    # Navigation + social links
    replace_menu(
        "primary",
        None,
        [
            {"label": "Stories", "url": "/topics"},
            {
                "label": "People",
                "url": "/people",
                "children": [
                    {"label": "People Directory", "url": "/people"},
                    {"label": "Authors", "url": "/authors"},
                    {"label": "Series", "url": "/series"},
                ],
            },
            {"label": "Opportunities", "url": "/opportunities"},
            {"label": "Resources", "url": "/resources"},
        ],
    )
    replace_menu("secondary", None, [{"label": "Newsletter", "url": "/newsletter"}, {"label": "About", "url": "/about"}])
    replace_menu(
        "footer_explore",
        "Explore",
        [{"label": "Stories", "url": "/topics"}, {"label": "People", "url": "/people"}],
    )
    replace_menu(
        "footer_opportunity",
        "Opportunity",
        [{"label": "Jobs", "url": "/jobs"}, {"label": "Opportunities", "url": "/opportunities"}],
    )
    replace_menu("footer_wsf", "WSF", [{"label": "About", "url": "/about"}, {"label": "Partnerships", "url": "/partnerships"}])
    replace_menu("footer_legal", "Legal", [{"label": "Privacy Policy", "url": "/privacy"}, {"label": "Terms of Use", "url": "/terms"}])
    replace_social_links(
        [
            {"platform": "linkedin", "url": "https://linkedin.com/company/womenshapingfutures", "handle": "Women Shaping Futures"},
            {"platform": "instagram", "url": "https://instagram.com/womenshapingfutures", "handle": "@womenshapingfutures"},
        ]
    )

    # Homepage modules
    HomepageModule.query.delete()
    db.session.add(
        HomepageModule(
            type="hero",
            enabled=True,
            sort_order=0,
            selection_mode="manual",
            config={
                "leadArticleSlug": "how-women-are-redefining-leadership",
                "secondaryArticleSlugs": ["building-a-saas-company-from-austin-not-silicon-valley"],
            },
        )
    )
    db.session.add(
        HomepageModule(
            type="latest_stories",
            enabled=True,
            sort_order=1,
            heading="Latest Stories",
            selection_mode="automatic",
            config={"itemCount": 8},
        )
    )
    db.session.add(
        HomepageModule(
            type="featured_woman",
            enabled=True,
            sort_order=2,
            heading="Women Shaping Futures Spotlight",
            selection_mode="manual",
            config={"personSlug": "danielle-reyes"},
        )
    )

    # Site settings
    upsert_site_settings(
        {
            "audience_stats": {
                "linkedinFollowers": 132000,
                "linkedinAvgReach": 480000,
                "linkedinEngagementRate": 0.061,
                "newsletterSubscribers": 34210,
                "monthlyWebsiteVisitors": 210000,
                "monthlyPageViews": 812400,
                "countriesReached": 42,
                "audienceGeography": [
                    {"region": "North America", "percent": 38},
                    {"region": "Africa", "percent": 24},
                    {"region": "Europe", "percent": 17},
                    {"region": "Asia", "percent": 10},
                    {"region": "Latin America & Caribbean", "percent": 6},
                    {"region": "Middle East", "percent": 3},
                    {"region": "Oceania", "percent": 2},
                ],
                "audienceIndustries": [
                    {"name": "Technology", "percent": 24},
                    {"name": "Financial Services", "percent": 18},
                    {"name": "Professional Services", "percent": 15},
                    {"name": "Healthcare & Life Sciences", "percent": 11},
                    {"name": "Nonprofit & Education", "percent": 10},
                    {"name": "Other", "percent": 22},
                ],
                "audienceSeniority": [
                    {"level": "Manager", "percent": 28},
                    {"level": "Director / Senior Manager", "percent": 26},
                    {"level": "VP / Executive", "percent": 19},
                    {"level": "Founder / C-Suite", "percent": 15},
                    {"level": "Individual Contributor", "percent": 12},
                ],
            },
            "newsletter_stats": {"openRate": 0.47, "weeklySends": 1},
        }
    )

    db.session.commit()
