// Static mock fixtures for the Analytics Dashboard — mock mode only
// (VITE_USE_MOCK=true). Shapes mirror exactly what the real
// /api/v1/analytics/* endpoints return (see app/services/analytics_reports.py)
// so AdminAnalytics.jsx never needs a mock-specific code path.

export const overview = {
  range: { start: '2026-08-28', end: '2026-09-26' },
  metrics: {
    contentViews: 48200,
    articleViews: 31150,
    searchesPerformed: 4820,
    newsletterSignups: 612,
    jobViews: 3410,
    opportunityViews: 2190,
    eventViews: 1540,
    resourceDownloads: 980,
  },
  comparison: {
    previousStart: '2026-07-29',
    previousEnd: '2026-08-27',
    changes: {
      contentViews: 8.4,
      articleViews: 5.1,
      searchesPerformed: 12.7,
      newsletterSignups: -3.2,
      jobViews: 6.8,
      opportunityViews: 2.4,
      eventViews: 15.9,
      resourceDownloads: 4.0,
    },
  },
  audienceBySource: [
    { source: 'linkedin', count: 2120 },
    { source: 'direct', count: 1010 },
    { source: 'search', count: 860 },
    { source: 'newsletter', count: 520 },
  ],
  trend: {
    granularity: 'day',
    points: Array.from({ length: 14 }, (_, i) => ({
      date: `2026-09-${String(13 + i).padStart(2, '0')}`,
      contentViews: 2800 + i * 120,
      articleViews: 1800 + i * 80,
    })),
  },
}

export const content = {
  totalViews: 48200,
  totalArticles: 5,
  page: 1,
  perPage: 20,
  results: [
    { slug: 'how-women-are-redefining-leadership', title: 'How Women Are Redefining Leadership in 2026', url: '/how-women-are-redefining-leadership', views: 12400, publishedDate: '2026-08-14T00:00:00Z', topic: 'Workplace' },
    { slug: 'real-cost-of-bootstrapping', title: 'The Real Cost of Bootstrapping a Business in 2026', url: '/real-cost-of-bootstrapping', views: 9100, publishedDate: '2026-08-02T00:00:00Z', topic: 'Entrepreneurship' },
    { slug: 'negotiation-conversation', title: 'The Negotiation Conversation Nobody Prepares You For', url: '/negotiation-conversation', views: 7800, publishedDate: '2026-07-21T00:00:00Z', topic: 'Career' },
    { slug: 'linkedin-profile-interviews', title: 'Why Your LinkedIn Profile Is Costing You Interviews', url: '/linkedin-profile-interviews', views: 6300, publishedDate: '2026-07-09T00:00:00Z', topic: 'Career' },
    { slug: 'county-health-system', title: 'The Woman Rebuilding a County Health System', url: '/county-health-system', views: 5100, publishedDate: '2026-06-28T00:00:00Z', topic: 'Women & Impact' },
  ],
  topics: [
    { topic: 'Career', views: 14100 },
    { topic: 'Workplace', views: 12400 },
    { topic: 'Entrepreneurship', views: 9100 },
    { topic: 'Women & Impact', views: 5100 },
  ],
  series: [{ series: 'Founders in Focus', views: 6200 }],
}

export const search = {
  totalSearches: 4820,
  zeroResultSearches: 340,
  resultClicks: 3110,
  topQueries: [
    { query: 'leadership', count: 412, lastSearched: '2026-09-25T14:02:00Z' },
    { query: 'remote jobs', count: 298, lastSearched: '2026-09-25T09:11:00Z' },
    { query: 'fellowship', count: 201, lastSearched: '2026-09-24T18:40:00Z' },
    { query: 'mentorship', count: 176, lastSearched: '2026-09-23T11:05:00Z' },
  ],
  clicksByResultType: [
    { resultType: 'articles', count: 1420 },
    { resultType: 'jobs', count: 890 },
    { resultType: 'opportunities', count: 512 },
    { resultType: 'events', count: 288 },
  ],
}

export const newsletter = {
  newSubscribers: 612,
  unsubscribes: 48,
  activeTotal: 34210,
  growthTrend: Array.from({ length: 6 }, (_, i) => ({
    date: `2026-0${4 + i}-01`,
    newSubscribers: 480 + i * 30,
  })),
  issueViews: 8900,
}

export const careers = {
  jobs: {
    views: 3410,
    applyClicks: 612,
    topJobs: [
      { slug: 'marketing-director-harrow-vance', title: 'Marketing Director', url: '/jobs/marketing-director-harrow-vance', views: 890 },
      { slug: 'senior-financial-analyst', title: 'Senior Financial Analyst', url: '/jobs/senior-financial-analyst', views: 640 },
    ],
  },
  opportunities: {
    views: 2190,
    applyClicks: 340,
    topOpportunities: [{ slug: 'rising-leaders-fellowship', title: 'Rising Leaders Fellowship', url: '/opportunities/rising-leaders-fellowship', views: 710 }],
  },
  events: {
    views: 1540,
    registrationClicks: 260,
    topEvents: [{ slug: 'women-in-leadership-summit', title: 'Women in Leadership Summit 2026', url: '/events/women-in-leadership-summit', views: 520 }],
  },
  resources: {
    views: 2870,
    downloads: 980,
    downloadClicks: 1150,
    topResources: [{ slug: 'career-planning-guide', title: 'The 5-Year Career Planning Guide', url: '/resources/career-planning-guide', views: 1040 }],
  },
}

export const communityPrograms = {
  community: { joins: 84, activeMembers: 3120, countriesRepresented: 42 },
  mentorship: { mentorApplications: 22, menteeApplications: 61, activeMatches: 38, completedMatches: 14 },
  storySubmissions: { received: 19, approved: 8, published: 5 },
  nominations: { received: 27, shortlisted: 9, converted: 3 },
}

export const commercial = {
  sponsors: [
    { sponsor: 'Fintech Forward', impressions: 42000, clicks: 890, ctr: 2.12 },
    { sponsor: 'Career Bright', impressions: 18500, clicks: 210, ctr: 1.14 },
  ],
  advertise: { pageViews: 1240, mediaKitDownloads: 68, inquirySubmissions: 12, offeringClicks: 190 },
  partnerships: {
    inquiries: 22,
    byStatus: [
      { status: 'new', count: 6 },
      { status: 'qualified', count: 4 },
      { status: 'active', count: 8 },
      { status: 'completed', count: 4 },
    ],
  },
  orders: { byCurrency: [{ currency: 'USD', completedCount: 214, completedTotal: 8420 }, { currency: 'KES', completedCount: 38, completedTotal: 96000 }] },
}
