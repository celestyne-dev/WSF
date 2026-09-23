export const SPONSORSHIP_TYPES = [
  'Brand Sponsor',
  'Newsletter Sponsor',
  'Event Sponsor',
  'Content Sponsor',
  'Series Sponsor',
  'Resource Sponsor',
  'Employer Sponsor',
  'Community Sponsor',
  'Supporting Partner',
  'Presenting Sponsor',
  'Other',
]

export const SPONSOR_STATUSES = ['draft', 'scheduled', 'active', 'paused', 'completed', 'archived']

export const SPONSOR_DISCLOSURE_LABELS = ['Sponsored', 'Sponsored by', 'Presented by', 'In partnership with']

// Deliberately limited to placements this app actually renders (homepage
// strip, article disclosure banner) — see backend SPONSOR_PLACEMENT_KEYS.
export const SPONSOR_PLACEMENT_KEYS = ['homepage_featured', 'homepage_footer', 'article_sidebar', 'article_inline']

export const SPONSOR_PLACEMENT_LABELS = {
  homepage_featured: 'Homepage — featured strip',
  homepage_footer: 'Homepage — footer strip',
  article_sidebar: 'Article — sidebar',
  article_inline: 'Article — inline',
}
