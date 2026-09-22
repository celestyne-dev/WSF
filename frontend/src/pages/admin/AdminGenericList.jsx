import { useEffect, useState } from 'react'
import { fetchEvents } from '../../api/events'
import { fetchResources } from '../../api/resources'
import { fetchNewsletterArchive } from '../../api/site'
import {
  fetchStorySubmissions,
  fetchNominations,
  fetchPartnershipInquiries,
  fetchAdCampaigns,
  fetchRedirects,
} from '../../api/admin'
import { fetchArticles } from '../../api/articles'
import { formatDate, formatCurrency } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatCard from '../../components/cms/StatCard'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { Users, Mail, MousePointerClick } from 'lucide-react'

const CONFIGS = {
  events: {
    title: 'Events',
    description: 'WSF and partner events, webinars, and conferences.',
    columns: ['Title', 'Type', 'Format', 'Date'],
    load: async () => {
      const res = await fetchEvents({ pageSize: 100 })
      return res.items.map((e) => [e.title, e.type, e.format, formatDate(e.date)])
    },
  },
  resources: {
    title: 'Resources',
    description: 'Guides, templates, and worksheets in the resource library.',
    columns: ['Name', 'Type', 'Access', 'Price'],
    load: async () => {
      const res = await fetchResources({ pageSize: 100 })
      return res.items.map((r) => [r.name, r.type, r.isPremium ? 'Premium' : 'Free', r.isPremium ? formatCurrency(r.price, r.currency) : '—'])
    },
  },
  submissions: {
    title: 'Story Submissions',
    description: 'Reader-submitted stories awaiting editorial review.',
    columns: ['Name', 'Country', 'Title', 'Submitted', 'Status'],
    load: async () => {
      const rows = await fetchStorySubmissions()
      return rows.map((s) => [s.name, s.country?.name || s.countryCode, s.title, formatDate(s.submittedAt), <StatusBadge key={s.id} status={s.status} />])
    },
  },
  nominations: {
    title: 'Nominations',
    description: 'Reader nominations for Women to Watch and other features.',
    columns: ['Nominee', 'Country', 'Category', 'Submitted', 'Status'],
    load: async () => {
      const rows = await fetchNominations()
      return rows.map((n) => [n.nomineeName, n.country?.name || n.countryCode, n.category, formatDate(n.submittedAt), <StatusBadge key={n.id} status={n.status} />])
    },
  },
  partnerships: {
    title: 'Partnership Inquiries',
    description: 'Inbound sponsorship and partnership requests.',
    columns: ['Company', 'Interest', 'Submitted', 'Status'],
    load: async () => {
      const rows = await fetchPartnershipInquiries()
      return rows.map((p) => [p.company, p.interest, formatDate(p.submittedAt), <StatusBadge key={p.id} status={p.status} />])
    },
  },
  advertising: {
    title: 'Advertising Campaigns',
    description: 'Direct and sponsored ad campaigns across placements.',
    columns: ['Advertiser', 'Placement', 'Impressions', 'Clicks', 'Status'],
    load: async () => {
      const rows = await fetchAdCampaigns()
      return rows.map((a) => [
        a.advertiser,
        a.placement,
        new Intl.NumberFormat('en-US').format(a.impressions),
        new Intl.NumberFormat('en-US').format(a.clicks),
        <StatusBadge key={a.id} status={a.status} />,
      ])
    },
    emptyMessage: 'Ad campaign tracking isn’t built on the backend yet — nothing to show here in real mode.',
  },
}

function NewsletterSection() {
  const [archive, setArchive] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchNewsletterArchive()
      .then((data) => active && setArchive(data))
      .catch(() => active && setError('Something went wrong loading the newsletter archive. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  if (error) return <EmptyState title="Couldn't load newsletter data" description={error} />
  if (archive === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader title="Newsletter" description="WSF Weekly subscriber base and issue archive." />
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Subscribers" value={new Intl.NumberFormat('en-US').format(archive.stats.subscriberCount)} icon={Users} />
        <StatCard label="Average open rate" value={archive.stats.openRate != null ? `${Math.round(archive.stats.openRate * 100)}%` : '—'} icon={Mail} />
        <StatCard label="Weekly sends" value={archive.stats.weeklySends ?? '—'} icon={MousePointerClick} />
      </div>
      <GenericTable columns={['Issue', 'Subject', 'Send Date']} rows={archive.issues.map((i) => [`#${i.issueNumber}`, i.subject, formatDate(i.sendDate)])} />
    </div>
  )
}

function SeoSection() {
  const [articles, setArticles] = useState(undefined)
  const [redirects, setRedirects] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchArticles({ pageSize: 6 }), fetchRedirects()])
      .then(([articlesRes, redirectRows]) => {
        if (!active) return
        setArticles(articlesRes.items)
        setRedirects(redirectRows)
      })
      .catch(() => active && setError('Something went wrong loading SEO data. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  if (error) return <EmptyState title="Couldn't load SEO data" description={error} />
  if (articles === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader title="SEO" description="Per-page metadata, canonical URLs, and redirects. Article canonical URLs are generated automatically from the flat public slug." />
      <GenericTable columns={['Article', 'SEO Title', 'Canonical URL']} rows={articles.map((a) => [a.title, a.seo?.title, a.seo?.canonical])} />
      <div className="mt-8">
        <p className="mb-2 text-sm font-semibold text-charcoal">Redirects</p>
        <GenericTable columns={['From', 'To', 'Type']} rows={redirects.map((r) => [r.from, r.to, '301 Permanent'])} />
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

function ConfiguredSection({ config }) {
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setRows(undefined)
    setError(null)
    config
      .load()
      .then((data) => active && setRows(data))
      .catch(() => active && setError('Something went wrong loading this data. Please try again.'))
    return () => {
      active = false
    }
  }, [config])

  return (
    <div>
      <AdminPageHeader title={config.title} description={config.description} />
      {error && <EmptyState title="Couldn't load this list" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? <GenericTable columns={config.columns} rows={rows} /> : <EmptyState title="Nothing here yet" description={config.emptyMessage} />
      )}
    </div>
  )
}

export default function AdminGenericList({ section }) {
  if (section === 'newsletter') return <NewsletterSection />
  if (section === 'seo') return <SeoSection />

  const config = CONFIGS[section]
  if (!config) return null

  return <ConfiguredSection config={config} />
}
