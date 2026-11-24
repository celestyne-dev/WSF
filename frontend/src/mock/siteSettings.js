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
  newsletterPopup: { enabled: true, delaySeconds: 15, scrollPercent: 45, dismissDays: 14, successDays: 365, title: 'WSF Weekly', body: 'Career moves, opportunities and women worth knowing, delivered to your inbox.', ctaLabel: 'Join WSF Weekly' },
  cookieConsent: { bannerEnabled: true, version: '1', title: 'We use cookies', body: 'We use essential technologies to make WSF work. With your permission, we may also use analytics and optional embedded media to understand how the site is used and provide third-party content.' },
  accountPolicy: { minimumAge: 16 },
  seo: {
    defaultTitle: 'Women Shaping Futures',
    defaultDescription: 'Women Shaping Futures — a global media, opportunity, and growth platform for women.',
    defaultOgImage: null,
  },
}
