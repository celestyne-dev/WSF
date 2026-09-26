"""Seeds a representative slice of realistic content — enough to verify
the real API end-to-end against the frontend, not a full mirror of
frontend/src/mock/*.js. Idempotent: re-running updates existing rows by
slug rather than duplicating them.
"""
from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models.article import Article
from app.models.cms import HomepageModule, Menu, MenuItem, SiteSetting, SocialLink
from app.models.opportunity import Event, EventSpeaker, EventSponsor, Job, Opportunity
from app.models.page import Page
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


def _seed_menu_if_empty(key, heading, items_data):
    """Unlike replace_menu() (used for a deliberate admin save, where
    fully replacing a menu's items is exactly what's wanted), seeding must
    never overwrite a menu an admin has already configured — this checks
    for any existing items under `key` first and skips entirely if found,
    matching the create-only convention used for Homepage/Pages seeding.
    """
    menu = Menu.query.filter_by(key=key).first()
    if menu is not None and MenuItem.query.filter_by(menu_id=menu.id).first() is not None:
        return
    replace_menu(key, heading, items_data)


def _seed_social_links_if_empty(links_data):
    """replace_social_links() is a deliberate full-replace for an admin
    save; seeding must never wipe social links an admin has already
    configured through AdminFooter, so this skips entirely if any row
    already exists — same create-only convention as _seed_menu_if_empty.
    """
    if SocialLink.query.first() is not None:
        return
    replace_social_links(links_data)


def _seed_setting_if_absent(key, value):
    """Like _seed_menu_if_empty: seeding a SiteSetting key must never
    overwrite a value an admin has already saved (e.g. via AdminFooter's
    branding/newsletter CTA/contact/copyright fields).
    """
    if db.session.get(SiteSetting, key) is not None:
        return
    upsert_site_settings({key: value})


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


def _get_or_create_event(slug):
    event = Event.query.filter_by(slug=slug).first()
    if event is None:
        event = Event(slug=slug)
        db.session.add(event)
    return event


# Unlike every _get_or_create_* helper above (which update existing rows
# on re-seed), pages are administrator-edited legal/informational content:
# a reseed must never clobber a page a real admin has already changed. So
# this only ever creates a system page's row once, on the run where it's
# first missing, and otherwise leaves it alone entirely (see
# _seed_pages()). The wording below is migrated verbatim from what
# frontend/src/pages/AboutPage.jsx, ContactPage.jsx, and LegalPage.jsx
# used to hard-code, so the public site's content doesn't change the
# moment this phase ships.
def _heading(text):
    return {"type": "heading", "text": text}


def _paragraph(text):
    return {"type": "paragraph", "text": text}


def _list(items):
    return {"type": "list", "items": items}


SYSTEM_PAGE_SEEDS = {
    "about": dict(
        title="A platform built to move women forward",
        subtitle=(
            "Women Shaping Futures started in 2019 as a small LinkedIn page sharing stories of women in "
            "business. Today, we're a global editorial and opportunity platform reaching women worldwide."
        ),
        content=[
            _heading("Our mission"),
            _paragraph(
                "We exist to amplify women's stories, connect women with opportunity, and equip them with the "
                "resources to lead, grow, and shape their own futures. We believe representation matters — but "
                "representation without access to jobs, mentors, and capital is incomplete. That's why we built "
                "more than a media brand: a platform spanning journalism, community, opportunity, and education."
            ),
            _heading("What we do"),
            _list(
                [
                    "<strong>Inspire</strong> — profiles, interviews, and stories of women shaping their industries.",
                    "<strong>Inform</strong> — original journalism, guides, and expert-driven advice.",
                    "<strong>Connect</strong> — a directory of people, mentors, organizations, and events.",
                    "<strong>Educate</strong> — resources, workshops, and learning tracks.",
                    "<strong>Create opportunity</strong> — jobs, grants, scholarships, and fellowships.",
                ]
            ),
            _heading("Editorial standards"),
            _paragraph(
                "Every story we publish is fact-checked and edited to a professional publishing standard. "
                "Sponsored content is always clearly disclosed and never disguised as independent editorial. "
                "Read our full Editorial Policy for details on sourcing, corrections, and disclosure."
            ),
        ],
        seo={
            "title": "About Women Shaping Futures",
            "description": "Women Shaping Futures is a global media, opportunity, and community platform for ambitious women.",
        },
    ),
    "contact": dict(
        title="Get in Touch",
        subtitle="Reach the right team, faster.",
        content=[
            _heading("Editorial"),
            _paragraph(
                'Story tips, corrections, and press inquiries. '
                '<a href="mailto:editorial@womenshapingfutures.org">editorial@womenshapingfutures.org</a>'
            ),
            _heading("Partnerships"),
            _paragraph(
                'Sponsorships, advertising, and brand collaborations. '
                '<a href="mailto:partnerships@womenshapingfutures.org">partnerships@womenshapingfutures.org</a>'
            ),
            _heading("General"),
            _paragraph(
                'Everything else, including account support. '
                '<a href="mailto:hello@womenshapingfutures.org">hello@womenshapingfutures.org</a>'
            ),
            _paragraph("Nairobi, Kenya — serving a global audience"),
        ],
        seo={
            "title": "Contact | Women Shaping Futures",
            "description": "Get in touch with the Women Shaping Futures editorial, partnerships, and support teams.",
        },
    ),
    "privacy": dict(
        title="Privacy Policy",
        subtitle=(
            "This Privacy Policy explains what information Women Shaping Futures collects, how we use it, "
            "and the choices you have."
        ),
        content=[
            _heading("Information we collect"),
            _paragraph(
                "We collect information you provide directly (such as newsletter sign-ups, story submissions, "
                "and account details) and information collected automatically (such as pages visited and "
                "device data)."
            ),
            _heading("How we use your information"),
            _paragraph(
                "We use your information to deliver our newsletter, personalize content, respond to inquiries, "
                "and improve our platform."
            ),
            _heading("Your choices"),
            _paragraph(
                "You may unsubscribe from our newsletter at any time and request deletion of your personal "
                "data by contacting privacy@womenshapingfutures.org."
            ),
        ],
        seo={"title": "Privacy Policy | Women Shaping Futures"},
    ),
    "terms": dict(
        title="Terms of Use",
        subtitle="By accessing Women Shaping Futures, you agree to these Terms of Use.",
        content=[
            _heading("Use of content"),
            _paragraph(
                "Content on this site is for personal, non-commercial use. Republishing requires written permission."
            ),
            _heading("User submissions"),
            _paragraph(
                "By submitting a story or nomination, you grant Women Shaping Futures a license to edit and "
                "publish the content if selected."
            ),
            _heading("Limitation of liability"),
            _paragraph(
                "Women Shaping Futures is not liable for outcomes related to third-party jobs, opportunities, "
                "or events listed on this platform."
            ),
        ],
        seo={"title": "Terms of Use | Women Shaping Futures"},
    ),
    "cookies": dict(
        title="Cookie Policy",
        subtitle=(
            "We use cookies to operate our website, remember your preferences, and understand how our "
            "platform is used."
        ),
        content=[
            _heading("Essential cookies"),
            _paragraph("Required for core site functionality, such as navigation and account access."),
            _heading("Analytics cookies"),
            _paragraph("Help us understand traffic patterns so we can improve our content and platform."),
            _heading("Managing cookies"),
            _paragraph("You can control cookies through your browser settings at any time."),
        ],
        seo={"title": "Cookie Policy | Women Shaping Futures"},
    ),
    "editorial-policy": dict(
        title="Editorial Policy",
        subtitle="Women Shaping Futures is committed to accurate, fair, and transparent journalism.",
        content=[
            _heading("Sourcing & fact-checking"),
            _paragraph(
                "Every published article is reviewed by an editor and fact-checked against primary sources "
                "where possible."
            ),
            _heading("Sponsored content disclosure"),
            _paragraph(
                "Sponsored articles are clearly labeled and never presented as independent editorial judgment."
            ),
            _heading("Corrections"),
            _paragraph(
                "We correct errors promptly and transparently. Report a correction to "
                "editorial@womenshapingfutures.org."
            ),
        ],
        seo={"title": "Editorial Policy | Women Shaping Futures"},
    ),
}


def _seed_pages():
    """Create-only: a page that already exists (whether seeded before or
    since edited by an admin) is left completely untouched, unlike the
    update-on-reseed helpers above — see the module docstring above
    SYSTEM_PAGE_SEEDS for why.
    """
    for key, fields in SYSTEM_PAGE_SEEDS.items():
        if Page.query.filter_by(key=key).first() is not None:
            continue
        db.session.add(
            Page(
                key=key,
                slug=key,
                page_type="system",
                title=fields["title"],
                subtitle=fields.get("subtitle"),
                content=fields["content"],
                seo=fields.get("seo"),
                status="published",
                published_at=db.func.now(),
            )
        )


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
        org_type="company",
        description="Kaziwave builds payroll and benefits infrastructure for small businesses across East Africa.",
        featured=True,
    )
    lumen = _get_or_create_organization(
        "lumen-analytics",
        name="Lumen Analytics",
        industry="Workforce Technology",
        country_code="US",
        org_type="company",
        description="Lumen Analytics builds workforce planning software for mid-market employers.",
        featured=True,
    )
    harrow_vance = _get_or_create_organization(
        "harrow-vance",
        name="Harrow & Vance",
        industry="Marketing & Communications",
        country_code="GB",
        org_type="company",
        description="Harrow & Vance is a London-based brand and communications agency for growth-stage consumer companies.",
    )
    maple_ridge = _get_or_create_organization(
        "maple-ridge-capital",
        name="Maple Ridge Capital",
        industry="Financial Services",
        country_code="CA",
        org_type="company",
        description="Maple Ridge Capital is a Toronto-based investment firm managing capital for mid-market growth companies.",
    )
    northstar = _get_or_create_organization(
        "northstar-collective",
        name="Northstar Collective",
        industry="Communications",
        country_code="US",
        org_type="company",
        description="Northstar Collective is a fully remote communications and public relations firm working with purpose-driven brands worldwide.",
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

    job_specs = [
        {
            "slug": "senior-product-manager-lumen-analytics",
            "title": "Senior Product Manager",
            "organization": lumen,
            "company_name": "Lumen Analytics",
            "city": "Austin",
            "location": "Austin, Texas, United States",
            "country_code": "US",
            "work_mode": "Hybrid",
            "employment_type": "Full-time",
            "career_level": "Senior",
            "industry": "Technology",
            "salary_min": 145000,
            "salary_max": 175000,
            "currency": "USD",
            "salary_period": "year",
            "short_description": "Own our workforce planning product line as Lumen Analytics expands into two new market segments.",
            "description": [
                {"type": "paragraph", "text": "Lumen Analytics is hiring a Senior Product Manager to own our workforce planning product line end to end, from roadmap through launch, as we expand into two new market segments this year."},
            ],
            "responsibilities": [
                "Own the product roadmap for our workforce planning suite",
                "Partner with design and engineering on quarterly release planning",
                "Run customer discovery with mid-market HR and people-ops leaders",
                "Define and track success metrics for each release",
            ],
            "requirements": [
                "6+ years in product management, ideally in B2B SaaS",
                "Experience shipping enterprise or mid-market software",
                "Strong written communication and stakeholder management",
            ],
            "qualifications": ["Bachelor's degree or equivalent practical experience"],
            "skills": ["Product strategy", "SQL", "Roadmapping", "Cross-functional leadership"],
            "benefits": ["Health, dental & vision insurance", "Hybrid-friendly", "401(k) match", "Annual learning budget"],
            "application_url": "https://lumenanalytics.example.com/careers/senior-product-manager",
            "deadline_days": 30,
            "featured": True,
        },
        {
            "slug": "marketing-director-harrow-vance",
            "title": "Marketing Director",
            "organization": harrow_vance,
            "company_name": "Harrow & Vance",
            "city": "London",
            "location": "London, United Kingdom",
            "country_code": "GB",
            "work_mode": "Hybrid",
            "employment_type": "Full-time",
            "career_level": "Director",
            "industry": "Marketing",
            "salary_min": 75000,
            "salary_max": 95000,
            "currency": "GBP",
            "salary_period": "year",
            "short_description": "Lead brand and growth marketing for Harrow & Vance's portfolio of consumer clients.",
            "description": [
                {"type": "paragraph", "text": "Harrow & Vance is looking for a Marketing Director to lead brand strategy and growth marketing across our portfolio of consumer-facing clients, managing a team of six."},
            ],
            "responsibilities": [
                "Set brand and growth marketing strategy across client accounts",
                "Manage and mentor a team of six marketers",
                "Own agency-wide campaign performance reporting",
            ],
            "requirements": [
                "8+ years in marketing, with 3+ in a leadership role",
                "Agency or in-house consumer brand experience",
            ],
            "qualifications": ["Bachelor's degree in marketing, communications, or related field"],
            "skills": ["Brand strategy", "Team leadership", "Campaign analytics", "Client management"],
            "benefits": ["Private healthcare", "25 days annual leave", "Hybrid working", "Professional development budget"],
            "application_url": "https://harrowvance.example.co.uk/careers/marketing-director",
            "deadline_days": 35,
            "featured": True,
        },
        {
            "slug": "senior-financial-analyst-maple-ridge-capital",
            "title": "Senior Financial Analyst",
            "organization": maple_ridge,
            "company_name": "Maple Ridge Capital",
            "city": "Toronto",
            "location": "Toronto, Ontario, Canada",
            "country_code": "CA",
            "work_mode": "On-site",
            "employment_type": "Full-time",
            "career_level": "Senior",
            "industry": "Finance",
            "salary_min": 95000,
            "salary_max": 115000,
            "currency": "CAD",
            "salary_period": "year",
            "short_description": "Build financial models and diligence memos for Maple Ridge Capital's mid-market investment team.",
            "description": [
                {"type": "paragraph", "text": "Maple Ridge Capital is hiring a Senior Financial Analyst to support our investment team with financial modeling, diligence, and portfolio monitoring for mid-market growth companies."},
            ],
            "responsibilities": [
                "Build and maintain financial models for prospective investments",
                "Prepare diligence memos and present findings to the investment committee",
                "Monitor portfolio company performance against quarterly targets",
            ],
            "requirements": [
                "4+ years in investment banking, private equity, or corporate finance",
                "Advanced Excel and financial modeling skills",
            ],
            "qualifications": ["CFA designation or in progress is an asset"],
            "skills": ["Financial modeling", "Valuation", "Diligence", "Portfolio analysis"],
            "benefits": ["Extended health benefits", "RRSP matching", "Performance bonus"],
            "application_url": "https://mapleridgecapital.example.ca/careers/senior-financial-analyst",
            "deadline_days": 21,
            "featured": False,
        },
        {
            "slug": "head-of-operations-kaziwave",
            "title": "Head of Operations",
            "organization": kaziwave,
            "company_name": "Kaziwave",
            "city": "Nairobi",
            "location": "Nairobi, Kenya",
            "country_code": "KE",
            "work_mode": "On-site",
            "employment_type": "Full-time",
            "career_level": "Director",
            "industry": "Operations",
            "salary_min": 4200000,
            "salary_max": 5400000,
            "currency": "KES",
            "salary_period": "year",
            "short_description": "Scale Kaziwave's operations as it expands payroll infrastructure across East Africa.",
            "description": [
                {"type": "paragraph", "text": "Kaziwave is hiring a Head of Operations to build the processes and team that will support our expansion into three new East African markets over the next 18 months."},
            ],
            "responsibilities": [
                "Design and scale operational processes across customer support, compliance, and payments",
                "Build and lead an operations team as we expand into new markets",
                "Partner with the CEO on quarterly operating plans",
            ],
            "requirements": [
                "7+ years in operations, with experience scaling a startup",
                "Experience in fintech or payments is a strong plus",
            ],
            "qualifications": ["Bachelor's degree in business, operations, or related field"],
            "skills": ["Process design", "Team leadership", "Cross-market expansion", "Vendor management"],
            "benefits": ["Medical cover for employee and dependents", "Performance bonus", "Professional development budget"],
            "application_url": "https://kaziwave.example.com/careers/head-of-operations",
            "deadline_days": 28,
            "featured": True,
        },
        {
            "slug": "business-development-lead-kaziwave",
            "title": "Business Development Lead",
            "organization": kaziwave,
            "company_name": "Kaziwave",
            "city": "Nairobi",
            "location": "Nairobi, Kenya",
            "country_code": "KE",
            "work_mode": "Hybrid",
            "employment_type": "Full-time",
            "career_level": "Mid-level",
            "industry": "Business Development",
            "salary_min": 2800000,
            "salary_max": 3600000,
            "currency": "KES",
            "salary_period": "year",
            "short_description": "Grow Kaziwave's small-business customer base across East Africa through new partnerships.",
            "description": [
                {"type": "paragraph", "text": "Kaziwave is hiring a Business Development Lead to build partnerships with SACCOs, business associations, and financial institutions that bring small businesses onto our payroll platform."},
            ],
            "responsibilities": [
                "Identify and close new partnership and channel opportunities",
                "Manage a pipeline of mid-to-late-stage partnership conversations",
                "Represent Kaziwave at industry events across the region",
            ],
            "requirements": [
                "3+ years in business development, partnerships, or sales",
                "Experience working with SMEs or financial institutions",
            ],
            "qualifications": [],
            "skills": ["Partnership development", "Negotiation", "Pipeline management"],
            "benefits": ["Medical cover", "Commission on closed partnerships", "Hybrid working"],
            "application_url": "https://kaziwave.example.com/careers/business-development-lead",
            "deadline_days": 25,
            "featured": False,
        },
        {
            "slug": "communications-manager-northstar-collective",
            "title": "Communications Manager",
            "organization": northstar,
            "company_name": "Northstar Collective",
            "city": None,
            "location": "Remote — Worldwide",
            "country_code": None,
            "work_mode": "Remote",
            "remote_scope": "worldwide",
            "employment_type": "Full-time",
            "career_level": "Mid-level",
            "industry": "Communications",
            "salary_min": 68000,
            "salary_max": 82000,
            "currency": "USD",
            "salary_period": "year",
            "short_description": "Lead media relations and messaging for purpose-driven clients, from anywhere in the world.",
            "description": [
                {"type": "paragraph", "text": "Northstar Collective is a fully remote communications firm looking for a Communications Manager to lead media relations and messaging strategy for a portfolio of purpose-driven clients."},
            ],
            "responsibilities": [
                "Develop and execute media relations strategy for client accounts",
                "Draft press releases, talking points, and executive messaging",
                "Track and report on earned media coverage",
            ],
            "requirements": [
                "4+ years in communications, PR, or journalism",
                "Proven media relationships across business or trade press",
            ],
            "qualifications": ["Bachelor's degree in communications, journalism, or related field"],
            "skills": ["Media relations", "Executive messaging", "Crisis communications"],
            "benefits": ["Fully remote", "Flexible hours across time zones", "Home office stipend", "Unlimited PTO"],
            "application_url": "https://northstarcollective.example.com/careers/communications-manager",
            "deadline_days": 40,
            "featured": False,
        },
    ]

    for spec in job_specs:
        job = Job.query.filter_by(slug=spec["slug"]).first()
        if job is None:
            job = Job(slug=spec["slug"])
            db.session.add(job)
        job.title = spec["title"]
        job.organization = spec["organization"]
        job.company_name = spec["company_name"]
        job.city = spec["city"]
        job.location = spec["location"]
        job.country_code = spec["country_code"]
        job.work_mode = spec["work_mode"]
        job.remote_scope = spec.get("remote_scope")
        job.employment_type = spec["employment_type"]
        job.career_level = spec["career_level"]
        job.industry = spec["industry"]
        job.salary_min = spec["salary_min"]
        job.salary_max = spec["salary_max"]
        job.currency = spec["currency"]
        job.salary_period = spec["salary_period"]
        job.salary_visible = True
        job.short_description = spec["short_description"]
        job.description = spec["description"]
        job.responsibilities = spec["responsibilities"]
        job.requirements = spec["requirements"]
        job.qualifications = spec["qualifications"]
        job.skills = spec["skills"]
        job.benefits = spec["benefits"]
        job.application_url = spec["application_url"]
        job.deadline = date.today() + timedelta(days=spec["deadline_days"])
        job.published_date = date.today()
        job.featured = spec["featured"]
        job.status = "published"

    opportunity = Opportunity.query.filter_by(slug="rising-leaders-fellowship").first()
    if opportunity is None:
        opportunity = Opportunity(slug="rising-leaders-fellowship")
        db.session.add(opportunity)
    opportunity.title = "Rising Leaders Fellowship"
    opportunity.organization_name = "Foster Capital"
    opportunity.type = "Fellowship"
    opportunity.short_description = "A six-month fellowship for women in mid-career technology and finance roles."
    opportunity.description = [
        {"type": "paragraph", "text": "A six-month fellowship for women in mid-career technology and finance roles, pairing structured leadership training with executive mentorship."},
        {"type": "heading", "level": 2, "text": "What's offered"},
        {"type": "list", "style": "bullet", "items": ["Quarterly in-person sessions in London and New York", "One-on-one executive mentorship", "A peer cohort of 20 fellows worldwide"]},
    ]
    opportunity.eligibility = "Women with 5-12 years of professional experience."
    opportunity.eligibility_notes = "Open to applicants currently working in technology or financial services."
    opportunity.career_stage = "Mid-career"
    opportunity.location = "Hybrid — quarterly in-person sessions in London and New York"
    opportunity.deadline = date.today() + timedelta(days=60)
    opportunity.opening_date = date.today() - timedelta(days=10)
    opportunity.published_date = date.today()
    opportunity.funding_type = "partially_funded"
    opportunity.funding_min = 10000
    opportunity.funding_max = 10000
    opportunity.currency = "USD"
    opportunity.funding_value = "$10,000 grant + executive mentorship"
    opportunity.application_url = "https://fostercapital.example.com/rising-leaders"
    opportunity.application_instructions = "Submit a CV and a 500-word statement of purpose through the link below."
    opportunity.featured = True
    opportunity.status = "published"
    opportunity.topics = [topics["leadership"], topics["careers"]]
    db.session.flush()

    from app.models.geography import Country

    opportunity.countries_eligible = Country.query.filter(Country.code.in_(["US", "GB", "CA"])).all()

    # Five events spanning WSF's actual global audience (strong US base,
    # plus Kenya, the UK, Canada, and a virtual/global webinar) — not
    # Africa-only, per explicit editorial direction.
    event = _get_or_create_event("women-in-leadership-summit")
    event.title = "Women in Leadership Summit 2026"
    event.short_description = "Our flagship annual summit bringing together executives, founders, and policymakers shaping the next decade of business."
    event.description = [
        {"type": "paragraph", "text": "Our flagship annual summit bringing together executives, founders, and policymakers to accelerate women's leadership across every industry."},
        {"type": "heading", "level": 2, "text": "Who should attend"},
        {"type": "list", "style": "bullet", "items": ["Senior executives and founders", "Policymakers and institutional investors", "Rising leaders preparing for their next executive role"]},
        {"type": "heading", "level": 2, "text": "What you'll gain"},
        {"type": "list", "style": "bullet", "items": ["A playbook for leading through uncertainty, drawn from six keynote case studies", "Direct access to 40+ senior leaders across finance, tech, and policy", "A working peer group that continues past the summit itself"]},
    ]
    event.type = "Conference"
    event.format = "in-person"
    event.date = date.today() + timedelta(days=90)
    event.location = "New York, United States"
    event.city = "New York"
    event.country_code = "US"
    event.venue = "The Glasshouse"
    event.organizer_name = "Women Shaping Futures"
    event.registration_url = "https://wsf-events.example.com/register/leadership-summit"
    event.registration_required = True
    event.registration_deadline = date.today() + timedelta(days=80)
    event.ticket_price, event.currency = 425, "USD"
    event.capacity = 600
    event.agenda = [
        {"startTime": "08:30", "endTime": "09:15", "title": "Registration & Breakfast", "sessionType": "Networking"},
        {"startTime": "09:15", "endTime": "10:00", "title": "Opening Keynote: Leading Through Uncertainty", "description": "A candid look at the leadership decisions that don't make it into the case studies.", "sessionType": "Keynote", "speakerNames": ["Danielle Reyes"]},
        {"startTime": "10:15", "endTime": "11:15", "title": "Panel: Building Boards That Actually Challenge You", "sessionType": "Panel"},
        {"startTime": "12:30", "endTime": "13:30", "title": "Lunch & Structured Networking", "sessionType": "Networking"},
        {"startTime": "16:00", "endTime": "16:30", "title": "Closing Remarks", "sessionType": "Keynote"},
    ]
    event.status = "published"
    event.published_date = date.today()
    event.featured = True
    event.speakers = [EventSpeaker(person=danielle, position=0)]
    event.sponsors = [
        EventSponsor(organization=lumen, tier="Gold Sponsor", position=0),
        EventSponsor(organization=northstar, tier="Community Partner", position=1),
    ]

    event = _get_or_create_event("founder-growth-workshop")
    event.title = "Founder Growth Workshop"
    event.short_description = "A hands-on working session for founders ready to move from early traction to their next stage of growth."
    event.description = [
        {"type": "paragraph", "text": "A full-day, hands-on workshop for founders who've found early traction and are now wrestling with the harder problems: hiring a real leadership team, raising a priced round, and building systems that don't depend on the founder doing everything."},
        {"type": "heading", "level": 2, "text": "Who should attend"},
        {"type": "list", "style": "bullet", "items": ["Founders with a live product and early revenue or users", "Early-stage operators preparing to raise institutional capital"]},
    ]
    event.type = "Workshop"
    event.format = "in-person"
    event.date = date.today() + timedelta(days=45)
    event.location = "Nairobi, Kenya"
    event.city = "Nairobi"
    event.country_code = "KE"
    event.venue = "Nairobi Garage"
    event.organizer = kaziwave
    event.organizer_name = kaziwave.name
    event.registration_url = "https://wsf-events.example.com/register/founder-growth-workshop"
    event.registration_required = True
    event.ticket_price, event.currency = 3500, "KES"
    event.capacity = 80
    event.agenda = [
        {"startTime": "09:00", "endTime": "09:30", "title": "Arrival & Coffee", "sessionType": "Networking"},
        {"startTime": "09:30", "endTime": "11:00", "title": "Building a Leadership Team You Can Actually Delegate To", "sessionType": "Workshop", "speakerNames": ["Naliaka Wafula"]},
        {"startTime": "11:15", "endTime": "12:30", "title": "Fundraising Clinic: Priced Rounds & Term Sheets", "description": "Bring your own cap table — we'll work through it live.", "sessionType": "Workshop"},
        {"startTime": "13:30", "endTime": "15:00", "title": "Office Hours with Founders Who've Done It", "sessionType": "Mentoring"},
    ]
    event.status = "published"
    event.published_date = date.today()
    event.featured = False
    event.speakers = [EventSpeaker(person=naliaka, position=0)]
    event.sponsors = [EventSponsor(organization=kaziwave, tier="Presenting Sponsor", position=0)]

    event = _get_or_create_event("women-in-technology-webinar")
    event.title = "Women in Technology Webinar"
    event.short_description = "A free, global webinar on scaling engineering teams without losing the culture that made them work."
    event.description = [
        {"type": "paragraph", "text": "Open to anyone, anywhere: a practical session on what actually changes when an engineering org grows past 100 people, and how to keep it a place people want to stay."},
        {"type": "heading", "level": 2, "text": "What you'll learn"},
        {"type": "list", "style": "bullet", "items": ["How to redesign your engineering org chart before it redesigns itself", "What to stop doing as a technical leader once you're managing managers", "A live Q&A with time reserved for audience questions"]},
    ]
    event.type = "Webinar"
    event.format = "virtual"
    event.date = date.today() + timedelta(days=20)
    event.location = "Global / Virtual"
    event.city = None
    event.country_code = None
    event.virtual_link = "https://wsf-events.example.com/webinar/women-in-technology"
    event.virtual_link_public = True
    event.organizer_name = "Women Shaping Futures"
    event.registration_url = "https://wsf-events.example.com/register/women-in-technology-webinar"
    event.registration_required = True
    event.ticket_price = None
    event.currency = None
    event.capacity = 500
    event.agenda = [
        {"startTime": "12:00", "endTime": "12:05", "title": "Welcome", "sessionType": "Intro"},
        {"startTime": "12:05", "endTime": "12:35", "title": "Scaling Engineering Without Losing the Culture", "sessionType": "Talk", "speakerNames": ["Fatima Al-Sayed"]},
        {"startTime": "12:35", "endTime": "13:00", "title": "Live Q&A", "sessionType": "Q&A"},
    ]
    event.status = "published"
    event.published_date = date.today()
    event.featured = True
    event.speakers = [
        EventSpeaker(
            name="Fatima Al-Sayed",
            title="VP of Engineering",
            organization_name="Skyline Cloud",
            bio="Fatima leads a 120-person engineering organization and writes widely about scaling technical teams inclusively.",
            position=0,
        )
    ]
    event.sponsors = [EventSponsor(name="Skyline Cloud", url="https://skylinecloud.example.com", tier="Supporting Partner", position=0)]

    event = _get_or_create_event("career-advancement-masterclass")
    event.title = "Career Advancement Masterclass"
    event.short_description = "A half-day masterclass on making the case for your next promotion — in the room or on camera."
    event.description = [
        {"type": "paragraph", "text": "A half-day masterclass for professionals preparing to make the case for their next promotion, whether that conversation happens in a London office or over video."},
        {"type": "heading", "level": 2, "text": "Who should attend"},
        {"type": "list", "style": "bullet", "items": ["Mid-career professionals targeting their next senior role", "Anyone preparing for a promotion or performance review conversation"]},
    ]
    event.type = "Masterclass"
    event.format = "hybrid"
    event.date = date.today() + timedelta(days=60)
    event.location = "London, United Kingdom"
    event.city = "London"
    event.country_code = "GB"
    event.venue = "Harrow & Vance Studio"
    event.virtual_link = "https://wsf-events.example.com/webinar/career-advancement-masterclass"
    event.virtual_link_public = True
    event.organizer = harrow_vance
    event.organizer_name = harrow_vance.name
    event.registration_url = "https://wsf-events.example.com/register/career-advancement-masterclass"
    event.registration_required = True
    event.ticket_price, event.currency = 95, "GBP"
    event.capacity = 120
    event.agenda = [
        {"startTime": "13:00", "endTime": "13:45", "title": "Building Your Promotion Case", "sessionType": "Talk", "speakerNames": ["Priya Chandrasekaran"]},
        {"startTime": "13:45", "endTime": "14:30", "title": "Practice Rounds: Mock Promotion Conversations", "sessionType": "Workshop"},
        {"startTime": "14:45", "endTime": "15:15", "title": "Closing Q&A", "sessionType": "Q&A"},
    ]
    event.status = "published"
    event.published_date = date.today()
    event.featured = False
    event.speakers = [
        EventSpeaker(
            name="Priya Chandrasekaran",
            title="Head of Talent Development",
            organization_name="Harrow & Vance",
            bio="Priya has coached over 400 professionals through promotion and career-transition conversations.",
            position=0,
        )
    ]
    event.sponsors = [EventSponsor(organization=harrow_vance, tier="Presenting Sponsor", position=0)]

    event = _get_or_create_event("women-entrepreneurs-networking-event")
    event.title = "Women Entrepreneurs Networking Event"
    event.short_description = "An evening mixer for founders and operators building companies across Canada."
    event.description = [
        {"type": "paragraph", "text": "A relaxed evening mixer for founders, operators, and early-stage investors building companies across Canada — no panels, no pitches, just real conversation."},
        {"type": "heading", "level": 2, "text": "Who should attend"},
        {"type": "list", "style": "bullet", "items": ["Founders and early operators based in or building toward Canada", "Investors and advisors active in the Canadian founder community"]},
    ]
    event.type = "Networking Event"
    event.format = "in-person"
    event.date = date.today() + timedelta(days=35)
    event.location = "Toronto, Canada"
    event.city = "Toronto"
    event.country_code = "CA"
    event.venue = "Maple Ridge Capital HQ"
    event.organizer = maple_ridge
    event.organizer_name = maple_ridge.name
    event.registration_url = "https://wsf-events.example.com/register/entrepreneurs-networking-toronto"
    event.registration_required = True
    event.ticket_price = None
    event.currency = None
    event.capacity = 150
    event.agenda = [
        {"startTime": "18:00", "endTime": "18:15", "title": "Doors Open", "sessionType": "Networking"},
        {"startTime": "18:15", "endTime": "19:30", "title": "Open Networking", "sessionType": "Networking"},
        {"startTime": "19:30", "endTime": "19:45", "title": "Closing Remarks", "sessionType": "Intro"},
    ]
    event.status = "published"
    event.published_date = date.today()
    event.featured = False
    event.sponsors = [EventSponsor(organization=maple_ridge, tier="Presenting Sponsor", position=0)]

    def _get_or_create_resource(slug):
        resource = Resource.query.filter_by(slug=slug).first()
        if resource is None:
            resource = Resource(slug=slug)
            db.session.add(resource)
        return resource

    resource = _get_or_create_resource("career-planning-guide")
    resource.name = "The 5-Year Career Planning Guide"
    resource.subtitle = "A structured framework for mapping out where your career is headed."
    resource.short_description = "A worksheet-driven guide for mapping out your next five years, one deliberate decision at a time."
    resource.description = [
        {"type": "paragraph", "text": "Most career plans fail because they're really just wish lists. This guide walks you through a structured, worksheet-driven process for turning a vague sense of ambition into a concrete five-year plan — with checkpoints you'll actually return to."},
        {"type": "heading", "level": 2, "text": "What's included"},
        {"type": "list", "style": "bullet", "items": ["A five-year vision worksheet", "Quarterly milestone templates", "A skills-gap self-assessment", "A decision framework for evaluating new opportunities"]},
        {"type": "heading", "level": 2, "text": "Who it's for"},
        {"type": "paragraph", "text": "Mid-career professionals who feel busy but not necessarily on purpose, and want a plan they can revisit every quarter."},
    ]
    resource.type = "Guide"
    resource.topics = [topics["careers"], topics["personal-growth"]]
    resource.author = amara
    resource.price, resource.currency = 0, "USD"
    resource.access_type = "direct_download"
    resource.file_url = "https://cdn.wsf.example.com/resources/5-year-career-planning-guide.pdf"
    resource.file_format = "PDF"
    resource.page_count = 28
    resource.is_premium = False
    resource.featured = True
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=120)
    resource.seo = {
        "title": "The 5-Year Career Planning Guide | Women Shaping Futures",
        "description": "A free, worksheet-driven guide for mapping out your next five years of career growth.",
    }

    resource = _get_or_create_resource("career-reset-workbook")
    resource.name = "The Career Reset Workbook"
    resource.subtitle = "A guided workbook for professionals rebuilding their career on their own terms."
    resource.short_description = "Forty pages of prompts and exercises for anyone starting a deliberate career reset."
    resource.description = [
        {"type": "paragraph", "text": "Whether you're coming back from a career break, leaving a role that no longer fits, or simply ready for something different, this workbook gives you a structured way to reset — without pretending the process is linear."},
        {"type": "heading", "level": 2, "text": "What's included"},
        {"type": "list", "style": "bullet", "items": ["A values-and-strengths inventory", "A gap-analysis worksheet for resumes and career breaks", "A 90-day reset action plan", "Scripts for explaining a career gap in interviews"]},
    ]
    resource.type = "Workbook"
    resource.topics = [topics["careers"], topics["personal-growth"]]
    resource.author = amara
    resource.price, resource.currency = 0, "USD"
    resource.access_type = "email_gate"
    resource.file_url = "https://cdn.wsf.example.com/resources/career-reset-workbook.pdf"
    resource.file_format = "PDF"
    resource.page_count = 40
    resource.is_premium = False
    resource.featured = True
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=60)
    resource.seo = {
        "title": "The Career Reset Workbook | Women Shaping Futures",
        "description": "A free guided workbook for professionals rebuilding their career on their own terms.",
    }

    resource = _get_or_create_resource("salary-negotiation-checklist")
    resource.name = "Salary Negotiation Checklist"
    resource.subtitle = "A step-by-step checklist for walking into your next offer conversation prepared."
    resource.short_description = "A one-page checklist covering research, scripts, and the questions to ask before you say yes."
    resource.description = [
        {"type": "paragraph", "text": "Negotiating pay is a skill, not a personality trait — and most people never get real practice at it. This checklist breaks the conversation into the research, timing, and language that make it far less intimidating."},
        {"type": "heading", "level": 2, "text": "Key benefits"},
        {"type": "list", "style": "bullet", "items": ["Know exactly what to research before the call", "Have language ready for the most common pushback", "Avoid the three mistakes that quietly cost candidates the most money"]},
    ]
    resource.type = "Checklist"
    resource.topics = [topics["careers"], topics["money"]]
    resource.author = jordan
    resource.price, resource.currency = 0, "USD"
    resource.access_type = "email_gate"
    resource.file_url = "https://cdn.wsf.example.com/resources/salary-negotiation-checklist.pdf"
    resource.file_format = "PDF"
    resource.page_count = 2
    resource.is_premium = False
    resource.featured = True
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=45)
    resource.seo = {
        "title": "Salary Negotiation Checklist | Women Shaping Futures",
        "description": "A free step-by-step checklist for negotiating your next salary or offer with confidence.",
    }

    resource = _get_or_create_resource("linkedin-personal-brand-guide")
    resource.name = "LinkedIn Personal Brand Guide"
    resource.subtitle = "How to build a LinkedIn presence that actually reflects your expertise."
    resource.short_description = "A practical guide to positioning, profile structure, and a sustainable posting rhythm."
    resource.description = [
        {"type": "paragraph", "text": "Most LinkedIn advice is either generic growth-hacking or performative posting. This guide focuses on the fundamentals: a profile that reflects real expertise, a content approach you can sustain, and a way to build visibility that leads somewhere."},
        {"type": "heading", "level": 2, "text": "What's included"},
        {"type": "list", "style": "bullet", "items": ["A profile audit checklist", "Four proven post formats with examples", "A realistic weekly posting rhythm", "Guidance on engaging without feeling performative"]},
    ]
    resource.type = "Guide"
    resource.topics = [topics["careers"], topics["workplace"]]
    resource.author_name = "WSF Editorial Team"
    resource.price, resource.currency = 0, "USD"
    resource.access_type = "email_gate"
    resource.file_url = "https://cdn.wsf.example.com/resources/linkedin-personal-brand-guide.pdf"
    resource.file_format = "PDF"
    resource.page_count = 22
    resource.is_premium = False
    resource.featured = False
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=20)
    resource.seo = {
        "title": "LinkedIn Personal Brand Guide | Women Shaping Futures",
        "description": "A free guide to building a LinkedIn presence that reflects your real expertise.",
    }

    resource = _get_or_create_resource("women-founders-business-planning-toolkit")
    resource.name = "Women Founders Business Planning Toolkit"
    resource.subtitle = "A complete toolkit for turning a business idea into a fundable plan."
    resource.short_description = "Templates and worksheets covering market sizing, financial projections, and pitch structure."
    resource.description = [
        {"type": "paragraph", "text": "Built with input from founders who've raised seed and Series A rounds, this toolkit walks through the planning work investors actually expect to see — without the jargon."},
        {"type": "heading", "level": 2, "text": "What's included"},
        {"type": "list", "style": "bullet", "items": ["A one-page business model canvas template", "A 12-month financial projection spreadsheet", "A market-sizing worksheet", "A pitch deck outline with section-by-section guidance"]},
        {"type": "heading", "level": 2, "text": "Who it's for"},
        {"type": "paragraph", "text": "Early-stage founders preparing to raise their first round, or formalize a plan for a growing business."},
    ]
    resource.type = "Toolkit"
    resource.topics = [topics["entrepreneurship"], topics["business"], topics["money"]]
    resource.author = jordan
    resource.price, resource.currency = 4900, "USD"
    resource.access_type = "premium"
    resource.file_format = "ZIP"
    resource.page_count = 46
    resource.is_premium = True
    resource.featured = True
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=15)
    resource.seo = {
        "title": "Women Founders Business Planning Toolkit | Women Shaping Futures",
        "description": "A premium toolkit of templates for turning a business idea into a fundable plan.",
    }

    resource = _get_or_create_resource("leadership-reflection-workbook")
    resource.name = "Leadership Reflection Workbook"
    resource.subtitle = "A guided journal for leaders who want to grow deliberately, not just react."
    resource.short_description = "Structured reflection prompts for new and experienced leaders alike."
    resource.description = [
        {"type": "paragraph", "text": "Leadership growth rarely comes from more information — it comes from reflection on real decisions. This workbook gives new and experienced leaders a structured way to process what's working, what isn't, and what to try next."},
        {"type": "heading", "level": 2, "text": "What's included"},
        {"type": "list", "style": "bullet", "items": ["Twelve weeks of guided reflection prompts", "A feedback-gathering template", "A framework for turning feedback into a growth plan"]},
    ]
    resource.type = "Workbook"
    resource.topics = [topics["leadership"], topics["personal-growth"]]
    resource.author = amara
    resource.price, resource.currency = 0, "USD"
    resource.access_type = "direct_download"
    resource.file_url = "https://cdn.wsf.example.com/resources/leadership-reflection-workbook.pdf"
    resource.file_format = "PDF"
    resource.page_count = 34
    resource.is_premium = False
    resource.featured = False
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=90)
    resource.seo = {
        "title": "Leadership Reflection Workbook | Women Shaping Futures",
        "description": "A free guided workbook for leaders who want to grow deliberately.",
    }

    resource = _get_or_create_resource("job-interview-preparation-guide")
    resource.name = "Job Interview Preparation Guide"
    resource.subtitle = "How to prepare for behavioral, technical, and panel interviews with confidence."
    resource.short_description = "A complete interview-prep guide covering story-building, research, and follow-up."
    resource.description = [
        {"type": "paragraph", "text": "Strong candidates don't just answer questions well — they prepare deliberately. This guide covers how to build a bank of stories, research a company and interviewers, and handle the parts of interviewing most people dread."},
        {"type": "heading", "level": 2, "text": "What's included"},
        {"type": "list", "style": "bullet", "items": ["A STAR-method story-bank template", "A company and interviewer research checklist", "Answers to the ten most common tough questions", "A post-interview follow-up email template"]},
    ]
    resource.type = "Guide"
    resource.topics = [topics["careers"]]
    resource.author = jordan
    resource.price, resource.currency = 0, "USD"
    resource.access_type = "direct_download"
    resource.file_url = "https://cdn.wsf.example.com/resources/job-interview-preparation-guide.pdf"
    resource.file_format = "PDF"
    resource.page_count = 31
    resource.is_premium = False
    resource.featured = False
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=10)
    resource.seo = {
        "title": "Job Interview Preparation Guide | Women Shaping Futures",
        "description": "A free guide to preparing for behavioral, technical, and panel interviews.",
    }

    resource = _get_or_create_resource("30-day-career-growth-planner")
    resource.name = "30-Day Career Growth Planner"
    resource.subtitle = "A daily planner for building career-growth habits one month at a time."
    resource.short_description = "Daily and weekly prompts for building momentum toward your next career move."
    resource.description = [
        {"type": "paragraph", "text": "Career growth rarely happens in one big leap — it happens in the small, consistent actions most people never get around to. This planner breaks a month into daily and weekly prompts that build real momentum."},
        {"type": "heading", "level": 2, "text": "Who it's for"},
        {"type": "paragraph", "text": "Anyone who wants a career growth plan but keeps putting it off for lack of structure."},
    ]
    resource.type = "Planner"
    resource.topics = [topics["careers"], topics["personal-growth"]]
    resource.author_name = "WSF Editorial Team"
    resource.price, resource.currency = 0, "USD"
    resource.access_type = "direct_download"
    resource.file_url = "https://cdn.wsf.example.com/resources/30-day-career-growth-planner.pdf"
    resource.file_format = "PDF"
    resource.page_count = 36
    resource.is_premium = False
    resource.featured = False
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=5)
    resource.seo = {
        "title": "30-Day Career Growth Planner | Women Shaping Futures",
        "description": "A free 30-day planner for building career-growth habits one month at a time.",
    }

    resource = _get_or_create_resource("networking-conversation-starter-guide")
    resource.name = "Networking Conversation Starter Guide"
    resource.subtitle = "Real conversation starters for people who dread networking events."
    resource.short_description = "A practical guide to starting, sustaining, and following up on professional conversations."
    resource.description = [
        {"type": "paragraph", "text": "Most networking advice assumes you already enjoy small talk. This guide is for everyone else — with real openers, ways to exit a conversation gracefully, and a simple system for following up afterward."},
        {"type": "heading", "level": 2, "text": "What's included"},
        {"type": "list", "style": "bullet", "items": ["Thirty conversation starters for events, conferences, and virtual meetups", "A graceful-exit script bank", "A three-touch follow-up system"]},
    ]
    resource.type = "Checklist"
    resource.topics = [topics["careers"], topics["workplace"]]
    resource.author = amara
    resource.price, resource.currency = 0, "USD"
    resource.access_type = "direct_download"
    resource.file_url = "https://cdn.wsf.example.com/resources/networking-conversation-starter-guide.pdf"
    resource.file_format = "PDF"
    resource.page_count = 12
    resource.is_premium = False
    resource.featured = False
    resource.status = "published"
    resource.published_date = date.today() - timedelta(days=3)
    resource.seo = {
        "title": "Networking Conversation Starter Guide | Women Shaping Futures",
        "description": "A free guide with real conversation starters for professional networking.",
    }

    # Pages must exist before Navigation/Footer link to them below (About,
    # and Footer's Legal group) — moved ahead of that block so a fresh
    # database has real Page rows to link on the very first seed run,
    # rather than only after a second `flask seed-demo`.
    _seed_pages()

    # Navigation + Footer + social links — create-only (see
    # _seed_menu_if_empty/_seed_social_links_if_empty/_seed_setting_if_absent):
    # an admin's saved navigation/footer must never be overwritten by a reseed.
    about_page = Page.query.filter_by(key="about").first()
    contact_page = Page.query.filter_by(key="contact").first()
    privacy_page = Page.query.filter_by(key="privacy").first()
    terms_page = Page.query.filter_by(key="terms").first()
    cookies_page = Page.query.filter_by(key="cookies").first()
    editorial_policy_page = Page.query.filter_by(key="editorial-policy").first()

    def _page_child(label, page):
        return {"label": label, "item_type": "page", "page_id": page.id}

    def _topic_child(slug, label):
        return {"label": label, "item_type": "topic", "topic_id": topics[slug].id}

    _seed_menu_if_empty(
        "primary",
        None,
        [
            {"label": "Stories", "url": "/topics"},
            {
                "label": "Topics",
                "item_type": "group",
                "children": [
                    _topic_child("leadership", "Leadership"),
                    _topic_child("careers", "Career"),
                    _topic_child("business", "Business"),
                    _topic_child("entrepreneurship", "Entrepreneurship"),
                    _topic_child("workplace", "Workplace"),
                    _topic_child("women-impact", "Women & Impact"),
                ],
            },
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
            {"label": "Events", "url": "/events"},
            {"label": "Community", "url": "/community"},
            {"label": "Shop", "url": "/shop"},
        ],
    )
    # The header's dark utility bar reads this "secondary" menu — About
    # links to the real Pages-CMS row (item_type="page") rather than a
    # hard-coded "/about" string, so a future slug change there needs no
    # matching Navigation edit.
    secondary_items = [
        {"label": "WSF Weekly Newsletter", "url": "/newsletter"},
        {"label": "Partner With Us", "url": "/partnerships"},
    ]
    if about_page is not None:
        secondary_items.append({"label": "About", "item_type": "page", "page_id": about_page.id})
    _seed_menu_if_empty("secondary", None, secondary_items)
    _seed_menu_if_empty(
        "footer_explore",
        "Explore",
        [
            {"label": "Stories", "url": "/topics"},
            {"label": "Resources", "url": "/resources"},
            {"label": "Events", "url": "/events"},
        ],
    )
    _seed_menu_if_empty(
        "footer_opportunity",
        "Opportunities",
        [
            {"label": "Jobs", "url": "/jobs"},
            {"label": "Opportunities", "url": "/opportunities"},
            {"label": "Community", "url": "/community"},
            {"label": "Mentorship", "url": "/mentorship"},
        ],
    )
    # About links to the real Pages-CMS rows (item_type="page") rather than
    # hard-coded "/about"/"/contact" strings — a future slug change there
    # needs no matching Footer edit. Omitted entirely if a page hasn't been
    # seeded yet (shouldn't happen now _seed_pages() runs first, but this
    # keeps the seed from crashing if that ever changes).
    about_items = []
    if about_page is not None:
        about_items.append(_page_child("About", about_page))
    if contact_page is not None:
        about_items.append(_page_child("Contact", contact_page))
    about_items += [{"label": "Partner With Us", "url": "/partnerships"}, {"label": "Advertise", "url": "/advertise"}]
    _seed_menu_if_empty("footer_wsf", "About", about_items)

    # Legal links always resolve through the real Page row (see spec: "do
    # not hardcode raw routes for legal links; reuse Pages CMS") — never a
    # bare "/privacy" string, so a legal page can be safely relabeled
    # without ever touching its route.
    legal_items = [
        _page_child(label, page)
        for label, page in (
            ("Privacy", privacy_page),
            ("Terms", terms_page),
            ("Cookies", cookies_page),
            ("Editorial Policy", editorial_policy_page),
        )
        if page is not None
    ]
    _seed_menu_if_empty("footer_legal", "Legal", legal_items)

    _seed_social_links_if_empty(
        [
            {"platform": "linkedin", "url": "https://linkedin.com/company/womenshapingfutures", "handle": "Women Shaping Futures"},
            {"platform": "instagram", "url": "https://instagram.com/womenshapingfutures", "handle": "@womenshapingfutures"},
        ]
    )
    _seed_setting_if_absent(
        "footer",
        {
            "brandDescription": (
                "A global media, opportunity, and community platform amplifying women's stories and "
                "connecting women to jobs, mentors, and capital."
            ),
            "newsletterHeading": "WSF Weekly",
            "newsletterDescription": "Stories, jobs, and opportunities — every Thursday.",
            "newsletterVisible": True,
            "contactEmail": "hello@womenshapingfutures.org",
            "copyrightText": "Women Shaping Futures. All rights reserved.",
        },
    )

    # Homepage modules — create-only, like _seed_pages() below: if an
    # admin has already opened the Homepage Builder and saved a layout,
    # re-running this seed must never wipe their arrangement out from
    # under them. HomepageModule has no natural unique key to upsert
    # against (a re-run can't tell "the admin's hero" from "the seed's
    # hero"), so the only safe idempotent behavior is "skip entirely if
    # any row already exists" — exactly like every other create-only
    # seed block in this function.
    if HomepageModule.query.first() is None:
        db.session.add_all(
            [
                HomepageModule(
                    type="hero",
                    enabled=True,
                    sort_order=0,
                    selection_mode="manual",
                    config={
                        "leadArticleSlug": "how-women-are-redefining-leadership",
                        "secondaryArticleSlugs": ["building-a-saas-company-from-austin-not-silicon-valley"],
                    },
                ),
                HomepageModule(
                    type="featured_stories",
                    enabled=True,
                    sort_order=1,
                    heading="Featured Stories",
                    subheading="Editors' picks — the stories we don't want you to miss.",
                    selection_mode="manual",
                    config={
                        "articleSlugs": [
                            "the-negotiation-conversation-nobody-prepares-you-for",
                            "building-a-saas-company-from-austin-not-silicon-valley",
                        ]
                    },
                ),
                HomepageModule(
                    type="latest_stories",
                    enabled=True,
                    sort_order=2,
                    heading="Latest Stories",
                    subheading="Fresh reporting and essays, published this week.",
                    selection_mode="automatic",
                    config={"itemCount": 8},
                ),
                HomepageModule(
                    type="featured_woman",
                    enabled=True,
                    sort_order=3,
                    heading="Women Shaping Futures Spotlight",
                    subheading="A woman worth knowing, featured every month.",
                    selection_mode="manual",
                    config={"personSlug": "danielle-reyes"},
                ),
                HomepageModule(
                    type="series_feature",
                    enabled=True,
                    sort_order=4,
                    heading="Women Doing Incredible Things",
                    selection_mode="manual",
                    config={"seriesSlug": "women-doing-incredible-things", "itemCount": 3},
                ),
                HomepageModule(
                    type="topic_collection",
                    enabled=True,
                    sort_order=5,
                    heading="Leadership",
                    subheading="Editorial guidance for the way you work now.",
                    selection_mode="manual",
                    config={"topicSlug": "leadership", "itemCount": 3},
                ),
                HomepageModule(
                    type="opportunities",
                    enabled=True,
                    sort_order=6,
                    heading="Opportunities Worth Applying For",
                    subheading="Fellowships, scholarships, and grants closing soon.",
                    selection_mode="automatic",
                    config={"itemCount": 3},
                ),
                HomepageModule(
                    type="jobs",
                    enabled=True,
                    sort_order=7,
                    heading="Jobs We're Watching",
                    subheading="Featured roles from employers hiring now.",
                    selection_mode="automatic",
                    config={"itemCount": 4},
                ),
                HomepageModule(
                    type="events",
                    enabled=True,
                    sort_order=8,
                    heading="Upcoming Events",
                    subheading="Join us online or in person.",
                    selection_mode="automatic",
                    config={"itemCount": 3},
                ),
                HomepageModule(
                    type="resources",
                    enabled=True,
                    sort_order=9,
                    heading="Resources to Save",
                    subheading="Guides, templates, and worksheets from our library.",
                    selection_mode="automatic",
                    config={"itemCount": 3},
                ),
                HomepageModule(
                    type="newsletter",
                    enabled=True,
                    sort_order=10,
                    heading="WSF Weekly",
                    subheading="The stories, jobs, and opportunities worth your Thursday morning coffee.",
                ),
                HomepageModule(
                    type="partners",
                    enabled=True,
                    sort_order=11,
                    heading="In Partnership With",
                    selection_mode="manual",
                    # Only kaziwave/lumen-analytics are seeded as "published"
                    # organizations — harrow-vance/maple-ridge-capital/
                    # northstar-collective are deliberately seeded as
                    # "draft" (they're referenced as Article/Job employers,
                    # not as public partner logos), so listing them here
                    # would immediately surface a real "no longer
                    # published" warning in the builder.
                    config={"partnerSlugs": ["kaziwave", "lumen-analytics"]},
                ),
                HomepageModule(
                    type="sponsor_placement",
                    enabled=True,
                    sort_order=12,
                    heading="Our Sponsors",
                    config={"placementKey": "homepage_featured"},
                ),
            ]
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
