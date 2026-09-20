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

export const roleDefinitions = [
  { key: 'super_admin', label: 'Super Admin', description: 'Full access to every CMS area, including user management and site settings.' },
  { key: 'admin', label: 'Admin', description: 'Full content and commerce access, excluding user role management.' },
  { key: 'editor', label: 'Editor', description: 'Can create, edit, approve, and publish all editorial content.' },
  { key: 'author', label: 'Author', description: 'Can create and edit own articles; requires editor approval to publish.' },
  { key: 'moderator', label: 'Moderator', description: 'Reviews story submissions and nominations.' },
  { key: 'partnerships_manager', label: 'Partnerships Manager', description: 'Manages sponsors, partners, and partnership enquiries.' },
  { key: 'opportunities_manager', label: 'Opportunities Manager', description: 'Manages job, opportunity, and event listings.' },
  { key: 'events_manager', label: 'Events Manager', description: 'Manages event listings, agendas, and registrations.' },
  { key: 'analyst', label: 'Analyst', description: 'Read-only access to analytics dashboards.' },
  { key: 'member', label: 'Member', description: 'Registered reader with a public-facing account.' },
  { key: 'employer', label: 'Employer', description: 'Can submit and manage job and opportunity listings.' },
]

export const storySubmissions = [
  {
    id: 'sub1',
    name: 'Beatrice Achieng',
    email: 'beatrice.a@example.com',
    title: 'How I Rebuilt My Career After a Decade at Home',
    excerpt: 'After ten years raising three children, I had to relearn how to describe my own value on a job application.',
    submittedAt: '2026-09-12T09:30:00Z',
    status: 'reviewing',
  },
  {
    id: 'sub2',
    name: 'Miriam Okonkwo',
    email: 'miriam.o@example.com',
    title: 'What Nobody Tells You About Being the Only Woman on the Board',
    excerpt: 'I was the only woman in the room for four years before I understood why that was a design choice, not an accident.',
    submittedAt: '2026-09-10T14:15:00Z',
    status: 'received',
  },
  {
    id: 'sub3',
    name: 'Sarah Mbeki',
    email: 'sarah.mbeki@example.com',
    title: 'I Turned My Layoff Into a Six-Figure Consultancy',
    excerpt: 'The day I was let go, I gave myself thirty days to either find a job or build one.',
    submittedAt: '2026-09-08T11:00:00Z',
    status: 'accepted',
  },
  {
    id: 'sub4',
    name: 'Faith Wanjala',
    email: 'faith.w@example.com',
    title: 'Why I Left Banking to Become a Beekeeper',
    excerpt: 'I traded a corner office for 40 hives — and I have never made a clearer decision.',
    submittedAt: '2026-09-01T08:45:00Z',
    status: 'published',
  },
  {
    id: 'sub5',
    name: 'Ruth Chebet',
    email: 'ruth.c@example.com',
    title: 'My Startup Failed Publicly. Here Is What I Learned.',
    excerpt: 'We raised $400,000 and shut down eighteen months later. This is the retrospective I wish I had read first.',
    submittedAt: '2026-08-28T13:20:00Z',
    status: 'rejected',
  },
]

export const nominations = [
  {
    id: 'nom1',
    nomineeName: 'Judith Kilonzo',
    country: 'Kenya',
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
    country: 'Tanzania',
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
    country: 'Ghana',
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
