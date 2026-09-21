// Slugs that collide with a real top-level route (/admin, /search, /jobs,
// ...) and can therefore never be used as an article's flat public slug —
// a genuinely static application constant, not mock content. Shared by the
// router, api/articles.js (fetchArticleBySlug refuses these outright), and
// the CMS article editor (blocks save with an inline error).
export const RESERVED_SLUGS = [
  'admin', 'api', 'login', 'logout', 'register', 'search', 'people', 'authors',
  'topics', 'categories', 'series', 'resources', 'events', 'opportunities',
  'jobs', 'organizations', 'newsletter', 'mentorship', 'community', 'learning',
  'shop', 'partnerships', 'advertise', 'about', 'contact', 'privacy', 'terms',
  'cookies', 'submit', 'nominate', 'account', 'dashboard', 'articles', 'editorial-policy',
]
