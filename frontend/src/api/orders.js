import { apiClient } from './client'

// Orders CMS — administrative views over app/models/commerce.py's Order/
// OrderItem/OrderNote. No payment gateway is wired up yet (see that
// model's own docstring): payment_provider/payment_reference/refund_*
// are administrative records, never the result of real payment
// processing. This module is staff administration only — it does not
// add a cart or checkout UI, so the public POST /orders (guest/logged-in
// checkout) endpoint has no caller here; see the final report.
//
// OrderSchema has no field exclusions (see backend/app/schemas/
// commerce.py) because it is never routed to a public listing — only to
// staff (orders.manage), the order's own owner, or whoever holds its
// unguessable uuid (the same role a confirmation-email link plays
// elsewhere). That access control lives entirely server-side in
// app/api/v1/orders.py; this adapter does not add a parallel one.

function mapOrderItem(i) {
  if (!i) return null
  return {
    id: i.id,
    productId: i.product_id,
    // Snapshot fields — fixed at purchase time, never re-derived from the
    // current Product record (see OrderItem's own docstring).
    productName: i.product_name,
    productSku: i.product_sku || '',
    productSlug: i.product_slug || '',
    productType: i.product_type || '',
    quantity: i.quantity,
    unitPrice: i.unit_price,
    lineTotal: i.line_total,
    currency: i.currency,
    // A lightweight preview of the CURRENT product, for an optional
    // "view product" link only — never the source of truth for what was
    // actually purchased. May be null if the product was later deleted.
    product: i.product ? { id: i.product.id, slug: i.product.slug, name: i.product.name, status: i.product.status } : null,
  }
}

function mapOrderNote(n) {
  if (!n) return null
  return {
    id: n.id,
    body: n.body,
    user: n.user ? { id: n.user.id, name: n.user.full_name, email: n.user.email } : null,
    createdAt: n.created_at,
  }
}

export function mapOrder(o) {
  if (!o) return null
  return {
    id: o.id,
    uuid: o.uuid,
    reference: o.reference || '',
    userId: o.user_id,
    email: o.email,
    customerName: o.customer_name || '',
    phone: o.phone || '',
    billingAddress: o.billing_address || null,
    shippingAddress: o.shipping_address || null,
    orderStatus: o.order_status,
    paymentStatus: o.payment_status,
    fulfillmentStatus: o.fulfillment_status,
    subtotalAmount: o.subtotal_amount,
    discountAmount: o.discount_amount,
    taxAmount: o.tax_amount,
    shippingAmount: o.shipping_amount,
    totalAmount: o.total_amount,
    currency: o.currency,
    paymentProvider: o.payment_provider || '',
    paymentReference: o.payment_reference || '',
    paidAt: o.paid_at || null,
    refundAmount: o.refund_amount ?? null,
    refundReason: o.refund_reason || '',
    refundedAt: o.refunded_at || null,
    cancelledAt: o.cancelled_at || null,
    cancellationReason: o.cancellation_reason || '',
    archived: !!o.archived,
    archivedAt: o.archived_at || null,
    requiresShipping: !!o.requires_shipping,
    items: Array.isArray(o.items) ? o.items.map(mapOrderItem) : [],
    // Absent entirely from the response for a non-staff viewer (the
    // backend strips it — see _dump_order's can_manage branch); only
    // ever populated here when the caller is orders.manage staff.
    notes: Array.isArray(o.notes) ? o.notes.map(mapOrderNote) : [],
    createdAt: o.created_at,
    updatedAt: o.updated_at,
  }
}

// ---------------------------------------------------------------------------
// Admin (orders.manage)
// ---------------------------------------------------------------------------

// Supports exactly what GET /orders accepts today: orderStatus/
// paymentStatus/fulfillmentStatus/currency equality filters, a free-text
// `query` search (reference/email/customer_name — the backend's own
// apply_search call), `archived`, and `dateFrom`/`dateTo`. No
// product-slug or customer-name-specific filter is exposed here — see
// the final report.
export async function fetchOrders(params = {}) {
  const { data } = await apiClient.get('/orders', { params })
  return { ...data, items: data.items.map(mapOrder) }
}

export async function fetchOrder(uuid) {
  const { data } = await apiClient.get(`/orders/${uuid}`)
  return mapOrder(data)
}

// Matches OrderAdminUpdateSchema exactly — the only fields an admin may
// change on an order after creation. Never send items/totals/customer
// fields through this; the backend schema doesn't accept them and would
// silently ignore them anyway.
export async function updateOrder(uuid, payload) {
  const body = {}
  if (payload.orderStatus !== undefined) body.orderStatus = payload.orderStatus
  if (payload.paymentStatus !== undefined) body.paymentStatus = payload.paymentStatus
  if (payload.fulfillmentStatus !== undefined) body.fulfillmentStatus = payload.fulfillmentStatus
  if (payload.paymentProvider !== undefined) body.paymentProvider = payload.paymentProvider || null
  if (payload.paymentReference !== undefined) body.paymentReference = payload.paymentReference || null
  if (payload.refundAmount !== undefined) body.refundAmount = payload.refundAmount === '' ? null : Number(payload.refundAmount)
  if (payload.refundReason !== undefined) body.refundReason = payload.refundReason || null
  const { data } = await apiClient.patch(`/orders/${uuid}`, body)
  return mapOrder(data)
}

export async function cancelOrder(uuid, reason) {
  const { data } = await apiClient.post(`/orders/${uuid}/cancel`, { reason: reason || undefined })
  return mapOrder(data)
}

export async function archiveOrder(uuid) {
  const { data } = await apiClient.post(`/orders/${uuid}/archive`)
  return mapOrder(data)
}

export async function unarchiveOrder(uuid) {
  const { data } = await apiClient.post(`/orders/${uuid}/unarchive`)
  return mapOrder(data)
}

export async function addOrderNote(uuid, body) {
  const { data } = await apiClient.post(`/orders/${uuid}/notes`, { body })
  return mapOrder(data)
}

export async function fetchOrderHistory(uuid) {
  const { data } = await apiClient.get(`/orders/${uuid}/history`)
  return data.map((entry) => ({
    id: entry.id,
    action: entry.action,
    user: entry.user ? entry.user.full_name : null,
    changes: entry.changes || null,
    createdAt: entry.created_at,
  }))
}

// Only safe to call when the order has never been paid/fulfilled — the
// backend enforces this (409 reference_conflict otherwise) and this
// adapter does not duplicate that rule.
export async function deleteOrder(uuid) {
  await apiClient.delete(`/orders/${uuid}`)
}

// Triggers a browser download of the CSV export.
export async function exportOrders(params = {}) {
  const response = await apiClient.get('/orders/export', { params, responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `orders-${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
