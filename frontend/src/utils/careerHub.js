// WSF Career Hub — pure (Node-testable) rules for URL-driven filter state
// and card display. The backend (app/services/career_hub.py) is the source
// of truth for the vocabulary: the page fetches it from
// GET /career-hub/meta and every URL value is checked against it, so an
// unknown/stale value in a shared link is dropped instead of breaking the
// page. Display helpers never decide access — they only phrase what the
// server already computed (circle inclusion, prices, access level).
import { pickDefaultPrice } from './money.js'

export const HUB_FILTER_KEYS = ['q', 'goal', 'format', 'access', 'sort']
export const DEFAULT_SORT = 'newest'
export const PAGE_SIZE = 12

const MAX_QUERY_LENGTH = 100

function allowed(options, value) {
  return (options || []).some((o) => o.slug === value)
}

// URLSearchParams + meta vocabulary -> clean filter state. `goal` may also
// be a Topic slug (e.g. salary-negotiation) — the server resolves those, so
// when `topicAliases` isn't known yet a non-canonical goal is kept as-is.
export function parseHubParams(searchParams, meta) {
  const get = (key) => (searchParams.get(key) || '').trim()
  const goal = get('goal').toLowerCase()
  const format = get('format').toLowerCase()
  const access = get('access').toLowerCase()
  const sort = get('sort').toLowerCase()
  const page = Number.parseInt(get('page'), 10)
  return {
    q: get('q').slice(0, MAX_QUERY_LENGTH),
    goal: goal && (/^[a-z0-9-]+$/.test(goal) ? goal : ''),
    format: meta && !allowed(meta.formats, format) ? '' : format,
    access: meta && !allowed(meta.access, access) ? '' : access,
    sort: (meta && !allowed(meta.sorts, sort)) || !sort ? DEFAULT_SORT : sort,
    page: Number.isInteger(page) && page > 1 ? page : 1,
  }
}

// Filter state -> canonical query string (defaults omitted, stable order),
// so the same view always has the same URL.
export function buildHubSearch(state) {
  const params = new URLSearchParams()
  if (state.q?.trim()) params.set('q', state.q.trim())
  if (state.goal) params.set('goal', state.goal)
  if (state.format) params.set('format', state.format)
  if (state.access) params.set('access', state.access)
  if (state.sort && state.sort !== DEFAULT_SORT) params.set('sort', state.sort)
  if (state.page && state.page > 1) params.set('page', String(state.page))
  const text = params.toString()
  return text ? `?${text}` : ''
}

// Any filter change resets to page 1; only an explicit page change keeps it.
export function updateHubState(state, patch) {
  const next = { ...state, ...patch }
  if (!('page' in patch)) next.page = 1
  return next
}

export function isFiltering(state) {
  return Boolean(state.q?.trim() || state.goal || state.format || state.access)
}

export function resetHubState() {
  return { q: '', goal: '', format: '', access: '', sort: DEFAULT_SORT, page: 1 }
}

// Server request params for GET /career-hub.
export function hubRequestParams(state) {
  const params = { page: state.page || 1, pageSize: PAGE_SIZE, sort: state.sort || DEFAULT_SORT }
  for (const key of ['q', 'goal', 'format', 'access']) if (state[key]) params[key] = state[key]
  return params
}

// "Playbook · 45–60 min"
export function cardMetaLine(card) {
  return [card?.format?.label, card?.estimatedTime?.label].filter(Boolean).join(' · ')
}

// "SALARY & NEGOTIATION" — the card's topic, else its career goal.
export function cardEyebrow(card) {
  return card?.category?.name || card?.goal?.label || ''
}

// "KES 1,500 one-time" (server-formatted, default currency) or null.
export function cardPriceLine(card) {
  const pricing = card?.pricing
  if (!pricing?.prices?.length) return null
  const price = pickDefaultPrice(pricing.prices, pricing.defaultCurrency)
  if (!price?.formatted) return null
  return pricing.oneTime === false ? price.formatted : `${price.formatted} one-time`
}

// "Included with WSF Circle" / "Included with Yearly & Lifetime WSF Circle" — only
// when the server says Circle genuinely grants it.
export function cardCircleLine(card) {
  return card?.circle?.included && card.circle.label ? card.circle.label : null
}

// Signed-in viewer whose own membership covers this item (server-computed,
// e.g. "Included with your Lifetime membership") — shown as the primary
// state instead of a buy price. Null for anonymous / not covered.
export function cardViewerLine(card) {
  return card?.viewer?.included && card.viewer.label ? card.viewer.label : null
}

// Short access phrase for items with no price line (free / Circle-only).
export function cardAccessLine(card) {
  if (cardPriceLine(card)) return null
  if (card?.access?.level === 'circle' && cardCircleLine(card)) return null
  return card?.access?.label || null
}

// Human summary of the active filters, for the live results announcement.
export function describeResults(total, state, meta) {
  const label = (list, slug) => (list || []).find((o) => o.slug === slug)?.label || slug
  const parts = []
  if (state.goal) parts.push(label(meta?.goals, state.goal))
  if (state.format) parts.push(label(meta?.formats, state.format))
  if (state.access) parts.push(label(meta?.access, state.access))
  if (state.q?.trim()) parts.push(`“${state.q.trim()}”`)
  const count = `${total} ${total === 1 ? 'tool' : 'tools'}`
  return parts.length ? `${count} for ${parts.join(', ')}` : count
}
