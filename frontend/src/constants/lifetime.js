// WSF Lifetime copy — the SAME strings the server prerenders for /lifetime
// (backend app/services/spa_shell.py LIFETIME_*; a backend test keeps them
// in sync). "Eligible" is deliberate: Lifetime covers WSF-owned digital
// learning and resources, never "everything WSF will ever create".
export const LIFETIME_TITLE = 'Everything you need to keep growing your career — for life.'
export const LIFETIME_LEAD =
  'One payment. Lifetime access to eligible WSF courses, learning paths, premium career tools, resources and member benefits.'
export const LIFETIME_INCLUDED = [
  'Unlimited eligible WSF Learning courses',
  'Learning Paths',
  'Certificates of Completion when you complete a certificate-enabled course',
  'Premium Resource Vault',
  'Career Hub member benefits',
  'WSF Circle membership',
  'Future eligible WSF-owned digital courses and resources',
]
export const LIFETIME_EXCLUDED_NOTE =
  'Not included: physical products, 1:1 coaching, CV writing and other done-for-you services, consulting, retreats and travel, paid in-person events, partner or external courses, and third-party certifications.'

// Membership comparison. Every cell reflects the access rules the server
// actually enforces (backend services circle.py / resource_access.py /
// learning_access.py) — a column is only shown when a plan with that
// interval is really on sale. true = included, false = not included,
// string = a short qualified answer.
export const COMPARISON_ROWS = [
  { label: 'WSF articles and stories', free: true, monthly: true, yearly: true, lifetime: true },
  { label: 'Free Resources and free courses', free: true, monthly: true, yearly: true, lifetime: true },
  { label: 'Premium Resource Vault', free: 'Buy individually', monthly: true, yearly: true, lifetime: true },
  { label: 'WSF Circle courses', free: false, monthly: true, yearly: true, lifetime: true },
  { label: 'Premium WSF courses', free: 'Buy individually', monthly: 'Buy individually', yearly: 'Buy individually', lifetime: 'Included (eligible)' },
  { label: 'Learning Paths', free: 'Free courses', monthly: 'Free + Circle courses', yearly: 'Free + Circle courses', lifetime: 'All eligible courses' },
  { label: 'Certificates of Completion', free: 'On completion', monthly: 'On completion', yearly: 'On completion', lifetime: 'On completion' },
  { label: 'WSF Circle community and member tools', free: false, monthly: true, yearly: true, lifetime: true },
  { label: 'Annual-member bonus resources', free: false, monthly: false, yearly: true, lifetime: true },
  { label: 'Future eligible WSF digital content', free: false, monthly: 'While a member', yearly: 'While a member', lifetime: 'For life' },
  { label: 'Payment', free: '—', monthly: 'Renews monthly', yearly: 'Renews yearly', lifetime: 'One payment, no renewal' },
]
