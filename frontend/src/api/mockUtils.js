// Shared helpers for the mock resource modules so every endpoint returns the
// same envelope shape a real Flask + Marshmallow response would: a resolved
// promise (never throws for reads), with pagination metadata when relevant.

export const delay = (data, ms = 220) => new Promise((resolve) => setTimeout(() => resolve(data), ms))

export function paginate(items, { page = 1, pageSize = 12 } = {}) {
  const start = (page - 1) * pageSize
  const pageItems = items.slice(start, start + pageSize)
  return {
    items: pageItems,
    pagination: {
      page,
      pageSize,
      totalItems: items.length,
      totalPages: Math.max(1, Math.ceil(items.length / pageSize)),
    },
  }
}
