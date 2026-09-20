# Women Shaping Futures

A global editorial, opportunity, and growth platform for women — built as a
premium digital magazine (stories, people, series) fused with a jobs/
opportunities marketplace, events, resources, mentorship, and a CMS that
drives nearly everything on the public site.

This repository currently contains the **Phase 1 frontend prototype**: a
fully working React + Vite application with realistic editorial content,
built against a mock data/API layer that is structured to be swapped for the
real Flask REST API with no UI rewrite. A backend skeleton (Flask app
factory, config, folder structure) is scaffolded under `backend/` ready for
implementation.

## 1. Project Structure

```
women-shaping-futures/
├── frontend/                 # React + Vite + Tailwind SPA (this phase's focus)
│   ├── src/
│   │   ├── api/               # Resource clients (axios-ready, mock-backed today)
│   │   ├── app/                # (reserved for app-level providers)
│   │   ├── assets/
│   │   ├── components/
│   │   │   ├── layout/         # Header, Footer, MobileNav, SearchOverlay, Logo
│   │   │   ├── ui/              # CloudinaryImage, SectionHeading, Tag, Pagination…
│   │   │   ├── cards/           # ArticleCard, PersonCard, JobCard, EventCard…
│   │   │   ├── article/         # ArticleContent block renderer
│   │   │   ├── home/            # One component per homepage CMS module type
│   │   │   └── cms/              # Admin-only UI primitives (StatCard, StatusBadge…)
│   │   ├── features/            # Redux slices, grouped by domain
│   │   ├── hooks/                # useSeo, etc.
│   │   ├── layouts/              # PublicLayout, AdminLayout
│   │   ├── mock/                  # Realistic seed content (see §8)
│   │   ├── pages/                  # Route-level components (+ pages/admin/*)
│   │   ├── routes/                  # AppRoutes.jsx — the full route table
│   │   ├── store/                    # Redux Toolkit store
│   │   └── utils/                     # media.js (image resolution), format.js
│   └── ...
├── backend/                   # Flask app skeleton (Phase 1 build target next)
│   ├── app/
│   │   ├── api/                 # Blueprints per resource (not yet implemented)
│   │   ├── auth/                 # JWT auth & RBAC (not yet implemented)
│   │   ├── models/                # SQLAlchemy models (not yet implemented)
│   │   ├── schemas/                # Marshmallow schemas
│   │   ├── services/                # Slug/redirect/Cloudinary/payment logic
│   │   ├── utils/                     # RESERVED_SLUGS, helpers
│   │   ├── extensions.py
│   │   └── __init__.py                # Application factory
│   ├── migrations/
│   ├── tests/
│   ├── config.py
│   ├── requirements.txt
│   └── run.py
├── docs/
├── README.md
└── .gitignore
```

## 2. Installation & Running Locally

```bash
cd frontend
npm install
cp .env.example .env      # defaults already point at the mock layer
npm run dev                # http://localhost:5173
```

Build for production:

```bash
npm run build
npm run preview
```

The backend skeleton isn't runnable yet (no models/routes implemented), but
its scaffold is in place:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# flask db upgrade / flask run — once models & migrations are added
```

## 3. Dependencies (frontend)

- **React 19 + Vite** — standalone SPA, no Next.js, consumes a Flask REST API
- **React Router v6** — client-side routing, including the flat article URL
- **Redux Toolkit + React-Redux** — global state (auth, site nav/homepage, ui, newsletter)
- **Tailwind CSS v3** + `@tailwindcss/typography` — utility-first styling, editorial `prose` for article bodies
- **Axios** — HTTP client, pre-wired in `src/api/client.js` for when the mock layer is switched off
- **React Toastify** — non-blocking form/action feedback
- **Recharts** — admin dashboard and analytics charts
- **Lucide React** — iconography (brand/social icons use `SocialIcon.jsx`; see §9)

`react-datepicker` is listed in the spec for admin scheduling UI; it isn't
wired into a component yet in this pass (the article editor uses a status
dropdown rather than a full scheduling calendar) but is a direct drop-in for
`AdminArticleEditor`'s "Scheduled" status.

## 4. Architectural Decisions

**Mock API layer, not mock components.** Every piece of content flows
through `src/api/*.js` — `fetchArticles()`, `fetchJobBySlug()`,
`globalSearch()`, etc. Each function checks a `USE_MOCK` flag
(`VITE_USE_MOCK`, default `true`) and either reads from `src/mock/*.js` or
calls the real endpoint via the shared `axios` instance in `api/client.js`.
**No component imports mock data directly through the API layer's public
functions** — flipping `VITE_USE_MOCK=false` and pointing `VITE_API_URL` at
a running Flask API is the entire migration path.

**Flat article URLs, namespaced API.** Articles render at
`/{slug}` (e.g. `/how-women-are-redefining-leadership`), never
`/articles/{slug}`. This is enforced in the router (`routes/AppRoutes.jsx`):
static routes (`/people`, `/jobs`, …) are declared as siblings of the
catch-all `/:slug` route, and React Router's ranking algorithm always
prefers a static match over a dynamic one at the same depth — so a request
for `/jobs` can never be swallowed by the article route. A legacy
`/articles/:slug` route 301-redirects (via `<Navigate replace>`) to the flat
URL. Reserved slugs (`admin`, `search`, `people`, …) are centralized in
`src/mock/index.js` (`RESERVED_SLUGS`) and enforced in both
`api/articles.js` (`fetchArticleBySlug` refuses reserved slugs) and the CMS
article editor (`AdminArticleEditor` blocks save with an inline error). The
same list is mirrored in `backend/app/utils/__init__.py` for when backend
validation is implemented.

**CMS-driven homepage, not hard-coded sections.** The homepage
(`pages/HomePage.jsx`) renders an ordered list of modules fetched from
`fetchHomepageModules()` (backed by `mock/homepageModules.js`, modeling
`GET /api/v1/public/homepage`). Each module has a `type`
(`hero`, `latest_stories`, `featured_woman`, `series_feature`,
`opportunities`, `jobs`, `topic_collection`, `resources`, `events`,
`newsletter`, `partners`), and a lookup table in `HomePage.jsx` maps each
type to its renderer component in `components/home/`. The admin
`Homepage Builder` screen (`pages/admin/AdminHomepageBuilder.jsx`) edits the
same shape — enable/disable, reorder, edit heading/subheading — with no
code change required to rearrange the page.

**CMS-driven navigation.** `mock/navigation.js` models
`GET /api/v1/public/navigation`: primary nav (with dropdown children),
secondary nav, and footer link groups. `Header.jsx` and `Footer.jsx` render
whatever comes back — nothing is hard-coded in the layout components.

**Images without a real Cloudinary account.** This sandbox has no outbound
network access to an image CDN, so `src/utils/media.js` implements
`resolveImage()`/`resolveSrcSet()` with two branches: if
`VITE_CLOUDINARY_CLOUD_NAME` is set, it builds a real
`f_auto,q_auto,c_fill,g_auto,w_{width}` Cloudinary delivery URL (WebP where
supported, responsive, focal-point cropping); otherwise it renders a
deterministic, on-brand abstract placeholder (an inline SVG gradient, seeded
by the same `publicId` so a given person/article always gets the same
placeholder). Every image-consuming component (`CloudinaryImage.jsx`) is
already written against the *production* API — alt text, caption, credit,
width/height (to prevent layout shift), and `loading="lazy"` are all wired
up now. Pointing `VITE_CLOUDINARY_CLOUD_NAME` at a real Cloudinary account
is the entire migration path; no component changes.

**SEO without react-helmet.** `hooks/useSeo.js` imperatively sets
`document.title`, meta description/robots, canonical `<link>`, OpenGraph,
and Twitter card tags per page — kept dependency-free since Helmet wasn't in
the specified stack. Every page/detail route calls it with real, unique
metadata (see `ArticlePage`, which uses the article's own `seo` fields).

**Editorial content blocks, not raw HTML.** Article bodies
(`mock/articles.js` → `content: [...]`) are an ordered array of typed
blocks (`heading`, `paragraph`, `image`, `pullquote`, `blockquote`, `list`,
`highlight`, `newsletterCta`, `relatedBlock`, `sponsorBlock`, `ad`,
`button`, `table`, `faq`), rendered by
`components/article/ArticleContent.jsx`. This mirrors what a structured
rich-text CMS editor would persist, and keeps sponsored content,
advertising slots, and newsletter CTAs as first-class, clearly-labeled
blocks rather than embedded HTML.

**Auth & role-gating (prototype-depth).** `features/auth/authSlice.js`
implements a JWT-shaped login flow (`api/auth.js` mimics
`Flask-JWT-Extended`'s response shape) against the `adminUsers` mock list.
`layouts/AdminLayout.jsx` redirects to `/login` if there's no token. Log in
as `wanjiru@womenshapingfutures.org` with any 4+ character password to
reach the CMS (see `LoginPage.jsx` for the full demo-credential note).

## 5. Routes

Public (all under `PublicLayout` — header, footer, mobile nav, search overlay):

| Path | Page |
|---|---|
| `/` | Homepage (CMS-modular) |
| `/{slug}` | **Flat** article page (e.g. `/how-women-are-redefining-leadership`) |
| `/articles/{slug}` | 301-redirects to `/{slug}` |
| `/topics`, `/topics/{slug}` | Stories index / topic landing |
| `/people`, `/people/{slug}` | People directory / profile |
| `/authors`, `/authors/{slug}` | Authors index / profile |
| `/series`, `/series/{slug}` | Series index / detail |
| `/jobs`, `/jobs/{slug}` | Jobs listing / detail |
| `/opportunities`, `/opportunities/{slug}` | Opportunities listing / detail |
| `/events`, `/events/{slug}` | Events listing / detail |
| `/resources`, `/resources/{slug}` | Resource library / detail |
| `/organizations`, `/organizations/{slug}` | Organizations index / detail |
| `/newsletter` | WSF Weekly signup + archive |
| `/partnerships`, `/advertise` | Commercial pages |
| `/about`, `/contact` | Trust pages |
| `/search` | Global search (`?q=&type=`) |
| `/login` | Auth (redirects into `/admin` for staff roles) |
| `/submit`, `/nominate` | Story submission / nomination forms |
| `/mentorship`, `/community`, `/learning`, `/shop` | Phase 2/3 landing pages |
| `/privacy`, `/terms`, `/cookies`, `/editorial-policy` | CMS-style legal pages |

Admin (`AdminLayout`, auth-gated):

`/admin`, `/admin/articles`, `/admin/articles/new`, `/admin/articles/:id`,
`/admin/homepage`, `/admin/people`, `/admin/jobs`, `/admin/opportunities`,
`/admin/events`, `/admin/resources`, `/admin/newsletter`,
`/admin/submissions`, `/admin/nominations`, `/admin/partnerships`,
`/admin/advertising`, `/admin/media`, `/admin/seo`, `/admin/analytics`,
`/admin/users`, `/admin/settings`.

## 6. CMS Structure

`AdminLayout.jsx` renders a dark-sidebar shell (deliberately distinct from
the public site's ivory editorial look) grouped into: **Overview**
(Dashboard), **Content** (Articles, Homepage, People), **Opportunity**
(Jobs, Opportunities, Events, Resources), **Community** (Newsletter,
Submissions, Nominations), **Revenue** (Partnerships, Advertising), and
**System** (Media Library, SEO, Analytics, Users & Roles, Settings).

- `AdminDashboard` — stat cards + Recharts (page views, pending review queue, top articles)
- `AdminArticles` / `AdminArticleEditor` — full list + editor with slug
  auto-generation, reserved-slug/uniqueness validation, topic tagging,
  sponsor flag, and an editorial status dropdown
  (`draft → in_review → changes_requested → approved → scheduled → published → archived`)
- `AdminHomepageBuilder` — reorder (↑/↓), enable/disable, and edit heading/subheading for every homepage module
- `AdminGenericList` — a config-driven table reused for People, Jobs,
  Opportunities, Events, Resources, Submissions, Nominations,
  Partnerships, and Advertising (plus bespoke Newsletter/Media/SEO views)
- `AdminUsers` — the 11-role matrix from the spec, with descriptions
- `AdminSettings` — tabbed site identity / navigation / footer / newsletter / integrations
- `AdminAnalytics` — traffic trend, source breakdown, subscriber growth

## 7. Component Structure

See §1's tree. The short version: **layout** (chrome), **ui** (dumb
primitives), **cards** (one card per content type, each with its own
visual treatment so the homepage doesn't read as a wall of identical
cards), **article** (rich content block renderer), **home** (one component
per CMS module type), **cms** (admin-only chrome). Pages compose these; no
page hand-rolls markup that a shared component already owns.

## 8. Mock Data Architecture

`src/mock/*.js` holds realistic, hand-written editorial content — no Lorem
Ipsum — modeling every field called for in the spec (articles have
authors/co-authors, topics, series, sponsor disclosure, SEO fields, and
status; people have career timelines, achievements, awards; jobs carry
salary bands and deadlines; etc.). `src/mock/index.js` re-exports
everything plus the shared `RESERVED_SLUGS` list. `src/api/*.js` is the only
layer allowed to import from `mock/` for reads — components call the API
functions, not the mock files, directly (a few listing pages call a mock
getter directly for synchronous filtering; the point of the boundary is
that the *shape* returned matches what the real API will return, and
swapping the implementation is confined to `api/`).

All dates in the mock data are anchored relative to "today" so deadlines,
"upcoming" events, and "recent" newsletter issues actually read as
current — check `frontend/.env` isn't overriding `VITE_USE_MOCK` if content
ever looks stale.

## 9. Known Prototype Limitations

- **Placeholder imagery.** This sandbox can't reach an image CDN, so all
  photography is a deterministic abstract SVG placeholder in the brand
  palette (see `utils/media.js`). Wiring a real Cloudinary account is a
  one-line env var change — no component changes needed.
- **Social brand icons.** The installed `lucide-react` version dropped
  brand/logo glyphs; `components/ui/SocialIcon.jsx` provides minimal inline
  SVGs for Facebook/X/LinkedIn/Instagram/YouTube instead.
- **Admin CRUD is prototype-depth.** Saving in `AdminArticleEditor` or
  `AdminHomepageBuilder` validates and shows a success toast but doesn't
  persist (there's no backend yet). The validation logic (slug
  uniqueness/reserved-slug checks) is real and will carry over unchanged.
- **Backend is a skeleton**, not an implementation — see `backend/README`-equivalent notes in this file's §1 and the module docstrings under `backend/app/`.

## 10. Screens to Review First

1. **Homepage** (`/`) — the CMS-modular layout end to end
2. **Article** (`/how-women-are-redefining-leadership`) — full editorial treatment
3. **People directory + profile** (`/people`, `/people/naliaka-wafula`)
4. **Jobs** (`/jobs`, `/jobs/senior-marketing-manager-kaziwave`)
5. **Opportunities** (`/opportunities`)
6. **Search** (`/search?q=leadership`)
7. **Login** (`/login`) → **Admin Dashboard** (`/admin`)
8. **Admin Article Editor** (`/admin/articles/new`) — reserved-slug validation
9. **Admin Homepage Builder** (`/admin/homepage`) — reorder/enable modules
10. Resize any page to ~390px to check the mobile experience (hamburger nav, filters, forms)
