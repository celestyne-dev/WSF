import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { primaryNavigation, secondaryNavigation, footerNavigation, socialLinks } from '../mock/navigation'
import { homepageModules } from '../mock/homepageModules'
import { newsletterIssues, newsletterStats } from '../mock/newsletter'
import { audienceStats } from '../mock/admin'

function mapNavItem(item) {
  return {
    id: item.id,
    label: item.label,
    url: item.url,
    order: item.sort_order,
    visible: item.visible,
    children: (item.children || []).map((c) => ({ id: c.id, label: c.label, url: c.url })),
  }
}

function mapFooterGroup(menus, key) {
  const menu = menus[key]
  if (!menu) return { heading: '', links: [] }
  return { heading: menu.heading, links: (menu.items || []).map((i) => ({ label: i.label, url: i.url })) }
}

function mapNavigation(data) {
  const menus = data.menus || {}
  return {
    primary: (menus.primary?.items || []).map(mapNavItem),
    secondary: (menus.secondary?.items || []).map(mapNavItem),
    footer: {
      explore: mapFooterGroup(menus, 'footer_explore'),
      opportunity: mapFooterGroup(menus, 'footer_opportunity'),
      wsf: mapFooterGroup(menus, 'footer_wsf'),
      legal: mapFooterGroup(menus, 'footer_legal'),
    },
    social: (data.socialLinks || []).map((s) => ({ platform: s.platform, url: s.url, handle: s.handle })),
  }
}

function mapHomepageModule(m) {
  return {
    id: m.id,
    type: m.type,
    enabled: m.enabled,
    order: m.sort_order,
    heading: m.heading,
    subheading: m.subheading,
    selectionMode: m.selection_mode,
    ...(m.config || {}),
  }
}

function mapNewsletterIssue(i) {
  return {
    id: i.id,
    slug: i.slug,
    issueNumber: i.issue_number,
    subject: i.subject,
    sendDate: i.send_date,
    featuredArticleSlug: i.featured_article?.slug || null,
    summary: i.summary,
  }
}

export async function fetchNavigation() {
  if (!USE_MOCK) return mapNavigation((await apiClient.get('/public/navigation')).data)
  return delay({ primary: primaryNavigation, secondary: secondaryNavigation, footer: footerNavigation, social: socialLinks })
}

// GET /api/v1/public/settings — a flexible key/value store (site name,
// tagline, contact email, maintenance mode, ...). No mock equivalent
// exists since nothing was previously CMS-editable here; mock mode
// returns {} so consumers fall back to their current static copy.
export async function fetchSiteSettings() {
  if (!USE_MOCK) return (await apiClient.get('/public/settings')).data
  return delay({})
}

export async function fetchHomepageModules() {
  if (!USE_MOCK) return (await apiClient.get('/public/homepage')).data.map(mapHomepageModule)
  return delay([...homepageModules].filter((m) => m.enabled).sort((a, b) => a.order - b.order))
}

export async function fetchNewsletterArchive() {
  if (!USE_MOCK) {
    const [issuesRes, statsRes] = await Promise.all([
      apiClient.get('/newsletter/issues'),
      apiClient.get('/newsletter/stats'),
    ])
    return {
      issues: issuesRes.data.items.map(mapNewsletterIssue),
      stats: {
        subscriberCount: statsRes.data.subscriberCount ?? 0,
        openRate: statsRes.data.openRate ?? null,
        weeklySends: statsRes.data.weeklySends ?? null,
      },
    }
  }
  return delay({ issues: newsletterIssues, stats: newsletterStats })
}

export async function subscribeToNewsletter(payload) {
  if (!USE_MOCK) {
    try {
      await apiClient.post('/newsletter/subscribe', payload)
      return { success: true, message: 'You’re subscribed. Look out for WSF Weekly every Thursday.' }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({ success: true, message: 'You’re subscribed. Look out for WSF Weekly every Thursday.' }, 500)
}

// GET /api/v1/partnerships/audience — CMS-editable LinkedIn/newsletter/
// website audience numbers for the About, Community, and Partnerships
// pages' media-kit stats. Never hard-code these into a page component.
export async function fetchAudienceStats() {
  if (!USE_MOCK) return (await apiClient.get('/partnerships/audience')).data
  return delay(audienceStats)
}

export async function submitPartnershipInquiry(payload) {
  if (!USE_MOCK) {
    try {
      await apiClient.post('/partnerships/inquiries', payload)
      return { success: true, message: 'Thank you — our partnerships team will respond within two business days.' }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({ success: true, message: 'Thank you — our partnerships team will respond within two business days.' }, 500)
}

export async function submitStory(payload) {
  if (!USE_MOCK) {
    try {
      await apiClient.post('/submissions', payload)
      return { success: true, message: 'Your story has been received and entered our editorial review queue.' }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({ success: true, message: 'Your story has been received and entered our editorial review queue.' }, 500)
}

export async function submitNomination(payload) {
  if (!USE_MOCK) {
    try {
      await apiClient.post('/nominations', payload)
      return { success: true, message: 'Thank you for your nomination — our editorial team reviews every submission.' }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({ success: true, message: 'Thank you for your nomination — our editorial team reviews every submission.' }, 500)
}
