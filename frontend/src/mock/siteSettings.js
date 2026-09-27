// Mock-mode fixture for GET /public/settings — matches the real backend's
// {site, branding, contact, social, seo} shape (see api/site.js's
// mapSiteSettings and backend app/services/site_settings.py) so the same
// consumers (Logo, Footer copyright fallback, useSeo, JSON-LD) work
// identically whether VITE_USE_MOCK is true or false. Values mirror
// mock/navigation.js's socialLinks and the real WSF identity already used
// elsewhere in this app (index.html, mock/admin.js) rather than inventing
// new ones.
export const siteSettings = {
  site: {
    name: 'Women Shaping Futures',
    shortName: 'WSF',
    tagline: 'A global media, opportunity, and growth platform for women.',
    url: 'https://womenshapingfutures.org',
  },
  branding: { logo: null },
  contact: { email: 'hello@womenshapingfutures.org' },
  social: [
    { platform: 'linkedin', url: 'https://linkedin.com/company/womenshapingfutures', handle: 'Women Shaping Futures' },
    { platform: 'instagram', url: 'https://instagram.com/womenshapingfutures', handle: '@womenshapingfutures' },
  ],
  seo: {
    defaultTitle: 'Women Shaping Futures',
    defaultDescription: 'Women Shaping Futures — a global media, opportunity, and growth platform for women.',
    defaultOgImage: null,
  },
}
