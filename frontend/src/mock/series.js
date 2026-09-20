export const series = [
  {
    id: 's1',
    slug: 'women-doing-incredible-things',
    name: 'Women Doing Incredible Things',
    description:
      'Our flagship profile series celebrating women whose work — in business, science, government, or their own communities — deserves a wider audience.',
    coverImage: 'series/women-doing-incredible-things',
    sponsor: null,
    featured: true,
    articleCount: 86,
  },
  {
    id: 's2',
    slug: 'founder-stories',
    name: 'Founder Stories',
    description:
      'Honest, unpolished accounts of what it actually takes to start and grow a company — told by the women who did it.',
    coverImage: 'series/founder-stories',
    sponsor: { name: 'Baraza Ventures', logo: 'organizations/baraza-ventures' },
    featured: true,
    articleCount: 34,
  },
  {
    id: 's3',
    slug: 'women-who-started-again',
    name: 'Women Who Started Again',
    description:
      'Stories of career reinvention — women who left one path entirely to build another, often later in life than convention allows.',
    coverImage: 'series/women-who-started-again',
    sponsor: null,
    featured: false,
    articleCount: 22,
  },
  {
    id: 's4',
    slug: 'wsf-conversations',
    name: 'WSF Conversations',
    description: 'Long-form interviews with the women shaping business, policy, and culture across the continent and beyond.',
    coverImage: 'series/wsf-conversations',
    sponsor: null,
    featured: true,
    articleCount: 41,
  },
]

export const getSeriesBySlug = (slug) => series.find((s) => s.slug === slug)
