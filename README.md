# Women Shaping Futures

A global editorial, opportunity, and growth platform for women — built as a
premium digital magazine (stories, people, series) fused with a jobs/
opportunities marketplace, events, resources, mentorship, and a CMS that
drives nearly everything on the public site.

This repository contains both halves of the product: a React + Vite
frontend and a Flask + PostgreSQL backend. The frontend can run two ways —
against `src/mock/*.js` (no backend needed, the default) or against the
real backend (`VITE_USE_MOCK=false`, see §2) — through the exact same
`src/api/*.js` functions and with no UI rewrite between the two.

## 1. Project Structure

```
women-shaping-futures/
├── frontend/                 # React + Vite + Tailwind SPA (this phase's focus)
│   ├── src/
│   │   ├── api/               # Resource clients — real Flask API when VITE_USE_MOCK=false, mock/ otherwise
│   │   ├── app/                # (reserved for app-level providers)
│   │   ├── assets/
│   │   ├── components/
│   │   │   ├── layout/         # Header, Footer, MobileNav, SearchOverlay, Logo
│   │   │   ├── ui/              # MediaImage, SectionHeading, Tag, Pagination…
│   │   │   ├── cards/           # ArticleCard, PersonCard, JobCard, EventCard…
│   │   │   ├── article/         # ArticleContent block renderer
│   │   │   ├── home/            # One component per homepage CMS module type
│   │   │   └── cms/              # Admin-only UI primitives (StatCard, StatusBadge…)
│   │   ├── features/            # Redux slices, grouped by domain
│   │   ├── hooks/                # useSeo, etc.
│   │   ├── layouts/              # PublicLayout, AdminLayout
│   │   ├── mock/                  # Realistic seed content (see §8), incl. geography.js
│   │   ├── pages/                  # Route-level components (+ pages/admin/*)
│   │   ├── routes/                  # AppRoutes.jsx — the full route table
│   │   ├── store/                    # Redux Toolkit store
│   │   └── utils/                     # media.js, format.js, analytics.js (LinkedIn/UTM tracking)
│   └── ...
├── backend/                   # Flask + SQLAlchemy + PostgreSQL API — fully implemented
│   ├── app/
│   │   ├── api/v1/               # Blueprints per resource (articles, people, jobs, admin, analytics, …)
│   │   ├── auth/                  # JWT auth & RBAC decorators
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── schemas/                 # Marshmallow schemas (camelCase data_keys in, snake_case out)
│   │   ├── services/                 # Slug/redirect/media (Pillow)/CMS/RBAC/demo-seed logic
│   │   ├── utils/                     # RESERVED_SLUGS, filtering, pagination, response envelopes
│   │   ├── extensions.py
│   │   └── __init__.py                # Application factory
│   ├── migrations/
│   ├── tests/                          # pytest — run with `venv/bin/pytest`
│   ├── config.py
│   ├── requirements.txt
│   └── run.py
├── docs/
├── README.md
└── .gitignore
```

## 2. Installation & Running Locally

### Mock mode (default — no backend required)

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

### Real API mode (frontend + Flask/PostgreSQL backend)

The backend is fully implemented — Flask + SQLAlchemy + PostgreSQL, with
JWT auth/RBAC, the full content API, CMS/admin endpoints, and search. To
run the whole site against it instead of the mock layer:

```bash
# 1. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # set DATABASE_URL, JWT_SECRET_KEY, etc.
flask db upgrade                   # run migrations
flask seed-roles                   # seed RBAC roles/permissions (once)
flask seed-geography               # seed the Country reference table (once)
flask seed-demo                    # optional: seed demo content for local testing
flask create-superadmin --email you@example.com --password changeme
flask run                          # http://localhost:5000

# 2. Frontend — point it at the real API instead of the mock layer
cd frontend
cat > .env.local <<'EOF'
VITE_API_URL=http://localhost:5000/api/v1
VITE_USE_MOCK=false
EOF
npm run dev                       # restart if it was already running —
                                   # Vite only reads env files at startup
```

`.env.local` is gitignored (`*.local`), so these aren't committed and don't
need to be secrets — they're just local endpoint/mode configuration. With
`VITE_USE_MOCK=false`, every `src/api/*.js` function calls the real Flask
API instead of reading `src/mock/*.js` (see §4) — the whole public site,
search, and the CMS/admin screens run on live data. Log in at `/login` with
the `flask create-superadmin` credentials above to reach `/admin`.

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

**Media is self-hosted on the Hostinger VPS — no third-party media CDN.**
Uploaded images are never sent to an external service. The Flask backend
receives an upload (`POST /api/v1/media/upload`, multipart), validates its
MIME type/extension/size (`backend/app/services/media.py`), generates a
collision-safe UUID-based filename, and uses Pillow to strip metadata,
correct orientation, and generate responsive WebP variants
(`thumbnail`/`card`/`medium`/`large`/`hero`) alongside the preserved
original — written under `MEDIA_ROOT` (`originals/`, `thumbnail/`, `card/`,
`medium/`, `large/`, `hero/` subdirectories), outside the app's source tree
(production: `/var/www/womenshapingfutures/media/`; local dev:
`backend/instance/media/`). A `Media` row plus one `MediaVariant` row per
generated size (`backend/app/models/media.py`) records the metadata —
`uuid`, `stored_filename`, `file_path`, `public_url`, dimensions, file
size, `alt_text`, `caption`, `credit`, `copyright_source`, `uploaded_by` —
**not** the binary file; `MediaSchema` serializes `variants` as
`{thumbnail: {url, width, height}, card: {...}, ...}`. The **original is
preserved as-uploaded** (never converted) for archival/reprocessing — the
public site loads the WebP variants, never `/media/originals/*`, wherever
a variant exists (see `frontend/src/components/ui/MediaImage.jsx` and
`frontend/src/utils/media.js:resolveMediaImage`).

In production, Nginx serves every one of these directories directly from
disk at a clean URL under the WSF domain — Flask is only ever in the
upload → validate → process → metadata → permissions path, never in the
hot path of serving an image to a visitor:

```nginx
location /media/ {
    alias /var/www/womenshapingfutures/media/;
    # Covers /media/originals/, /media/thumbnail/, /media/card/,
    # /media/medium/, /media/large/, /media/hero/ — MediaService writes
    # each generated file under this same root, so no per-variant
    # location block is needed.
    add_header Cache-Control "public, max-age=31536000, immutable";
    access_log off;
}
```

Local development has no Nginx in front of Flask, so
`backend/app/__init__.py` registers an equivalent `GET /media/<path:filename>`
route (guarded by `app.debug`, so it's a no-op in production) that serves
straight from `MEDIA_ROOT` — the same URL shape either way, so
`frontend/src/utils/media.js` never needs to know which one is running.

`src/utils/media.js`'s `resolveImage()`/`resolveSrcSet()` (mock-mode
placeholder path) and `resolveMediaImage()` (real-media path, used by
`<MediaImage media={...} variant="card">`) both resolve a backend
`public_url` — root-relative in dev (different origin than the Vite dev
server) or already-absolute in production — against the API's own origin,
so images load correctly in both setups without an environment-specific
component change. `VITE_MEDIA_BASE_URL` remains available as a mock-mode
override for previewing what a real `{base}/{mediaPath}-{variant}.webp`
CDN-style URL scheme would look like; it's not used once real media data
(with real `variants`) is present.

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

**Global geography, not a hard-coded country list.** `mock/geography.js` is
the single source of truth for countries and regions — a representative
ISO 3166-1 alpha-2 set spanning North America, Latin America & Caribbean,
Europe, Africa, Asia, the Middle East, and Oceania, plus `GLOBAL`/`REMOTE`
pseudo-locations for content that isn't tied to one country (a fully
remote job, a worldwide grant). Every content type that carries a location
— people, authors, organizations, jobs, events, story submissions,
nominations — stores a `countryCode` (opportunities store an array,
`countriesEligible`, for multi-country eligibility) rather than a free-text
country name, and resolves it to a display name via `getCountryName()`
only at render time. Filters (`countryFilterOptions()`,
`regionFilterOptions()`, `matchesCountry()`, `matchesRegion()`, all in
`geography.js`) build their option lists from whatever codes actually
appear in the dataset, so adding a new country anywhere in the app is a
one-line addition to `COUNTRIES` — no page or filter needs to change.
Money follows the same non-hard-coded principle: every priced entity
stores `{ amount, currency }` (`USD`, `KES`, `GBP`, `CAD`, `ZAR`, `NGN` all
appear in the mock data) and `utils/format.js`'s `formatSalary`/
`formatCurrency` render whatever currency the record carries — nothing
defaults to a single currency.

**LinkedIn-first acquisition, tracked without an API dependency.**
Women Shaping Futures' established audience lives on LinkedIn, so the
funnel the site is built around is LinkedIn → article → more content →
newsletter → resource/event/product/community. `utils/analytics.js`
captures UTM parameters and `document.referrer` once per session
(`captureAcquisitionContext()`, wired into `PublicLayout` on every route
change) and classifies the visit's source (`linkedin`, another referrer
domain, or `direct`) without ever touching LinkedIn's API — the site's own
funnel works whether or not that integration exists. UTM params are read
from the query string only; they're never written into
`<link rel="canonical">`, so a `?utm_source=linkedin` link and its bare
equivalent always canonicalize to the same URL (`useSeo.js` sets canonical
from the article's own `seo.canonical` field, not `window.location`).
Every conversion point — `NewsletterForm`, `SubmitStoryPage`,
`NominatePage`, `PartnershipsPage`'s inquiry form, and the download/
registration/apply clicks on `ResourceDetailPage`/`EventDetailPage`/
`JobDetailPage`/`OpportunityDetailPage` — calls `trackEvent()` or attaches
`withAcquisitionMetadata()` to its payload, so a real analytics backend can
report "newsletter signups from LinkedIn" or "job applies from LinkedIn"
without any frontend changes. `ArticlePage`'s share bar leads with
LinkedIn (visually emphasized, first in the row) rather than treating all
networks equally. Audience numbers used on the Partnerships/media-kit page
(`mock/admin.js`'s `audienceStats`: LinkedIn followers, average reach,
engagement rate, audience geography/industries/seniority, newsletter
subscribers, website audience) are never hard-coded into a component —
`PartnershipsPage`, `AboutPage`, and `CommunityPage` all read from
`audienceStats`, and `AdminSettings`'s **Media Kit** tab edits the same
object, demonstrating the CMS control the real backend will expose at
`GET/PUT /api/v1/partnerships/audience`.

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
everything plus the shared `RESERVED_SLUGS` list. `src/api/*.js` is the
layer that owns reading from `mock/` — every page and component fetches
content through an `api/*.js` function (`fetchArticles()`,
`fetchPersonBySlug()`, …), never by importing a mock array directly, so
`VITE_USE_MOCK=false` genuinely switches the entire site (public pages,
homepage modules, admin/CMS) onto the real Flask API with no leftover mock
wiring. The remaining direct `mock/` imports outside `api/*.js` are narrow,
intentional exceptions:

- `RESERVED_SLUGS` (`mock/index.js`) — a static route-name constant, not
  content; imported directly by `ArticlePage`, `AdminArticleEditor`, and
  `api/articles.js` alike.
- `getCountryName()`/`getCountryNames()` (`mock/geography.js`) — a pure
  ISO-code-to-display-name lookup over a fixed reference list, not a CMS
  record; used by `PersonCard`, `OrganizationCard`, and a couple of detail
  pages purely for display text.
- `CountrySelect` falls back to the static `COUNTRIES` list only before
  the real list has loaded from Redux (or in mock mode) — never overrides
  live data.
- `ArticleCard` and `ArticleContent`'s related-reading block keep a mock
  slug-lookup fallback that only fires when the caller hasn't already
  supplied a resolved object — this covers mock mode and any legacy raw
  mock-array callers, and is inert once every caller passes real data.

Nothing else — no page, listing screen, homepage module, or admin screen —
reads `mock/` directly; swapping `VITE_USE_MOCK` is the entire migration
path (see §2).

All dates in the mock data are anchored relative to "today" so deadlines,
"upcoming" events, and "recent" newsletter issues actually read as
current — check `frontend/.env` isn't overriding `VITE_USE_MOCK` if content
ever looks stale.

**Editorial scope.** `mock/topics.js` defines the taxonomy the site
covers: Leadership, Career, Business, Entrepreneurship, Workplace,
Personal Growth, Money (general career economics only — salary
negotiation, understanding compensation, pricing — never individualized
investment, tax, or regulated financial advice), Opportunities, Women &
Impact, Women Founders, Women in STEM, and Technology. There is
deliberately no Health/Wellness/medical topic and no legal-advice or
specialist-financial-advice vertical — Women Shaping Futures covers areas
where it can offer strong editorial and educational value without acting
as a licensed professional service. The CMS can add, rename, or retire
topics without a frontend change (`getTopicBySlug()` is the only lookup
components use).

**Geographic balance.** The mock content deliberately spans North America
(with particularly strong US representation — several flagship articles,
jobs, and events are US-based, reflecting the platform's actual audience
concentration), Africa, Europe, Asia, Latin America, the Middle East, and
Oceania, rather than defaulting to any one region. See `mock/people.js`,
`mock/organizations.js`, `mock/jobs.js`, `mock/opportunities.js`, and
`mock/events.js` for the full spread.

## 9. Known Prototype Limitations

- **Placeholder imagery.** This sandbox has no media backend to upload to
  or fetch from, so all photography is a deterministic abstract SVG
  placeholder in the brand palette (see `utils/media.js`). Setting
  `VITE_MEDIA_BASE_URL` once the Flask media service is deployed on the
  Hostinger VPS is a one-line env var change — no component changes
  needed.
- **Social brand icons.** The installed `lucide-react` version dropped
  brand/logo glyphs; `components/ui/SocialIcon.jsx` provides minimal inline
  SVGs for Facebook/X/LinkedIn/Instagram/YouTube instead.
- **Admin CRUD persists for real in real API mode.** With `VITE_USE_MOCK=false`
  and the Flask backend running, saving in `AdminArticleEditor` or
  `AdminHomepageBuilder` writes through to PostgreSQL via the real
  `POST`/`PUT` endpoints — slug uniqueness and reserved-slug checks are
  enforced server-side too. In mock mode (`VITE_USE_MOCK=true`, the
  default), the same screens validate and show a success toast without a
  backend to persist to.
- **Ad campaign tracking has no backend yet.** Nothing in the backend phases
  built ad serving/impression tracking, so `Admin → Advertising` shows real
  data in mock mode only; real mode shows an honest "not yet available"
  empty state rather than fabricated numbers.

## 10. Screens to Review First

1. **Homepage** (`/`) — the CMS-modular layout end to end, now visibly global (US, UK, Kenya, Brazil, South Africa in the hero/spotlight/series alone)
2. **Article** (`/building-a-saas-company-from-austin-not-silicon-valley`) — a US-anchored story with the LinkedIn-first share bar
3. **People directory + profile** (`/people` with the Region filter, `/people/danielle-reyes`)
4. **Jobs** (`/jobs` with Region + Country filters, `/jobs/senior-product-manager-lumen-analytics` — a USD-denominated US role)
5. **Opportunities** (`/opportunities/global-founders-grant` — a `GLOBAL`-eligibility opportunity)
6. **Topics** (`/topics`) — the revised taxonomy (no Health/Wellness; Money scoped to career economics)
7. **Partnerships** (`/partnerships`) — CMS-driven audience stats (LinkedIn followers, geography/industry/seniority breakdowns)
8. **Search** (`/search?q=leadership`)
9. **Login** (`/login`) → **Admin Dashboard** (`/admin`) → **Settings → Media Kit** tab (editable audience stats)
10. **Admin Article Editor** (`/admin/articles/new`) — reserved-slug validation
11. **Admin Homepage Builder** (`/admin/homepage`) — reorder/enable modules
12. Resize any page to ~390px to check the mobile experience (hamburger nav, filters, forms)
