import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// The mock newsletter dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockNewsletter
async function loadMockNewsletter() {
  if (!_mockNewsletter) _mockNewsletter = await import('../mock/newsletter')
  return _mockNewsletter
}

export function mapSubscriber(s) {
  if (!s) return null
  return {
    id: s.id,
    email: s.email,
    firstName: s.first_name || '',
    lastName: s.last_name || '',
    status: s.status,
    source: s.placement || '',
    country: s.country ? { code: s.country.code, name: s.country.name } : null,
    interests: Array.isArray(s.interests) ? s.interests.map((t) => ({ id: t.id, slug: t.slug, name: t.name })) : [],
    interestSlugs: Array.isArray(s.interests) ? s.interests.map((t) => t.slug) : [],
    subscribedAt: s.subscribed_at || null,
    unsubscribedAt: s.unsubscribed_at || null,
  }
}

export function mapIssue(i) {
  if (!i) return null
  return {
    id: i.id,
    slug: i.slug,
    issueNumber: i.issue_number ?? null,
    title: i.title || '',
    subject: i.subject,
    preheader: i.preheader || '',
    content: Array.isArray(i.content) ? i.content : [],
    coverMedia: mapMediaRef(i.cover_media) || null,
    summary: i.summary || '',
    featuredArticle: i.featured_article || null,
    featuredArticleSlug: i.featured_article?.slug || null,
    status: i.status || 'draft',
    audienceFilter: i.audience_filter || null,
    scheduledAt: i.scheduled_at || null,
    sendTimezone: i.send_timezone || 'UTC',
    sentAt: i.sent_at || null,
    estimatedRecipients: i.estimated_recipients ?? null,
    createdAt: i.created_at || null,
    updatedAt: i.updated_at || null,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export async function subscribeToNewsletter(payload) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.post('/newsletter/subscribe', payload)
      return { success: true, message: 'You’re subscribed. Look out for WSF Weekly every Thursday.', subscriber: data }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({ success: true, message: 'You’re subscribed. Look out for WSF Weekly every Thursday.' }, 500)
}

export async function unsubscribeByEmail(email) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/newsletter/unsubscribe', { email })
    return data
  }
  return delay({ status: 'unsubscribed' }, 300)
}

export async function unsubscribeByToken(token) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/newsletter/unsubscribe/${token}`)
    return data
  }
  return delay({ email: 'reader@example.com', status: 'unsubscribed' }, 300)
}

export async function fetchNewsletterArchive(params = {}) {
  if (!USE_MOCK) {
    const [issuesRes, statsRes] = await Promise.all([
      apiClient.get('/newsletter/issues', { params }),
      apiClient.get('/newsletter/stats'),
    ])
    return {
      issues: issuesRes.data.items.map(mapIssue),
      stats: {
        subscriberCount: statsRes.data.subscriberCount ?? 0,
        openRate: statsRes.data.openRate ?? null,
        weeklySends: statsRes.data.weeklySends ?? null,
      },
    }
  }
  const { newsletterIssues, newsletterStats } = await loadMockNewsletter()
  return delay({ issues: newsletterIssues, stats: newsletterStats })
}

export async function fetchNewsletterIssueBySlug(slug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/newsletter/issues/${slug}`)
      return mapIssue(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { newsletterIssues } = await loadMockNewsletter()
  return delay(newsletterIssues.find((i) => i.slug === slug) || null)
}

// ---------------------------------------------------------------------------
// Admin: subscribers
// ---------------------------------------------------------------------------

export async function fetchSubscribers(params = {}) {
  const { data } = await apiClient.get('/newsletter/subscribers', { params })
  return { ...data, items: data.items.map(mapSubscriber) }
}

export async function fetchSubscriber(id) {
  const { data } = await apiClient.get(`/newsletter/subscribers/${id}`)
  return mapSubscriber(data)
}

export async function updateSubscriber(id, payload) {
  const { data } = await apiClient.patch(`/newsletter/subscribers/${id}`, {
    firstName: payload.firstName || undefined,
    lastName: payload.lastName || undefined,
    countryCode: payload.countryCode || undefined,
    topicSlugs: payload.interestSlugs || undefined,
  })
  return mapSubscriber(data)
}

export async function suppressSubscriber(id) {
  const { data } = await apiClient.post(`/newsletter/subscribers/${id}/suppress`)
  return mapSubscriber(data)
}

export async function reactivateSubscriber(id) {
  const { data } = await apiClient.post(`/newsletter/subscribers/${id}/reactivate`)
  return mapSubscriber(data)
}

// Triggers a browser download of the CSV export rather than returning
// parsed data — subscriber export is a file-download action, not
// something a page renders.
export async function exportSubscribers(params = {}) {
  const response = await apiClient.get('/newsletter/subscribers/export', { params, responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `newsletter-subscribers-${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// Admin: issues / campaigns
// ---------------------------------------------------------------------------

export async function fetchNewsletterIssues(params = {}) {
  const { data } = await apiClient.get('/newsletter/issues', { params })
  return { ...data, items: data.items.map(mapIssue) }
}

function toIssuePayload(form) {
  return {
    title: form.title,
    subject: form.subject,
    preheader: form.preheader || undefined,
    slug: form.slug || undefined,
    issueNumber: form.issueNumber === '' || form.issueNumber == null ? undefined : Number(form.issueNumber),
    content: form.content || [],
    coverMediaId: form.coverMedia?.id || undefined,
    summary: form.summary || undefined,
    featuredArticleSlug: form.featuredArticleSlug || undefined,
    status: form.status || 'draft',
    audienceFilter: form.audienceFilter || undefined,
    scheduledAt: form.scheduledAt || undefined,
    sendTimezone: form.sendTimezone || 'UTC',
  }
}

export async function createNewsletterIssue(form) {
  const { data } = await apiClient.post('/newsletter/issues', toIssuePayload(form))
  return mapIssue(data)
}

export async function updateNewsletterIssue(slug, form) {
  const { data } = await apiClient.put(`/newsletter/issues/${slug}`, toIssuePayload(form))
  return mapIssue(data)
}

export async function markNewsletterIssueSent(slug) {
  const { data } = await apiClient.post(`/newsletter/issues/${slug}/mark-sent`)
  return mapIssue(data)
}

export async function archiveNewsletterIssue(slug) {
  const { data } = await apiClient.post(`/newsletter/issues/${slug}/archive`)
  return mapIssue(data)
}

export async function estimateAudience(audienceFilter) {
  const { data } = await apiClient.post('/newsletter/audience-estimate', { audienceFilter: audienceFilter || undefined })
  return data.estimatedRecipients
}

export async function fetchNewsletterOverview() {
  const { data } = await apiClient.get('/newsletter/overview')
  return {
    activeSubscribers: data.activeSubscribers,
    newSubscribers30d: data.newSubscribers30d,
    unsubscribedCount: data.unsubscribedCount,
    draftIssues: data.draftIssues,
    scheduledIssues: data.scheduledIssues,
    sentIssues: data.sentIssues,
  }
}

export async function fetchNewsletterSender() {
  const { data } = await apiClient.get('/newsletter/sender')
  return data
}
