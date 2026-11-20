// Public header mega-menu PRESENTATION, keyed by stable public destinations.
//
// The CMS (Settings > Navigation, GET /public/navigation) stays the single
// source of WHICH links appear and in what order. This file only describes
// HOW known destinations are presented: a menu's intro copy and column
// groups, a link's short description and optional icon, and where a
// secondary-menu item or an extra top-level item is folded in. A
// destination that isn't listed here still renders (under "More"); nothing
// here ever adds a link the CMS doesn't have. Icon names are resolved to
// lucide-react components in the Header (kept as strings so the builder in
// utils/megaMenu.js stays Node-testable).

// Top-level destination -> mega-menu presentation.
export const MENU_PRESENTATION = {
  '/topics': {
    key: 'stories',
    icon: 'Newspaper',
    description: 'Reporting, profiles and ideas on how women lead, work and build.',
    ctaLabel: 'Explore all topics',
    groups: [
      { key: 'read', label: 'Read' },
      { key: 'stay-informed', label: 'Stay informed' },
    ],
  },
  '/people': {
    key: 'people',
    icon: 'Users',
    description: 'The women, contributors and organizations shaping careers and industries.',
    ctaLabel: 'Browse the directory',
    groups: [{ key: 'directory', label: 'Directory' }],
  },
  '/opportunities': {
    key: 'opportunities',
    icon: 'Briefcase',
    description: 'Find your next role, opportunity or connection.',
    ctaLabel: 'View all opportunities',
    absorbs: ['/events', '/jobs', '/mentorship', '/directory'],
    groups: [
      { key: 'work', label: 'Work' },
      { key: 'connect', label: 'Connect' },
    ],
  },
  '/resources': {
    key: 'resources',
    icon: 'BookOpen',
    description: 'Practical tools and learning for every stage of your career.',
    ctaLabel: 'Explore all resources',
    absorbs: ['/shop', '/learning', '/career-hub'],
    groups: [
      { key: 'tools', label: 'Career tools' },
      { key: 'learn', label: 'Learn' },
    ],
  },
  '/community': {
    key: 'community',
    icon: 'HeartHandshake',
    description: 'Connect with women building careers, businesses and futures.',
    ctaLabel: 'Meet the community',
    groups: [
      { key: 'join', label: 'Get involved' },
      { key: 'about', label: 'About WSF' },
    ],
  },
}

// Link destination -> {group, description, icon?}. Icons are used
// selectively (only where they help scanning), never on every link.
export const LINK_PRESENTATION = {
  '/topics': { group: 'read', description: 'Every subject we cover.' },
  '/series': { group: 'read', description: 'Ongoing editorial series.' },
  '/newsletter': { group: 'stay-informed', description: 'WSF Weekly, in your inbox.', icon: 'Mail' },
  '/people': { group: 'directory', description: 'Profiles of women shaping industries.' },
  '/authors': { group: 'directory', description: 'Meet our writers and editors.' },
  '/organizations': { group: 'directory', description: 'Companies and institutions in our network.' },
  '/opportunities': { group: 'work', description: 'Scholarships, fellowships, grants and more.' },
  '/jobs': { group: 'work', description: 'Roles at organizations hiring now.', icon: 'BriefcaseBusiness' },
  '/events': { group: 'connect', description: 'Talks, workshops and gatherings.', icon: 'CalendarDays' },
  '/mentorship': { group: 'connect', description: 'Learn from women a step ahead.', icon: 'Users' },
  '/directory': { group: 'connect', description: 'Women-led businesses and services.' },
  '/career-hub': { group: 'tools', description: 'Tools for your next career move.', icon: 'Compass' },
  '/resources': { group: 'tools', description: 'Guides, templates and toolkits.' },
  '/shop': { group: 'tools', description: 'Books, templates and more.', icon: 'ShoppingBag' },
  '/learning': { group: 'learn', description: 'Courses and learning programs.', icon: 'GraduationCap' },
  '/community': { group: 'join', description: 'Join the WSF community.' },
  '/submit': { group: 'join', description: 'Share your story with WSF.', icon: 'PenLine' },
  '/nominate': { group: 'join', description: 'Recognize a woman making an impact.' },
  '/partnerships': { group: 'about', description: 'Collaborate with Women Shaping Futures.', icon: 'Handshake' },
  '/advertise': { group: 'about', description: 'Reach our audience.' },
  '/about': { group: 'about', description: 'Our mission and team.' },
  '/contact': { group: 'about', description: 'Get in touch.' },
}

// Secondary ("utility") CMS items -> the top-level menu they are shown in,
// now that the separate dark utility bar is gone. Unlisted secondary items
// fall back to the Community menu (or the last available menu).
export const SECONDARY_PLACEMENT = {
  '/newsletter': 'stories',
  '/partnerships': 'community',
  '/advertise': 'community',
  '/about': 'community',
  '/contact': 'community',
  '/submit': 'community',
  '/nominate': 'community',
  '/learning': 'resources',
  '/career-hub': 'resources',
  '/shop': 'resources',
  '/organizations': 'people',
  '/mentorship': 'opportunities',
  '/directory': 'opportunities',
  '/events': 'opportunities',
  '/jobs': 'opportunities',
}

export const SECONDARY_FALLBACK_MENU = 'community'

// Folding extra top-level items into menus never shrinks the visible
// desktop bar below this many items (target: about 5-7).
export const MIN_TOP_LEVEL = 5
