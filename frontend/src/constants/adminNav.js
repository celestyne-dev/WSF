import {
  LayoutDashboard,
  Newspaper,
  Users,
  Briefcase,
  Award,
  CalendarDays,
  BookOpen,
  Mail,
  Inbox,
  Star,
  Handshake,
  Gem,
  Megaphone,
  Image,
  Search,
  BarChart3,
  Settings,
  LayoutTemplate,
  PenSquare,
  Building2,
  ShoppingBag,
  Send,
  Users2,
  GraduationCap,
  UserCheck,
  UserPlus,
  Link2,
  Hash,
  Folder,
  Layers,
  Tag,
  FileText,
  Compass,
  PanelBottom,
  History,
  ShieldCheck,
  MessageSquare,
  Library,
  Bell,
  Sparkles,
} from 'lucide-react'

// The single source of truth for the CMS sidebar AND the route-level access
// guard (see utils/routeAccess.js) — one list, not two, so a route can never
// be reachable directly while staying hidden from (or vice versa) the menu.
//
// Every `permission` array is the real backend gate for that section's
// primary API route (OR semantics, matching permission_required() in
// app/auth/decorators.py) — verified against each module's actual
// @permission_required(...)/has_permission() call, not assumed from the
// route's name. An item with no `permission` has no feature-specific gate
// server-side either (Notifications: any active CMS user).
export const NAV_GROUPS = [
  {
    heading: 'Overview',
    items: [
      // AdminDashboardResource requires analytics.view (app/api/v1/admin.py)
      // — most CMS roles (community_manager, newsletter_manager, etc.)
      // don't hold it, so Dashboard is gated here rather than being a
      // dead link; those roles land on their own area by default instead
      // (see getDefaultCmsRoute in utils/permissions.js).
      { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true, permission: ['analytics.view'] },
      // Available to every authenticated CMS user, unlike most other nav
      // items — this is a personal inbox, not a feature gated by a
      // specific permission (see backend api/v1/notifications.py's own
      // docstring on the same point).
      { to: '/admin/notifications', icon: Bell, label: 'Notifications' },
    ],
  },
  {
    heading: 'Content',
    items: [
      { to: '/admin/articles', icon: Newspaper, label: 'Articles', permission: ['articles.manage', 'articles.edit_own'] },
      { to: '/admin/editorial-calendar', icon: CalendarDays, label: 'Editorial Calendar', permission: ['articles.create', 'articles.edit_own', 'articles.manage', 'articles.publish'] },
      { to: '/admin/homepage', icon: LayoutTemplate, label: 'Homepage', permission: ['homepage.manage'] },
      { to: '/admin/navigation', icon: Compass, label: 'Navigation', permission: ['navigation.manage'] },
      { to: '/admin/footer', icon: PanelBottom, label: 'Footer', permission: ['footer.manage'] },
      { to: '/admin/people', icon: Users, label: 'People', permission: ['people.manage'] },
      { to: '/admin/authors', icon: PenSquare, label: 'Authors', permission: ['people.manage'] },
      { to: '/admin/organizations', icon: Building2, label: 'Organizations', permission: ['people.manage'] },
      { to: '/admin/pages', icon: FileText, label: 'Pages', permission: ['pages.manage'] },
    ],
  },
  {
    heading: 'Directory',
    items: [
      { to: '/admin/directory/listings', icon: Building2, label: 'Listings', permission: ['directory.manage'] },
      { to: '/admin/directory/submissions', icon: Inbox, label: 'Submissions', permission: ['directory.manage'] },
      { to: '/admin/directory/categories', icon: Folder, label: 'Categories', permission: ['taxonomy.manage'] },
    ],
  },
  {
    heading: 'Taxonomy',
    items: [
      { to: '/admin/taxonomy/topics', icon: Hash, label: 'Topics', permission: ['taxonomy.manage'] },
      { to: '/admin/taxonomy/categories', icon: Folder, label: 'Categories', permission: ['taxonomy.manage'] },
      { to: '/admin/taxonomy/series', icon: Layers, label: 'Series', permission: ['taxonomy.manage'] },
      { to: '/admin/taxonomy/tags', icon: Tag, label: 'Tags', permission: ['taxonomy.manage'] },
    ],
  },
  {
    heading: 'Opportunity',
    items: [
      { to: '/admin/jobs', icon: Briefcase, label: 'Jobs', permission: ['jobs.manage'] },
      { to: '/admin/opportunities', icon: Award, label: 'Opportunities', permission: ['opportunities.manage'] },
      { to: '/admin/events', icon: CalendarDays, label: 'Events', permission: ['events.manage'] },
      { to: '/admin/resources', icon: BookOpen, label: 'Resources', permission: ['resources.manage'] },
    ],
  },
  {
    heading: 'Shop',
    items: [{ to: '/admin/products', icon: ShoppingBag, label: 'Products', permission: ['products.manage'] }],
  },
  {
    heading: 'Learning',
    items: [{ to: '/admin/learning', icon: Library, label: 'Programs', permission: ['learning.manage'] }],
  },
  {
    heading: 'WSF Circle',
    items: [
      { to: '/admin/circle/plans', icon: Sparkles, label: 'Plans', permission: ['circle.manage'] },
      { to: '/admin/circle/memberships', icon: Users2, label: 'Memberships', permission: ['circle.manage'] },
    ],
  },
  {
    heading: 'Community',
    items: [
      { to: '/admin/members', icon: Users2, label: 'Members', permission: ['community.manage'] },
      { to: '/admin/community-page', icon: LayoutTemplate, label: 'Community Page', permission: ['community.manage'] },
      { to: '/admin/newsletter', icon: Mail, label: 'Newsletter', end: true, permission: ['newsletter.manage'] },
      { to: '/admin/newsletter/issues', icon: Send, label: 'Newsletter Issues', permission: ['newsletter.manage'] },
      { to: '/admin/newsletter/subscribers', icon: Users2, label: 'Subscribers', permission: ['newsletter.manage'] },
      { to: '/admin/submissions', icon: Inbox, label: 'Story Submissions', permission: ['submissions.manage'] },
      { to: '/admin/nominations', icon: Star, label: 'Nominations', permission: ['nominations.manage'] },
      { to: '/admin/contact', icon: MessageSquare, label: 'Contact Inquiries', permission: ['contact.manage'] },
    ],
  },
  {
    heading: 'Mentorship',
    items: [
      { to: '/admin/mentorship', icon: GraduationCap, label: 'Overview', end: true, permission: ['mentorship.manage'] },
      { to: '/admin/mentorship/programs', icon: CalendarDays, label: 'Programs', permission: ['mentorship.manage'] },
      { to: '/admin/mentorship/applications', icon: Inbox, label: 'Applications', permission: ['mentorship.manage'] },
      { to: '/admin/mentorship/mentors', icon: UserCheck, label: 'Mentors', permission: ['mentorship.manage'] },
      { to: '/admin/mentorship/mentees', icon: UserPlus, label: 'Mentees', permission: ['mentorship.manage'] },
      { to: '/admin/mentorship/matches', icon: Link2, label: 'Matches', permission: ['mentorship.manage'] },
    ],
  },
  {
    heading: 'Revenue',
    items: [
      { to: '/admin/partnerships', icon: Handshake, label: 'Partnerships', permission: ['partnerships.manage'] },
      { to: '/admin/sponsors', icon: Gem, label: 'Sponsors', permission: ['partnerships.manage'] },
      { to: '/admin/advertising', icon: Megaphone, label: 'Advertising', permission: ['partnerships.manage'] },
    ],
  },
  {
    heading: 'System',
    items: [
      { to: '/admin/media', icon: Image, label: 'Media Library', permission: ['media.upload', 'media.manage'] },
      // AdminGenericList's "seo" section loads admin redirects
      // (RedirectListResource, gated on articles.manage) alongside it —
      // same gate as Articles, not Settings.
      { to: '/admin/seo', icon: Search, label: 'SEO', permission: ['articles.manage'] },
      { to: '/admin/analytics', icon: BarChart3, label: 'Analytics', permission: ['analytics.view', 'analytics.commercial'] },
      { to: '/admin/users', icon: Users, label: 'Users', permission: ['users.view', 'users.manage', 'roles.manage'] },
      { to: '/admin/roles', icon: ShieldCheck, label: 'Roles & Permissions', permission: ['users.view', 'users.manage', 'roles.manage'] },
      { to: '/admin/audit', icon: History, label: 'Audit Log', permission: ['audit.view'] },
      { to: '/admin/settings', icon: Settings, label: 'Settings', permission: ['settings.manage'] },
    ],
  },
]
