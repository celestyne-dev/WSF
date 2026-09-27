// Mock-mode fixture for GET /api/v1/admin/audit — shaped identically to
// the real backend's response (see app/services/audit_query.py) so
// AdminAuditLog.jsx works the same whether VITE_USE_MOCK is true or
// false. Sample rows drawn from real, already-existing action names
// across the backend (see every log_action(...) call site) — not
// invented for this fixture.
export const auditLog = [
  {
    id: 1042,
    createdAt: '2026-09-27T09:14:00Z',
    actor: { id: 2, name: 'Wanjiru Kamau', email: 'wanjiru@womenshapingfutures.org' },
    action: 'settings.update',
    actionLabel: 'Updated site settings',
    category: 'site',
    entity: { type: 'SiteSetting', id: 'site_identity', label: 'Site Settings' },
    metadata: { site_name: 'Women Shaping Futures' },
  },
  {
    id: 1041,
    createdAt: '2026-09-27T08:52:00Z',
    actor: { id: 3, name: 'Amara Otieno', email: 'amara@womenshapingfutures.org' },
    action: 'article.publish',
    actionLabel: 'Published article',
    category: 'content',
    entity: { type: 'Article', id: '58', label: 'Women Are No Longer Waiting for Permission to Lead' },
    metadata: null,
  },
  {
    id: 1040,
    createdAt: '2026-09-27T08:10:00Z',
    actor: { id: 2, name: 'Wanjiru Kamau', email: 'wanjiru@womenshapingfutures.org' },
    action: 'user.deactivate',
    actionLabel: 'Deactivated account',
    category: 'access',
    entity: { type: 'User', id: '19', label: 'Sarah Wekesa' },
    metadata: null,
  },
  {
    id: 1039,
    createdAt: '2026-09-26T16:41:00Z',
    actor: { id: 2, name: 'Wanjiru Kamau', email: 'wanjiru@womenshapingfutures.org' },
    action: 'user.roles_update',
    actionLabel: 'Updated roles',
    category: 'access',
    entity: { type: 'User', id: '19', label: 'Sarah Wekesa' },
    metadata: { role_names: ['opportunities_manager'] },
  },
  {
    id: 1038,
    createdAt: '2026-09-26T14:05:00Z',
    actor: { id: 4, name: 'Diana Kioko', email: 'diana@womenshapingfutures.org' },
    action: 'partnership.status_change',
    actionLabel: 'Changed partnership status',
    category: 'commercial',
    entity: { type: 'PartnershipInquiry', id: '7', label: 'Equity Bank (James Muriuki)' },
    metadata: { from: 'contacted', to: 'qualified' },
  },
  {
    id: 1037,
    createdAt: '2026-09-26T11:22:00Z',
    actor: null,
    action: 'newsletter_subscribers_exported',
    actionLabel: 'Exported subscribers',
    category: 'newsletter',
    entity: { type: 'NewsletterSubscriber', id: null, label: 'Newsletter Subscriber' },
    metadata: { count: 1240 },
  },
  {
    id: 1036,
    createdAt: '2026-09-25T19:03:00Z',
    actor: { id: 3, name: 'Amara Otieno', email: 'amara@womenshapingfutures.org' },
    action: 'navigation.publish',
    actionLabel: 'Published navigation',
    category: 'site',
    entity: { type: 'Menu', id: null, label: 'Navigation/Footer' },
    metadata: { menu_keys: ['primary', 'secondary'] },
  },
]
