import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { primaryNavigation, secondaryNavigation, footerNavigation, socialLinks } from '../mock/navigation'
import { homepageModules } from '../mock/homepageModules'
import { newsletterIssues, newsletterStats } from '../mock/newsletter'

export async function fetchNavigation() {
  if (!USE_MOCK) return (await apiClient.get('/public/navigation')).data
  return delay({ primary: primaryNavigation, secondary: secondaryNavigation, footer: footerNavigation, social: socialLinks })
}

export async function fetchHomepageModules() {
  if (!USE_MOCK) return (await apiClient.get('/public/homepage')).data
  return delay([...homepageModules].filter((m) => m.enabled).sort((a, b) => a.order - b.order))
}

export async function fetchNewsletterArchive() {
  if (!USE_MOCK) return (await apiClient.get('/newsletter/issues')).data
  return delay({ issues: newsletterIssues, stats: newsletterStats })
}

export async function subscribeToNewsletter(payload) {
  if (!USE_MOCK) return (await apiClient.post('/newsletter/subscribe', payload)).data
  return delay({ success: true, message: 'You’re subscribed. Look out for WSF Weekly every Thursday.' }, 500)
}

export async function submitPartnershipInquiry(payload) {
  if (!USE_MOCK) return (await apiClient.post('/partnerships/inquiries', payload)).data
  return delay({ success: true, message: 'Thank you — our partnerships team will respond within two business days.' }, 500)
}

export async function submitStory(payload) {
  if (!USE_MOCK) return (await apiClient.post('/submissions', payload)).data
  return delay({ success: true, message: 'Your story has been received and entered our editorial review queue.' }, 500)
}

export async function submitNomination(payload) {
  if (!USE_MOCK) return (await apiClient.post('/nominations', payload)).data
  return delay({ success: true, message: 'Thank you for your nomination — our editorial team reviews every submission.' }, 500)
}
