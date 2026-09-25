// Unpublished editorial pipeline items — shown in the CMS only, layered on
// top of the published `articles` list so the Articles screen can
// demonstrate the full editorial workflow (draft/in_review/scheduled).
export const adminPipelineArticles = [
  {
    id: 'pipe1',
    title: 'Inside the Boardroom: What Women CFOs Wish They’d Known Sooner',
    authorSlug: 'grace-mwangi',
    topicSlug: 'careers',
    status: 'draft',
    updatedAt: '2026-09-13T15:00:00Z',
  },
  {
    id: 'pipe2',
    title: 'The Accelerator Cohort Six Months Later: Did It Work?',
    authorSlug: 'priya-nair',
    topicSlug: 'entrepreneurship',
    status: 'in_review',
    updatedAt: '2026-09-12T10:30:00Z',
  },
  {
    id: 'pipe3',
    title: 'Five Charts That Explain the Gender Pay Gap in Tech',
    authorSlug: 'temi-adeyemi',
    topicSlug: 'technology',
    status: 'scheduled',
    scheduledFor: '2026-09-27T08:00:00Z',
    updatedAt: '2026-09-11T09:00:00Z',
  },
]

export const adminUsers = [
  { id: 'u1', name: 'Wanjiru Kamau', email: 'wanjiru@womenshapingfutures.org', role: 'super_admin', status: 'active', lastLogin: '2026-09-14T09:12:00Z' },
  { id: 'u2', name: 'Amara Otieno', email: 'amara@womenshapingfutures.org', role: 'editor', status: 'active', lastLogin: '2026-09-14T07:45:00Z' },
  { id: 'u3', name: 'Grace Mwangi', email: 'grace@womenshapingfutures.org', role: 'editor', status: 'active', lastLogin: '2026-09-13T16:20:00Z' },
  { id: 'u4', name: 'Priya Nair', email: 'priya@womenshapingfutures.org', role: 'author', status: 'active', lastLogin: '2026-09-13T11:05:00Z' },
  { id: 'u5', name: 'Temi Adeyemi', email: 'temi@womenshapingfutures.org', role: 'author', status: 'active', lastLogin: '2026-09-10T14:30:00Z' },
  { id: 'u6', name: 'Faith Njeri', email: 'faith@womenshapingfutures.org', role: 'moderator', status: 'active', lastLogin: '2026-09-12T08:00:00Z' },
  { id: 'u7', name: 'Diana Kioko', email: 'diana@womenshapingfutures.org', role: 'partnerships_manager', status: 'active', lastLogin: '2026-09-11T10:15:00Z' },
  { id: 'u8', name: 'Sarah Wekesa', email: 'sarah@womenshapingfutures.org', role: 'opportunities_manager', status: 'invited', lastLogin: null },
]

// Role display labels/descriptions live in ../constants/roles.js — they're
// static UI metadata, not mock database records.

export const nominations = [
  {
    id: 'nom1',
    nomineeName: 'Judith Kilonzo',
    countryCode: 'KE',
    profession: 'Chief Financial Officer',
    organization: 'Kaziwave',
    achievements: 'Led Kaziwave through two funding rounds and built its finance function from scratch.',
    nominatorName: 'Naliaka Wafula',
    nominatorEmail: 'naliaka@kaziwave.example.com',
    relationship: 'Colleague / Manager',
    submittedAt: '2026-09-11T10:00:00Z',
    status: 'reviewing',
    category: 'Women to Watch',
  },
  {
    id: 'nom2',
    nomineeName: 'Rehema Suleiman',
    countryCode: 'TZ',
    profession: 'Marine Biologist',
    organization: 'University of Dar es Salaam',
    achievements: 'Leading coral reef restoration research recognized by two international science journals.',
    nominatorName: 'Anonymous',
    nominatorEmail: 'anon@example.com',
    relationship: 'Peer',
    submittedAt: '2026-09-09T16:40:00Z',
    status: 'received',
    category: 'Women in STEM',
  },
  {
    id: 'nom3',
    nomineeName: 'Comfort Adjei',
    countryCode: 'GH',
    profession: 'Founder',
    organization: 'Adjei Textiles',
    achievements: 'Built a textile export business employing 80 women artisans across rural Ghana.',
    nominatorName: 'Kwame Mensah',
    nominatorEmail: 'kwame.m@example.com',
    relationship: 'Business partner',
    submittedAt: '2026-09-05T09:10:00Z',
    status: 'accepted',
    category: 'Founder Stories',
  },
  {
    id: 'nom4',
    nomineeName: 'Christina Alvarez',
    countryCode: 'US',
    profession: 'Founder',
    organization: 'A Chicago-based logistics startup',
    achievements: 'Built a same-day delivery logistics platform now operating in eight US metro areas, entirely bootstrapped.',
    nominatorName: 'Danielle Reyes',
    nominatorEmail: 'danielle@lumenanalytics.example.com',
    relationship: 'Peer founder',
    submittedAt: '2026-09-14T12:00:00Z',
    status: 'received',
    category: 'Founder Stories',
  },
]

export const partnershipInquiries = [
  {
    id: 'pi1',
    company: 'Equity Bank',
    contactName: 'James Muriuki',
    email: 'james.muriuki@equitybank.example.com',
    interest: 'Newsletter sponsorship',
    message: 'We’d like to explore sponsoring WSF Weekly for a Q2 campaign around women-owned business banking.',
    submittedAt: '2026-09-12T13:00:00Z',
    status: 'new',
  },
  {
    id: 'pi2',
    company: 'Safaricom Foundation',
    contactName: 'Njoki Wanjiru',
    email: 'njoki.w@safaricomfoundation.example.com',
    interest: 'Sponsored series',
    message: 'Interested in co-branding a series on women in digital entrepreneurship.',
    submittedAt: '2026-09-08T10:30:00Z',
    status: 'in_discussion',
  },
  {
    id: 'pi3',
    company: 'Absa Bank Kenya',
    contactName: 'Peter Kimani',
    email: 'peter.kimani@absa.example.com',
    interest: 'Event sponsorship',
    message: 'Would like details on sponsorship tiers for the Women in Leadership Summit.',
    submittedAt: '2026-09-03T15:45:00Z',
    status: 'closed_won',
  },
]

export const adCampaigns = [
  {
    id: 'ad1',
    advertiser: 'Equity Bank',
    placement: 'homepage_top',
    creative: 'ads/equity-bank-banner',
    destinationUrl: 'https://equitybank.example.com',
    startDate: '2026-09-01',
    endDate: '2026-09-28',
    status: 'active',
    impressions: 128400,
    clicks: 1902,
    priority: 1,
  },
  {
    id: 'ad2',
    advertiser: 'Nadia Cosmetics',
    placement: 'article_sidebar',
    creative: 'ads/nadia-cosmetics-sidebar',
    destinationUrl: 'https://nadiacosmetics.example.com',
    startDate: '2026-08-15',
    endDate: '2026-10-15',
    status: 'active',
    impressions: 84200,
    clicks: 963,
    priority: 2,
  },
  {
    id: 'ad3',
    advertiser: 'University of Nairobi',
    placement: 'newsletter_banner',
    creative: 'ads/uon-newsletter',
    destinationUrl: 'https://uonbi.example.ac.ke',
    startDate: '2026-09-10',
    endDate: '2026-11-10',
    status: 'active',
    impressions: 34210,
    clicks: 512,
    priority: 1,
  },
  {
    id: 'ad4',
    advertiser: 'Orbital Health',
    placement: 'jobs_sidebar',
    creative: 'ads/orbital-health-jobs',
    destinationUrl: 'https://orbitalhealth.example.com',
    startDate: '2026-07-01',
    endDate: '2026-08-31',
    status: 'ended',
    impressions: 61300,
    clicks: 744,
    priority: 3,
  },
]

// CMS-editable audience / media-kit statistics (Settings > Media Kit).
// Never hard-code these numbers into a page component — always read them
// from here (or, once the backend exists, GET /api/v1/partnerships/audience)
// so the partnerships team can update them without a code deploy.
export const audienceStats = {
  linkedinFollowers: 132000,
  linkedinAvgReach: 480000,
  linkedinEngagementRate: 0.061,
  newsletterSubscribers: 34210,
  monthlyWebsiteVisitors: 210000,
  monthlyPageViews: 812400,
  countriesReached: 42,
  audienceGeography: [
    { region: 'North America', percent: 38 },
    { region: 'Africa', percent: 24 },
    { region: 'Europe', percent: 17 },
    { region: 'Asia', percent: 10 },
    { region: 'Latin America & Caribbean', percent: 6 },
    { region: 'Middle East', percent: 3 },
    { region: 'Oceania', percent: 2 },
  ],
  audienceIndustries: [
    { name: 'Technology', percent: 24 },
    { name: 'Financial Services', percent: 18 },
    { name: 'Professional Services', percent: 15 },
    { name: 'Healthcare & Life Sciences', percent: 11 },
    { name: 'Nonprofit & Education', percent: 10 },
    { name: 'Other', percent: 22 },
  ],
  audienceSeniority: [
    { level: 'Manager', percent: 28 },
    { level: 'Director / Senior Manager', percent: 26 },
    { level: 'VP / Executive', percent: 19 },
    { level: 'Founder / C-Suite', percent: 15 },
    { level: 'Individual Contributor', percent: 12 },
  ],
  updatedAt: '2026-09-15T00:00:00Z',
}

export const dashboardStats = {
  publishedArticles: 342,
  drafts: 18,
  scheduled: 6,
  subscribers: 34210,
  monthlyPageViews: 812400,
  activeJobs: 22,
  activeOpportunities: 14,
  upcomingEvents: 4,
  pendingSubmissions: 2,
  pendingNominations: 2,
}

export const pageViewsTrend = [
  { month: 'Apr', views: 512000 },
  { month: 'May', views: 588000 },
  { month: 'Jun', views: 634000 },
  { month: 'Jul', views: 601000 },
  { month: 'Aug', views: 742000 },
  { month: 'Sep', views: 812400 },
]

export const trafficBySource = [
  { name: 'Social', value: 44 },
  { name: 'Direct', value: 21 },
  { name: 'Search', value: 24 },
  { name: 'Newsletter', value: 11 },
]

export const topArticlesThisMonth = [
  { title: 'How Women Are Redefining Leadership in 2026', views: 48200 },
  { title: 'The Real Cost of Bootstrapping a Business in 2026', views: 36700 },
  { title: 'The Negotiation Conversation Nobody Prepares You For', views: 31150 },
  { title: 'Why Your LinkedIn Profile Is Costing You Interviews', views: 27340 },
  { title: 'The Woman Rebuilding a County Health System', views: 22980 },
]

export const subscriberGrowth = [
  { month: 'Apr', subscribers: 28100 },
  { month: 'May', subscribers: 29400 },
  { month: 'Jun', subscribers: 30650 },
  { month: 'Jul', subscribers: 31900 },
  { month: 'Aug', subscribers: 33200 },
  { month: 'Sep', subscribers: 34210 },
]
