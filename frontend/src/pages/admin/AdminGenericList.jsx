import { people } from '../../mock/people'
import { jobs } from '../../mock/jobs'
import { opportunities } from '../../mock/opportunities'
import { events } from '../../mock/events'
import { resources } from '../../mock/resources'
import { newsletterIssues, newsletterStats } from '../../mock/newsletter'
import { storySubmissions, nominations, partnershipInquiries, adCampaigns } from '../../mock/admin'
import { articles } from '../../mock/articles'
import { formatDate, formatCurrency } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatCard from '../../components/cms/StatCard'
import StatusBadge from '../../components/cms/StatusBadge'
import MediaImage from '../../components/ui/MediaImage'
import { Users, Mail, MousePointerClick } from 'lucide-react'

const CONFIGS = {
  people: {
    title: 'People',
    description: 'Profiles shown in the People Directory.',
    columns: ['Name', 'Title', 'Organization', 'Country', 'Featured'],
    rows: people.map((p) => [p.name, p.title, p.organization, p.country, p.featured ? 'Yes' : '—']),
  },
  jobs: {
    title: 'Jobs',
    description: 'Job listings submitted by employers or added by the opportunities team.',
    columns: ['Title', 'Company', 'Location', 'Deadline', 'Featured'],
    rows: jobs.map((j) => [j.title, j.company, j.location, formatDate(j.deadline), j.featured ? 'Yes' : '—']),
  },
  opportunities: {
    title: 'Opportunities',
    description: 'Scholarships, fellowships, grants, and accelerators.',
    columns: ['Title', 'Organization', 'Type', 'Deadline'],
    rows: opportunities.map((o) => [o.title, o.organization, o.type, formatDate(o.deadline)]),
  },
  events: {
    title: 'Events',
    description: 'WSF and partner events, webinars, and conferences.',
    columns: ['Title', 'Type', 'Format', 'Date'],
    rows: events.map((e) => [e.title, e.type, e.format, formatDate(e.date)]),
  },
  resources: {
    title: 'Resources',
    description: 'Guides, templates, and worksheets in the resource library.',
    columns: ['Name', 'Type', 'Access', 'Price'],
    rows: resources.map((r) => [r.name, r.type, r.isPremium ? 'Premium' : 'Free', r.isPremium ? formatCurrency(r.price, r.currency) : '—']),
  },
  submissions: {
    title: 'Story Submissions',
    description: 'Reader-submitted stories awaiting editorial review.',
    columns: ['Name', 'Title', 'Submitted', 'Status'],
    rows: storySubmissions.map((s) => [s.name, s.title, formatDate(s.submittedAt), <StatusBadge key={s.id} status={s.status} />]),
  },
  nominations: {
    title: 'Nominations',
    description: 'Reader nominations for Women to Watch and other features.',
    columns: ['Nominee', 'Category', 'Submitted', 'Status'],
    rows: nominations.map((n) => [n.nomineeName, n.category, formatDate(n.submittedAt), <StatusBadge key={n.id} status={n.status} />]),
  },
  partnerships: {
    title: 'Partnership Inquiries',
    description: 'Inbound sponsorship and partnership requests.',
    columns: ['Company', 'Interest', 'Submitted', 'Status'],
    rows: partnershipInquiries.map((p) => [p.company, p.interest, formatDate(p.submittedAt), <StatusBadge key={p.id} status={p.status} />]),
  },
  advertising: {
    title: 'Advertising Campaigns',
    description: 'Direct and sponsored ad campaigns across placements.',
    columns: ['Advertiser', 'Placement', 'Impressions', 'Clicks', 'Status'],
    rows: adCampaigns.map((a) => [
      a.advertiser,
      a.placement,
      new Intl.NumberFormat('en-US').format(a.impressions),
      new Intl.NumberFormat('en-US').format(a.clicks),
      <StatusBadge key={a.id} status={a.status} />,
    ]),
  },
}

function NewsletterSection() {
  return (
    <div>
      <AdminPageHeader title="Newsletter" description="WSF Weekly subscriber base and issue archive." />
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Subscribers" value={new Intl.NumberFormat('en-US').format(newsletterStats.subscriberCount)} icon={Users} />
        <StatCard label="Average open rate" value={`${Math.round(newsletterStats.openRate * 100)}%`} icon={Mail} />
        <StatCard label="Weekly sends" value={newsletterStats.weeklySends} icon={MousePointerClick} />
      </div>
      <GenericTable columns={['Issue', 'Subject', 'Send Date']} rows={newsletterIssues.map((i) => [`#${i.issueNumber}`, i.subject, formatDate(i.sendDate)])} />
    </div>
  )
}

function MediaSection() {
  const items = articles.slice(0, 6).map((a) => ({ id: a.heroImage, alt: a.heroImageAlt, caption: a.heroImageCaption }))
  return (
    <div>
      <AdminPageHeader title="Media Library" description="Uploads stored on the Hostinger VPS filesystem, with alt text, captions, and credits managed centrally." />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {items.map((item) => (
          <div key={item.id} className="border border-taupe-200 bg-white p-2">
            <MediaImage mediaPath={item.id} alt={item.alt} width={400} height={300} aspect={4 / 3} className="aspect-[4/3] w-full object-cover" />
            <p className="mt-2 truncate text-xs text-charcoal-600">{item.id}</p>
            <p className="truncate text-xs text-charcoal-600/60">{item.alt}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function SeoSection() {
  return (
    <div>
      <AdminPageHeader title="SEO" description="Per-page metadata, canonical URLs, and redirects. Article canonical URLs are generated automatically from the flat public slug." />
      <GenericTable
        columns={['Article', 'SEO Title', 'Canonical URL']}
        rows={articles.slice(0, 6).map((a) => [a.title, a.seo?.title, a.seo?.canonical])}
      />
      <div className="mt-8">
        <p className="mb-2 text-sm font-semibold text-charcoal">Redirects</p>
        <GenericTable columns={['From', 'To', 'Type']} rows={[['/articles/how-women-are-redefining-leadership', '/how-women-are-redefining-leadership', '301 Permanent']]} />
      </div>
    </div>
  )
}

function GenericTable({ columns, rows }) {
  return (
    <div className="overflow-x-auto border border-taupe-200 bg-white">
      <table className="w-full min-w-[600px] text-left text-sm">
        <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-4 py-3">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-taupe-200">
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="max-w-xs truncate px-4 py-3 text-charcoal-600">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function AdminGenericList({ section }) {
  if (section === 'newsletter') return <NewsletterSection />
  if (section === 'media') return <MediaSection />
  if (section === 'seo') return <SeoSection />

  const config = CONFIGS[section]
  if (!config) return null

  return (
    <div>
      <AdminPageHeader title={config.title} description={config.description} />
      <GenericTable columns={config.columns} rows={config.rows} />
    </div>
  )
}
