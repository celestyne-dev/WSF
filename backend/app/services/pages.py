"""System Page bootstrap — the single source of truth for the six fixed-
purpose Pages (About/Contact/Privacy/Terms/Cookies/Editorial Policy) this
app already has real routes for (see app/models/page.py SYSTEM_PAGE_KEYS).

Used by both `flask seed-pages` (safe to run against a real production
database — same category as seed_roles_and_permissions()/seed_countries())
and `flask seed-demo` (so a fresh dev database has real Page rows before
Navigation/Footer seed their links to them). There is exactly one copy of
this content; neither caller may duplicate it.
"""
from app.extensions import db
from app.models.page import Page

# Unlike every update-on-reseed seed helper elsewhere in this app (which
# update existing rows on re-seed), pages are administrator-edited legal/
# informational content: a reseed must never clobber a page a real admin
# has already changed. So this only ever creates a system page's row once,
# on the run where it's first missing, and otherwise leaves it alone
# entirely (see seed_system_pages()). The wording below is migrated
# verbatim from what frontend/src/pages/AboutPage.jsx, ContactPage.jsx,
# and LegalPage.jsx used to hard-code, so the public site's content
# doesn't change the moment this phase ships.
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


def seed_system_pages():
    """Create-only: a system page that already exists (whether seeded
    before or since edited by an admin) is left completely untouched —
    title, subtitle, content, SEO, status, and effective date are never
    reassigned on an existing row. Only genuinely missing system-page rows
    (by `key`) are created, each published immediately since a system page
    with no row yet is exactly the 404 this bootstrap exists to fix. Safe
    to run repeatedly and safe on a real production database — same
    category as seed_roles_and_permissions()/seed_countries(), never
    seed-demo. Self-contained commit, like those, since `flask seed-pages`
    calls this directly.

    Returns the list of keys actually created (empty on a fully-seeded
    database).
    """
    created = []
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
        created.append(key)
    db.session.commit()
    return created
