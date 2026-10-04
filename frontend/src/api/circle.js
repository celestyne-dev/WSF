import { apiClient } from './client'

// WSF Circle — provider-neutral premium membership. See backend
// app/models/circle.py / app/services/circle.py / app/api/v1/circle.py.
// No payment gateway exists — this module never implements checkout,
// payment-success callbacks, or subscribe/activate actions for ordinary
// users (see CircleMeResource's GET-only owner API).

// Handles both shapes GET /circle/plans can return from the SAME
// endpoint: the public, already-camelCase build_public_plan_payload()
// subset (no id/status/displayOrder/manageBillingUrl/timestamps), and
// the admin AutoSchema's full snake_case dump — same dual-read
// convention as api/products.js's mapProduct().
export function mapCirclePlan(p) {
  if (!p) return null
  return {
    id: p.id ?? null,
    slug: p.slug,
    name: p.name,
    shortDescription: p.short_description ?? p.shortDescription ?? '',
    description: Array.isArray(p.description) ? p.description : [],
    billingInterval: p.billing_interval || p.billingInterval || 'monthly',
    price: p.price ?? 0,
    currency: p.currency || 'USD',
    status: p.status || 'active',
    featured: !!p.featured,
    displayOrder: p.display_order ?? p.displayOrder ?? 0,
    checkoutUrl: p.checkout_url ?? p.checkoutUrl ?? null,
    checkoutAvailable: p.checkoutAvailable ?? !!(p.checkout_url ?? p.checkoutUrl),
    manageBillingUrl: p.manage_billing_url ?? p.manageBillingUrl ?? null,
    benefits: Array.isArray(p.benefits) ? p.benefits : [],
    seo: p.seo || {},
    createdAt: p.created_at || null,
    updatedAt: p.updated_at || null,
  }
}

// Handles both the admin AutoSchema's full snake_case dump (GET
// /circle/subscriptions*) and the owner-safe, already-camelCase
// build_owner_subscription_payload() shape (GET /circle/me) — provider
// customer/subscription ids and payment reference are simply absent from
// the owner shape, never present to map.
export function mapCircleSubscription(s) {
  if (!s) return null
  return {
    id: s.id,
    status: s.status,
    source: s.source || null,
    provider: s.provider || null,
    providerCustomerId: s.provider_customer_id ?? s.providerCustomerId ?? null,
    providerSubscriptionId: s.provider_subscription_id ?? s.providerSubscriptionId ?? null,
    paymentReference: s.payment_reference ?? s.paymentReference ?? null,
    startsAt: s.starts_at ?? s.startsAt ?? null,
    currentPeriodStart: s.current_period_start ?? s.currentPeriodStart ?? null,
    currentPeriodEnd: s.current_period_end ?? s.currentPeriodEnd ?? null,
    cancelAtPeriodEnd: !!(s.cancel_at_period_end ?? s.cancelAtPeriodEnd),
    cancelledAt: s.cancelled_at ?? s.cancelledAt ?? null,
    endedAt: s.ended_at ?? s.endedAt ?? null,
    createdAt: s.created_at || null,
    updatedAt: s.updated_at || null,
    plan: s.plan ? mapCirclePlan(s.plan) : null,
    user: s.user ? { id: s.user.id, fullName: s.user.full_name || s.user.fullName, email: s.user.email } : null,
  }
}

function buildPlanPayload(payload) {
  return {
    name: payload.name,
    slug: payload.slug || undefined,
    shortDescription: payload.shortDescription || undefined,
    description: payload.description,
    billingInterval: payload.billingInterval || undefined,
    price: payload.price,
    currency: payload.currency || undefined,
    status: payload.status || undefined,
    featured: payload.featured,
    displayOrder: payload.displayOrder,
    checkoutUrl: payload.checkoutUrl || undefined,
    manageBillingUrl: payload.manageBillingUrl || undefined,
    benefits: payload.benefits,
    seo: payload.seo || undefined,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export async function fetchCirclePlans(params = {}) {
  const { data } = await apiClient.get('/circle/plans', { params })
  return (data || []).map(mapCirclePlan)
}

export async function fetchCirclePlan(slug) {
  const { data } = await apiClient.get(`/circle/plans/${slug}`)
  return mapCirclePlan(data)
}

// ---------------------------------------------------------------------------
// Authenticated owner (/circle/me) — GET only, by design: payment
// activation is admin/provider-side only, never a self-service action.
// ---------------------------------------------------------------------------

export async function fetchMyCircleMembership() {
  const { data } = await apiClient.get('/circle/me')
  return { hasAccess: !!data?.hasAccess, subscription: mapCircleSubscription(data?.subscription) }
}

// ---------------------------------------------------------------------------
// Admin — plans (circle.manage)
// ---------------------------------------------------------------------------

export async function fetchAdminCirclePlans(params = {}) {
  const { data } = await apiClient.get('/circle/plans', { params })
  return (data || []).map(mapCirclePlan)
}

export async function fetchAdminCirclePlan(slug) {
  const { data } = await apiClient.get(`/circle/plans/${slug}`)
  return mapCirclePlan(data)
}

export async function createCirclePlan(payload) {
  const { data } = await apiClient.post('/circle/plans', buildPlanPayload(payload))
  return mapCirclePlan(data)
}

export async function updateCirclePlan(slug, payload) {
  const { data } = await apiClient.patch(`/circle/plans/${slug}`, buildPlanPayload(payload))
  return mapCirclePlan(data)
}

export async function deleteCirclePlan(slug) {
  await apiClient.delete(`/circle/plans/${slug}`)
}

// ---------------------------------------------------------------------------
// Admin — subscriptions/memberships (circle.manage)
// ---------------------------------------------------------------------------

export async function fetchCircleSubscriptions(params = {}) {
  const { data } = await apiClient.get('/circle/subscriptions', { params })
  return { ...data, items: data.items.map(mapCircleSubscription) }
}

export async function fetchCircleSubscription(id) {
  const { data } = await apiClient.get(`/circle/subscriptions/${id}`)
  return mapCircleSubscription(data)
}

// Staff records a subscription for an EXISTING WSF account, found by
// exact normalized email — never an arbitrary userId (see backend
// app/api/v1/circle.py's CircleSubscriptionListResource.post).
export async function createCircleSubscription(payload) {
  const body = {
    email: payload.email,
    planId: payload.planId,
    status: payload.status || undefined,
    source: payload.source,
    provider: payload.provider || undefined,
    providerCustomerId: payload.providerCustomerId || undefined,
    providerSubscriptionId: payload.providerSubscriptionId || undefined,
    paymentReference: payload.paymentReference || undefined,
    startsAt: payload.startsAt || undefined,
    currentPeriodStart: payload.currentPeriodStart || undefined,
    currentPeriodEnd: payload.currentPeriodEnd || undefined,
    cancelAtPeriodEnd: payload.cancelAtPeriodEnd,
  }
  const { data } = await apiClient.post('/circle/subscriptions', body)
  return mapCircleSubscription(data)
}

// Partial update — only keys actually present in `payload` are sent.
export async function updateCircleSubscription(id, payload = {}) {
  const body = {}
  const fieldKeys = [
    'status', 'provider', 'providerCustomerId', 'providerSubscriptionId', 'paymentReference',
    'startsAt', 'currentPeriodStart', 'currentPeriodEnd', 'cancelAtPeriodEnd',
  ]
  fieldKeys.forEach((key) => {
    if (payload[key] !== undefined) body[key] = payload[key]
  })
  const { data } = await apiClient.patch(`/circle/subscriptions/${id}`, body)
  return mapCircleSubscription(data)
}
