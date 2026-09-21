// Editorial topic taxonomy. Women Shaping Futures covers leadership,
// career, business, and personal-growth content — areas where we can offer
// strong editorial, educational, and inspirational value without acting as
// a specialist professional service. We deliberately do not run verticals
// that would require clinical, legal, tax, or regulated financial
// credentials (medical/health advice, legal advice, tax advice, or
// individualized investment recommendations).
//
// The CMS can add, rename, or retire topics without any frontend code
// change — this list stands in for a `Topic` database table.

export const topics = [
  {
    id: 't1',
    slug: 'leadership',
    name: 'Leadership',
    description:
      'Leadership journeys, communication, managing teams, and the lessons of women leading organizations around the world.',
    articleCount: 42,
  },
  {
    id: 't2',
    slug: 'careers',
    name: 'Career',
    description:
      'Career development, job search, interviews, personal branding, promotions, career transitions, and returning to work.',
    articleCount: 63,
  },
  {
    id: 't9',
    slug: 'business',
    name: 'Business',
    description: 'Running and growing a business — marketing, customer growth, pricing, and the everyday lessons of building something.',
    articleCount: 31,
  },
  {
    id: 't3',
    slug: 'entrepreneurship',
    name: 'Entrepreneurship',
    description: 'Founders, funding, first hires, and the realities of building a company from nothing.',
    articleCount: 51,
  },
  {
    id: 't7',
    slug: 'workplace',
    name: 'Workplace',
    description: 'Workplace culture, communication, professional relationships, and navigating the environments women work in.',
    articleCount: 37,
  },
  {
    id: 't11',
    slug: 'personal-growth',
    name: 'Personal Growth',
    description: 'Confidence, resilience, purpose, habits, and the transitions — planned or not — that reshape a career or a life.',
    articleCount: 28,
  },
  {
    id: 't4',
    slug: 'money',
    name: 'Money',
    description:
      'General career-economics education — salary negotiation, understanding compensation, asking for a raise, and business pricing. Not individualized investment, tax, or regulated financial advice.',
    articleCount: 29,
  },
  {
    id: 't12',
    slug: 'opportunities',
    name: 'Opportunities',
    description: 'Editorial coverage of the jobs, scholarships, fellowships, grants, and programmes worth knowing about.',
    articleCount: 18,
  },
  {
    id: 't6',
    slug: 'women-impact',
    name: 'Women & Impact',
    description: 'Women Doing Incredible Things, Women Leading Organizations, Founder Stories, Community Impact, and voices from around the world.',
    articleCount: 33,
  },
  {
    id: 't8',
    slug: 'women-founders',
    name: 'Women Founders',
    description: 'Founder journeys — the pitch that worked, the year that almost broke the company, and what came after.',
    articleCount: 19,
  },
  {
    id: 't5',
    slug: 'women-in-stem',
    name: 'Women in STEM',
    description: 'Scientists, engineers, and technologists changing what a career in STEM can look like.',
    articleCount: 24,
  },
  {
    id: 't10',
    slug: 'technology',
    name: 'Technology',
    description: 'Where women are building, investing in, and shaping the technology industry.',
    articleCount: 27,
  },
]

export const getTopicBySlug = (slug) => topics.find((t) => t.slug === slug)
