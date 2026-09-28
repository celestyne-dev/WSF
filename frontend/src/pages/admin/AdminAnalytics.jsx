import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import {
  LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'
import { Download } from 'lucide-react'
import {
  fetchAnalyticsOverview, fetchAnalyticsContent, fetchAnalyticsSearch, fetchAnalyticsNewsletter,
  fetchAnalyticsCareers, fetchAnalyticsCommunityPrograms, fetchAnalyticsCommercial,
  exportAnalyticsContent, exportAnalyticsSearch, exportAnalyticsSponsors,
} from '../../api/analytics'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

// Shared by every "Export CSV" button — a 403 (missing analytics.export/
// .commercial) surfaces as a clear message, never a raw unhandled
// promise rejection in the console.
function handleExport(exportFn) {
  exportFn().catch((err) => {
    const message =
      err?.response?.status === 403
        ? "You don't have permission to export this report."
        : 'Something went wrong exporting this report. Please try again.'
    toast.error(message)
  })
}

const COLORS = ['#7A2438', '#5B3A4E', '#C98A85', '#9C8C79', '#3E5C50']

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'content', label: 'Content' },
  { key: 'search', label: 'Search' },
  { key: 'newsletter', label: 'Newsletter' },
  { key: 'careers', label: 'Careers & Opportunities' },
  { key: 'programs', label: 'Community & Programs' },
  { key: 'commercial', label: 'Commercial' },
]

const QUICK_RANGES = [
  { key: '7', label: 'Last 7 days', days: 7 },
  { key: '30', label: 'Last 30 days', days: 30 },
  { key: '90', label: 'Last 90 days', days: 90 },
]

function isoDate(d) {
  return d.toISOString().slice(0, 10)
}

function defaultRange(days = 30) {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - (days - 1))
  return { start: isoDate(start), end: isoDate(end) }
}

function numberFormat(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('en-US').format(n)
}

function abbreviate(n) {
  if (n == null) return '—'
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

function KpiCard({ label, value, change }) {
  return (
    <div className="border border-taupe-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</p>
      <p className="mt-2 font-serif text-2xl font-semibold text-charcoal" title={numberFormat(value)}>
        {abbreviate(value)}
      </p>
      {change != null && (
        <p className={`mt-1 text-xs font-semibold ${change >= 0 ? 'text-emerald-700' : 'text-burgundy-600'}`}>
          {change >= 0 ? '+' : ''}
          {change}% vs previous period
        </p>
      )}
    </div>
  )
}

function ChartEmpty() {
  return <p className="flex h-full items-center justify-center text-sm text-charcoal-600">No data for this period.</p>
}

export default function AdminAnalytics() {
  const [tab, setTab] = useState('overview')
  const [range, setRange] = useState(defaultRange(30))
  const [activeQuickRange, setActiveQuickRange] = useState('30')

  const [overview, setOverview] = useState(undefined)
  const [content, setContent] = useState(undefined)
  const [search, setSearchData] = useState(undefined)
  const [newsletter, setNewsletter] = useState(undefined)
  const [careers, setCareers] = useState(undefined)
  const [programs, setPrograms] = useState(undefined)
  const [commercial, setCommercial] = useState(undefined)
  const [commercialDenied, setCommercialDenied] = useState(false)
  const [error, setError] = useState(null)

  const loadTab = useCallback(
    (key) => {
      setError(null)
      const r = { ...range, compare: true }
      if (key === 'overview' && overview === undefined) {
        fetchAnalyticsOverview(r).then(setOverview).catch(() => setError('Something went wrong loading analytics. Please try again.'))
      } else if (key === 'content' && content === undefined) {
        fetchAnalyticsContent(range).then(setContent).catch(() => setError('Something went wrong loading analytics. Please try again.'))
      } else if (key === 'search' && search === undefined) {
        fetchAnalyticsSearch(range).then(setSearchData).catch(() => setError('Something went wrong loading analytics. Please try again.'))
      } else if (key === 'newsletter' && newsletter === undefined) {
        fetchAnalyticsNewsletter(range).then(setNewsletter).catch(() => setError('Something went wrong loading analytics. Please try again.'))
      } else if (key === 'careers' && careers === undefined) {
        fetchAnalyticsCareers(range).then(setCareers).catch(() => setError('Something went wrong loading analytics. Please try again.'))
      } else if (key === 'programs' && programs === undefined) {
        fetchAnalyticsCommunityPrograms(range).then(setPrograms).catch(() => setError('Something went wrong loading analytics. Please try again.'))
      } else if (key === 'commercial' && commercial === undefined && !commercialDenied) {
        fetchAnalyticsCommercial(range)
          .then(setCommercial)
          .catch((err) => {
            if (err.response?.status === 403) setCommercialDenied(true)
            else setError('Something went wrong loading analytics. Please try again.')
          })
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [range],
  )

  // Reset every tab's cached data when the date range changes, then
  // re-fetch whichever tab is currently open.
  useEffect(() => {
    setOverview(undefined)
    setContent(undefined)
    setSearchData(undefined)
    setNewsletter(undefined)
    setCareers(undefined)
    setPrograms(undefined)
    setCommercial(undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.start, range.end])

  useEffect(() => {
    loadTab(tab)
  }, [tab, loadTab])

  function applyQuickRange(q) {
    setActiveQuickRange(q.key)
    setRange(defaultRange(q.days))
  }

  function applyCustomRange(field, value) {
    setActiveQuickRange(null)
    setRange((r) => ({ ...r, [field]: value }))
  }

  return (
    <div>
      <AdminPageHeader
        title="Analytics"
        description="Real first-party analytics from tracked events and platform data — no third-party integrations, no fabricated metrics."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {QUICK_RANGES.map((q) => (
              <button
                key={q.key}
                type="button"
                onClick={() => applyQuickRange(q)}
                className={`px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                  activeQuickRange === q.key ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600 hover:bg-taupe-200'
                }`}
              >
                {q.label}
              </button>
            ))}
            <label className="flex items-center gap-1 text-xs text-charcoal-600">
              From
              <input
                type="date"
                value={range.start}
                max={range.end}
                onChange={(e) => applyCustomRange('start', e.target.value)}
                className="border border-taupe-300 px-2 py-1"
              />
            </label>
            <label className="flex items-center gap-1 text-xs text-charcoal-600">
              To
              <input
                type="date"
                value={range.end}
                min={range.start}
                max={isoDate(new Date())}
                onChange={(e) => applyCustomRange('end', e.target.value)}
                className="border border-taupe-300 px-2 py-1"
              />
            </label>
          </div>
        }
      />

      <div className="mb-6 flex flex-wrap gap-2 border-b border-taupe-200" role="tablist" aria-label="Analytics sections">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide transition-colors ${
              tab === t.key ? 'border-b-2 border-plum-600 text-plum-600' : 'text-charcoal-600 hover:text-charcoal'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <EmptyState title="Couldn't load analytics" description={error} />}

      {!error && tab === 'overview' && <OverviewTab data={overview} />}
      {!error && tab === 'content' && <ContentTab data={content} range={range} />}
      {!error && tab === 'search' && <SearchTab data={search} range={range} />}
      {!error && tab === 'newsletter' && <NewsletterTab data={newsletter} />}
      {!error && tab === 'careers' && <CareersTab data={careers} />}
      {!error && tab === 'programs' && <ProgramsTab data={programs} />}
      {!error && tab === 'commercial' && <CommercialTab data={commercial} denied={commercialDenied} range={range} />}
    </div>
  )
}

function OverviewTab({ data }) {
  if (data === undefined) return <PageLoader />
  const { metrics, comparison, audienceBySource, trend } = data
  const changes = comparison?.changes || {}
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="Content views" value={metrics.contentViews} change={changes.contentViews} />
        <KpiCard label="Article views" value={metrics.articleViews} change={changes.articleViews} />
        <KpiCard label="Searches performed" value={metrics.searchesPerformed} change={changes.searchesPerformed} />
        <KpiCard label="Newsletter signups" value={metrics.newsletterSignups} change={changes.newsletterSignups} />
        <KpiCard label="Job views" value={metrics.jobViews} change={changes.jobViews} />
        <KpiCard label="Opportunity views" value={metrics.opportunityViews} change={changes.opportunityViews} />
        <KpiCard label="Event views" value={metrics.eventViews} change={changes.eventViews} />
        <KpiCard label="Resource downloads" value={metrics.resourceDownloads} change={changes.resourceDownloads} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="border border-taupe-200 bg-white p-5 lg:col-span-2">
          <p className="text-sm font-semibold text-charcoal">Content activity trend</p>
          <div className="mt-4 h-64">
            {trend.points.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend.points}>
                  <CartesianGrid stroke="#EDE7DE" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v) => numberFormat(v)} />
                  <Legend />
                  <Line type="monotone" dataKey="contentViews" name="Content views" stroke="#7A2438" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="articleViews" name="Article views" stroke="#5B3A4E" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <ChartEmpty />
            )}
          </div>
        </div>

        <div className="border border-taupe-200 bg-white p-5 lg:col-span-2">
          <p className="text-sm font-semibold text-charcoal">Audience by source</p>
          <div className="mt-4 h-64">
            {audienceBySource.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={audienceBySource} dataKey="count" nameKey="source" innerRadius={55} outerRadius={85} paddingAngle={2}>
                    {audienceBySource.map((entry, i) => (
                      <Cell key={entry.source} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <ChartEmpty />
            )}
          </div>
          <table className="mt-4 w-full text-sm">
            <caption className="sr-only">Audience by source, exact counts</caption>
            <tbody>
              {audienceBySource.map((row) => (
                <tr key={row.source} className="border-t border-taupe-100">
                  <td className="py-1 capitalize">{row.source}</td>
                  <td className="py-1 text-right">{numberFormat(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function ContentTab({ data, range }) {
  if (data === undefined) return <PageLoader />
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-charcoal-600">{numberFormat(data.totalViews)} article views across {numberFormat(data.totalArticles)} articles in this period.</p>
        <button
          type="button"
          onClick={() => handleExport(() => exportAnalyticsContent(range))}
          className="btn-secondary !px-3 !py-1.5 text-xs inline-flex items-center gap-1.5"
        >
          <Download size={14} /> Export CSV
        </button>
      </div>

      <div className="overflow-x-auto border border-taupe-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-taupe-200 text-left text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              <th className="px-4 py-3">Article</th>
              <th className="px-4 py-3">Topic</th>
              <th className="px-4 py-3">Published</th>
              <th className="px-4 py-3 text-right">Views</th>
            </tr>
          </thead>
          <tbody>
            {data.results.length ? (
              data.results.map((row) => (
                <tr key={row.slug} className="border-b border-taupe-100 last:border-0">
                  <td className="px-4 py-3">
                    {row.url ? (
                      <Link to={row.url} className="text-charcoal hover:text-burgundy-600" target="_blank" rel="noreferrer">
                        {row.title}
                      </Link>
                    ) : (
                      <span className="text-charcoal-600">{row.title}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-charcoal-600">{row.topic || '—'}</td>
                  <td className="px-4 py-3 text-charcoal-600">{row.publishedDate ? new Date(row.publishedDate).toLocaleDateString() : '—'}</td>
                  <td className="px-4 py-3 text-right font-semibold">{numberFormat(row.views)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-charcoal-600">No article views recorded for this period.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {(data.topics.length > 0 || data.series.length > 0) && (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-sm font-semibold text-charcoal">Views by Topic (current taxonomy)</p>
            <table className="mt-3 w-full text-sm">
              <tbody>
                {data.topics.map((row) => (
                  <tr key={row.topic} className="border-t border-taupe-100">
                    <td className="py-1.5">{row.topic}</td>
                    <td className="py-1.5 text-right">{numberFormat(row.views)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.series.length > 0 && (
            <div className="border border-taupe-200 bg-white p-5">
              <p className="text-sm font-semibold text-charcoal">Views by Series (current taxonomy)</p>
              <table className="mt-3 w-full text-sm">
                <tbody>
                  {data.series.map((row) => (
                    <tr key={row.series} className="border-t border-taupe-100">
                      <td className="py-1.5">{row.series}</td>
                      <td className="py-1.5 text-right">{numberFormat(row.views)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SearchTab({ data, range }) {
  if (data === undefined) return <PageLoader />
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <KpiCard label="Total searches" value={data.totalSearches} />
        <KpiCard label="Zero-result searches" value={data.zeroResultSearches} />
        <KpiCard label="Result clicks" value={data.resultClicks} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="border border-taupe-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-charcoal">Top search queries</p>
            <button type="button" onClick={() => handleExport(() => exportAnalyticsSearch(range))} className="btn-secondary !px-3 !py-1.5 text-xs inline-flex items-center gap-1.5">
              <Download size={14} /> Export CSV
            </button>
          </div>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <th className="py-1.5">Query</th>
                <th className="py-1.5 text-right">Searches</th>
                <th className="py-1.5 text-right">Last searched</th>
              </tr>
            </thead>
            <tbody>
              {data.topQueries.length ? (
                data.topQueries.map((row) => (
                  <tr key={row.query} className="border-t border-taupe-100">
                    <td className="py-1.5">{row.query}</td>
                    <td className="py-1.5 text-right">{numberFormat(row.count)}</td>
                    <td className="py-1.5 text-right text-charcoal-600">{row.lastSearched ? new Date(row.lastSearched).toLocaleDateString() : '—'}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3} className="py-6 text-center text-charcoal-600">No searches recorded for this period.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="border border-taupe-200 bg-white p-5">
          <p className="text-sm font-semibold text-charcoal">Result clicks by type</p>
          <table className="mt-3 w-full text-sm">
            <tbody>
              {data.clicksByResultType.length ? (
                data.clicksByResultType.map((row) => (
                  <tr key={row.resultType} className="border-t border-taupe-100">
                    <td className="py-1.5 capitalize">{row.resultType}</td>
                    <td className="py-1.5 text-right">{numberFormat(row.count)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="py-6 text-center text-charcoal-600">No result clicks recorded for this period.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function NewsletterTab({ data }) {
  if (data === undefined) return <PageLoader />
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="New subscribers" value={data.newSubscribers} />
        <KpiCard label="Unsubscribes" value={data.unsubscribes} />
        <KpiCard label="Active subscribers" value={data.activeTotal} />
        <KpiCard label="Issue views" value={data.issueViews} />
      </div>
      <div className="border border-taupe-200 bg-white p-5">
        <p className="text-sm font-semibold text-charcoal">Subscriber growth</p>
        <div className="mt-4 h-56">
          {data.growthTrend.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.growthTrend}>
                <CartesianGrid stroke="#EDE7DE" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => numberFormat(v)} />
                <Line type="monotone" dataKey="newSubscribers" name="New subscribers" stroke="#5B3A4E" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <ChartEmpty />
          )}
        </div>
      </div>
    </div>
  )
}

function EngagementSection({ title, views, clicksLabel, clicks, topRows, topLabel = 'Views' }) {
  return (
    <div className="border border-taupe-200 bg-white p-5">
      <p className="text-sm font-semibold text-charcoal">{title}</p>
      <div className="mt-3 grid grid-cols-2 gap-4">
        <KpiCard label="Views" value={views} />
        <KpiCard label={clicksLabel} value={clicks} />
      </div>
      {topRows.length > 0 && (
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              <th className="py-1.5">Title</th>
              <th className="py-1.5 text-right">{topLabel}</th>
            </tr>
          </thead>
          <tbody>
            {topRows.map((row) => (
              <tr key={row.slug} className="border-t border-taupe-100">
                <td className="py-1.5">
                  {row.url ? (
                    <Link to={row.url} className="text-charcoal hover:text-burgundy-600" target="_blank" rel="noreferrer">
                      {row.title}
                    </Link>
                  ) : (
                    row.title
                  )}
                </td>
                <td className="py-1.5 text-right">{numberFormat(row.views)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function CareersTab({ data }) {
  if (data === undefined) return <PageLoader />
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <EngagementSection title="Jobs" views={data.jobs.views} clicksLabel="Apply-link clicks" clicks={data.jobs.applyClicks} topRows={data.jobs.topJobs} />
      <EngagementSection
        title="Opportunities"
        views={data.opportunities.views}
        clicksLabel="Apply-link clicks"
        clicks={data.opportunities.applyClicks}
        topRows={data.opportunities.topOpportunities}
      />
      <EngagementSection
        title="Events"
        views={data.events.views}
        clicksLabel="Registration-link clicks"
        clicks={data.events.registrationClicks}
        topRows={data.events.topEvents}
      />
      <EngagementSection title="Resources" views={data.resources.views} clicksLabel="Real downloads" clicks={data.resources.downloads} topRows={data.resources.topResources} />
    </div>
  )
}

function ProgramsTab({ data }) {
  if (data === undefined) return <PageLoader />
  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
      <div className="border border-taupe-200 bg-white p-5">
        <p className="text-sm font-semibold text-charcoal">Community</p>
        <div className="mt-3 grid grid-cols-3 gap-3">
          <KpiCard label="New joins" value={data.community.joins} />
          <KpiCard label="Active members" value={data.community.activeMembers} />
          <KpiCard label="Countries represented" value={data.community.countriesRepresented} />
        </div>
      </div>
      <div className="border border-taupe-200 bg-white p-5">
        <p className="text-sm font-semibold text-charcoal">Mentorship</p>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <KpiCard label="Mentor applications" value={data.mentorship.mentorApplications} />
          <KpiCard label="Mentee applications" value={data.mentorship.menteeApplications} />
          <KpiCard label="Active matches" value={data.mentorship.activeMatches} />
          <KpiCard label="Completed matches" value={data.mentorship.completedMatches} />
        </div>
      </div>
      <div className="border border-taupe-200 bg-white p-5">
        <p className="text-sm font-semibold text-charcoal">Story Submissions</p>
        <div className="mt-3 grid grid-cols-3 gap-3">
          <KpiCard label="Received" value={data.storySubmissions.received} />
          <KpiCard label="Approved" value={data.storySubmissions.approved} />
          <KpiCard label="Published" value={data.storySubmissions.published} />
        </div>
      </div>
      <div className="border border-taupe-200 bg-white p-5">
        <p className="text-sm font-semibold text-charcoal">Nominations</p>
        <div className="mt-3 grid grid-cols-3 gap-3">
          <KpiCard label="Received" value={data.nominations.received} />
          <KpiCard label="Shortlisted" value={data.nominations.shortlisted} />
          <KpiCard label="Converted to editorial" value={data.nominations.converted} />
        </div>
      </div>
    </div>
  )
}

function CommercialTab({ data, denied, range }) {
  if (denied) {
    return <EmptyState title="Not authorized" description="Commercial analytics (Sponsors, Advertise, Partnerships, Orders) requires the Commercial Analytics permission." />
  }
  if (data === undefined) return <PageLoader />
  return (
    <div className="space-y-6">
      <div className="border border-taupe-200 bg-white p-5">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-charcoal">Sponsor performance</p>
          <button type="button" onClick={() => handleExport(() => exportAnalyticsSponsors(range))} className="btn-secondary !px-3 !py-1.5 text-xs inline-flex items-center gap-1.5">
            <Download size={14} /> Export CSV
          </button>
        </div>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              <th className="py-1.5">Sponsor</th>
              <th className="py-1.5 text-right">Impressions</th>
              <th className="py-1.5 text-right">Clicks</th>
              <th className="py-1.5 text-right">CTR</th>
            </tr>
          </thead>
          <tbody>
            {data.sponsors.length ? (
              data.sponsors.map((row, i) => (
                <tr key={`${row.sponsor}-${i}`} className="border-t border-taupe-100">
                  <td className="py-1.5">{row.sponsor}</td>
                  <td className="py-1.5 text-right">{numberFormat(row.impressions)}</td>
                  <td className="py-1.5 text-right">{numberFormat(row.clicks)}</td>
                  <td className="py-1.5 text-right">{row.ctr != null ? `${row.ctr}%` : '—'}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="py-6 text-center text-charcoal-600">No sponsor impressions/clicks recorded for this period.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="border border-taupe-200 bg-white p-5">
          <p className="text-sm font-semibold text-charcoal">Advertise / Media Kit</p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <KpiCard label="Page views" value={data.advertise.pageViews} />
            <KpiCard label="Media kit downloads" value={data.advertise.mediaKitDownloads} />
            <KpiCard label="Inquiries submitted" value={data.advertise.inquirySubmissions} />
            <KpiCard label="Offering clicks" value={data.advertise.offeringClicks} />
          </div>
        </div>
        <div className="border border-taupe-200 bg-white p-5">
          <p className="text-sm font-semibold text-charcoal">Partnerships</p>
          <table className="mt-3 w-full text-sm">
            <tbody>
              {data.partnerships.byStatus.map((row) => (
                <tr key={row.status} className="border-t border-taupe-100">
                  <td className="py-1.5 capitalize">{row.status}</td>
                  <td className="py-1.5 text-right">{numberFormat(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border border-taupe-200 bg-white p-5">
        <p className="text-sm font-semibold text-charcoal">Completed order revenue (by currency)</p>
        <p className="mt-1 text-xs text-charcoal-600">Multiple currencies are never summed together without a real exchange rate.</p>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              <th className="py-1.5">Currency</th>
              <th className="py-1.5 text-right">Completed orders</th>
              <th className="py-1.5 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.orders.byCurrency.length ? (
              data.orders.byCurrency.map((row) => (
                <tr key={row.currency} className="border-t border-taupe-100">
                  <td className="py-1.5">{row.currency}</td>
                  <td className="py-1.5 text-right">{numberFormat(row.completedCount)}</td>
                  <td className="py-1.5 text-right">
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: row.currency }).format(row.completedTotal)}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3} className="py-6 text-center text-charcoal-600">No completed orders in this period.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
