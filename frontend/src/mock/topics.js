export const topics = [
  {
    id: 't1',
    slug: 'leadership',
    name: 'Leadership',
    description:
      'How women are leading teams, companies, movements, and countries — and rewriting the rules as they go.',
    articleCount: 42,
  },
  {
    id: 't2',
    slug: 'careers',
    name: 'Careers',
    description: 'Career moves, negotiation, promotions, career pivots, and the everyday work of building a working life.',
    articleCount: 63,
  },
  {
    id: 't3',
    slug: 'entrepreneurship',
    name: 'Entrepreneurship',
    description: 'Founders, funding, first hires, and the realities of building a business from nothing.',
    articleCount: 51,
  },
  {
    id: 't4',
    slug: 'money',
    name: 'Money',
    description: 'Investing, negotiating pay, building wealth, and closing the financial confidence gap.',
    articleCount: 29,
  },
  {
    id: 't5',
    slug: 'women-in-stem',
    name: 'Women in STEM',
    description: 'Scientists, engineers, and technologists changing what a career in STEM can look like.',
    articleCount: 24,
  },
  {
    id: 't6',
    slug: 'wellness',
    name: 'Wellness',
    description: 'Sustainable ambition — rest, boundaries, and the health habits that make a demanding life possible.',
    articleCount: 33,
  },
  {
    id: 't7',
    slug: 'workplace',
    name: 'Workplace',
    description: 'Culture, management, difficult conversations, and what actually makes a workplace work for women.',
    articleCount: 37,
  },
  {
    id: 't8',
    slug: 'social-impact',
    name: 'Social Impact',
    description: 'Women building organizations, policy, and movements to change their communities and countries.',
    articleCount: 21,
  },
  {
    id: 't9',
    slug: 'women-founders',
    name: 'Women Founders',
    description: 'Founder journeys — the pitch that worked, the year that almost broke the company, and what came after.',
    articleCount: 19,
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
