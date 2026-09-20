// CMS-controlled navigation. In production this is served from
// GET /api/v1/public/navigation and editable in Settings > Navigation.

export const primaryNavigation = [
  { id: 'n1', label: 'Stories', url: '/topics', order: 1, visible: true },
  {
    id: 'n2',
    label: 'People',
    url: '/people',
    order: 2,
    visible: true,
    children: [
      { id: 'n2a', label: 'People Directory', url: '/people' },
      { id: 'n2b', label: 'Authors', url: '/authors' },
      { id: 'n2c', label: 'Series', url: '/series' },
    ],
  },
  {
    id: 'n3',
    label: 'Topics',
    url: '/topics',
    order: 3,
    visible: true,
    children: [
      { id: 'n3a', label: 'Leadership', url: '/topics/leadership' },
      { id: 'n3b', label: 'Careers', url: '/topics/careers' },
      { id: 'n3c', label: 'Entrepreneurship', url: '/topics/entrepreneurship' },
      { id: 'n3d', label: 'Money', url: '/topics/money' },
      { id: 'n3e', label: 'Women in STEM', url: '/topics/women-in-stem' },
      { id: 'n3f', label: 'All Topics', url: '/topics' },
    ],
  },
  {
    id: 'n4',
    label: 'Opportunities',
    url: '/opportunities',
    order: 4,
    visible: true,
    children: [
      { id: 'n4a', label: 'All Opportunities', url: '/opportunities' },
      { id: 'n4b', label: 'Jobs', url: '/jobs' },
      { id: 'n4c', label: 'Events', url: '/events' },
    ],
  },
  { id: 'n7', label: 'Resources', url: '/resources', order: 5, visible: true },
  { id: 'n8', label: 'Mentorship', url: '/mentorship', order: 6, visible: true },
  { id: 'n9', label: 'Community', url: '/community', order: 7, visible: true },
]

export const secondaryNavigation = [
  { id: 's1', label: 'Newsletter', url: '/newsletter' },
  { id: 's2', label: 'Learning', url: '/learning' },
  { id: 's3', label: 'Organizations', url: '/organizations' },
  { id: 's4', label: 'Shop', url: '/shop' },
  { id: 's5', label: 'Partnerships', url: '/partnerships' },
  { id: 's6', label: 'About', url: '/about' },
]

export const footerNavigation = {
  explore: {
    heading: 'Explore',
    links: [
      { label: 'Stories', url: '/topics' },
      { label: 'People', url: '/people' },
      { label: 'Topics', url: '/topics' },
      { label: 'Series', url: '/series' },
      { label: 'Authors', url: '/authors' },
    ],
  },
  opportunity: {
    heading: 'Opportunity',
    links: [
      { label: 'Jobs', url: '/jobs' },
      { label: 'Opportunities', url: '/opportunities' },
      { label: 'Events', url: '/events' },
      { label: 'Resources', url: '/resources' },
      { label: 'Mentorship', url: '/mentorship' },
    ],
  },
  wsf: {
    heading: 'WSF',
    links: [
      { label: 'About', url: '/about' },
      { label: 'Partnerships', url: '/partnerships' },
      { label: 'Advertise', url: '/advertise' },
      { label: 'Newsletter', url: '/newsletter' },
      { label: 'Contact', url: '/contact' },
      { label: 'Submit a Story', url: '/submit' },
      { label: 'Nominate a Woman', url: '/nominate' },
    ],
  },
  legal: {
    heading: 'Legal',
    links: [
      { label: 'Privacy Policy', url: '/privacy' },
      { label: 'Terms of Use', url: '/terms' },
      { label: 'Cookie Policy', url: '/cookies' },
      { label: 'Editorial Policy', url: '/editorial-policy' },
    ],
  },
}

export const socialLinks = [
  { platform: 'instagram', url: 'https://instagram.com/womenshapingfutures', handle: '@womenshapingfutures' },
  { platform: 'linkedin', url: 'https://linkedin.com/company/womenshapingfutures', handle: 'Women Shaping Futures' },
  { platform: 'twitter', url: 'https://twitter.com/wsfmedia', handle: '@wsfmedia' },
  { platform: 'facebook', url: 'https://facebook.com/womenshapingfutures', handle: 'Women Shaping Futures' },
  { platform: 'youtube', url: 'https://youtube.com/@womenshapingfutures', handle: 'Women Shaping Futures' },
]
