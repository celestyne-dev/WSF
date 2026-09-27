import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'

// GET /api/v1/admin/audit — a read-only, paginated view over the
// existing app-wide AuditLog table (see backend app/services/audit.py
// and app/api/v1/admin_audit.py) — never a second logging system. There
// is no create/update/delete here by design: the Audit Log is append-
// only, and this module never writes to it.
//
// The backend already returns camelCase keys shaped exactly like this
// module's own consumers expect ({id, createdAt, actor, action,
// actionLabel, category, entity: {type, id, label}, metadata}) — no
// snake_case mapping needed here, unlike most other api/*.js modules.
export async function fetchAuditLog(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/audit', {
      params: {
        page: params.page,
        pageSize: params.pageSize || 50,
        actor: params.actor || undefined,
        action: params.action || undefined,
        entityType: params.entityType || undefined,
        entityId: params.entityId || undefined,
        category: params.category || undefined,
        dateFrom: params.dateFrom || undefined,
        dateTo: params.dateTo || undefined,
        q: params.query || undefined,
        sort: params.sort || undefined,
      },
    })
    // The shared response interceptor (api/client.js) already unwraps a
    // {data: [...], meta} envelope into {items, pagination} whenever the
    // response's `data` is an array — exactly this endpoint's shape.
    return data
  }
  const { auditLog } = await import('../mock/auditLog')
  let rows = auditLog
  if (params.action) rows = rows.filter((r) => r.action === params.action)
  if (params.entityType) rows = rows.filter((r) => r.entity.type === params.entityType)
  if (params.category) rows = rows.filter((r) => r.category === params.category)
  if (params.query) {
    const q = params.query.toLowerCase()
    rows = rows.filter(
      (r) =>
        r.action.toLowerCase().includes(q) ||
        r.actor?.name?.toLowerCase().includes(q) ||
        r.actor?.email?.toLowerCase().includes(q) ||
        r.entity?.label?.toLowerCase().includes(q),
    )
  }
  return delay(paginate(rows, params))
}
