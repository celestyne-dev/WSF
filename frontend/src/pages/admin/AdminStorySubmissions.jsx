import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { fetchSubmissions } from '../../api/submissions'
import { fetchCountries } from '../../api/geography'
import { fetchTopics, fetchSeries } from '../../api/taxonomies'
import { fetchAdminUsers } from '../../api/admin'
import { SUBMISSION_STATUSES, STORY_TYPES, STORY_TYPE_LABELS } from '../../constants/submissions'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

export default function AdminStorySubmissions() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [country, setCountry] = useState('')
  const [storyType, setStoryType] = useState('')
  const [topic, setTopic] = useState('')
  const [seriesId, setSeriesId] = useState('')
  const [assignedEditorId, setAssignedEditorId] = useState('')

  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [series, setSeries] = useState([])
  const [editors, setEditors] = useState([])
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchCountries().then(setCountries).catch(() => {})
    fetchTopics().then(setTopics).catch(() => {})
    fetchSeries().then(setSeries).catch(() => {})
    fetchAdminUsers().then(setEditors).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchSubmissions({
      q: query || undefined,
      status: status || undefined,
      country: country || undefined,
      storyType: storyType || undefined,
      topic: topic || undefined,
      seriesId: seriesId || undefined,
      assignedEditorId: assignedEditorId || undefined,
      pageSize: 100,
    })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading submissions. Please try again.'))
    return () => {
      active = false
    }
  }, [query, status, country, storyType, topic, seriesId, assignedEditorId])

  return (
    <div>
      <AdminPageHeader title="Story Submissions" description="Stories received from the public, awaiting editorial review." />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search reference, title, submitter, email…" className="w-64 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {SUBMISSION_STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select value={country} onChange={(e) => setCountry(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All countries</option>
          {countries.map((c) => (
            <option key={c.code} value={c.code}>{c.name}</option>
          ))}
        </select>
        <select value={storyType} onChange={(e) => setStoryType(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All story types</option>
          {STORY_TYPES.map((t) => (
            <option key={t} value={t}>{STORY_TYPE_LABELS[t]}</option>
          ))}
        </select>
        <select value={topic} onChange={(e) => setTopic(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All topics</option>
          {topics.map((t) => (
            <option key={t.slug} value={t.slug}>{t.name}</option>
          ))}
        </select>
        <select value={seriesId} onChange={(e) => setSeriesId(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All series</option>
          {series.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <select value={assignedEditorId} onChange={(e) => setAssignedEditorId(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All editors</option>
          {editors.map((u) => (
            <option key={u.id} value={u.id}>{u.name}</option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load submissions" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[1080px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Reference</th>
                  <th className="px-4 py-3">Story title</th>
                  <th className="px-4 py-3">Submitter</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Story type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Assigned editor</th>
                  <th className="px-4 py-3">Submitted</th>
                  <th className="px-4 py-3">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/submissions/${row.id}`} className="hover:text-burgundy-600">
                        {row.reference || `#${row.id}`}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      <Link to={`/admin/submissions/${row.id}`} className="hover:text-burgundy-600">{row.title}</Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.fullName}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.country?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.storyType ? STORY_TYPE_LABELS[row.storyType] || row.storyType : '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.assignedEditor?.fullName || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.submittedAt ? formatDate(row.submittedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.updatedAt ? formatDate(row.updatedAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No submissions match those filters" description="Try a different search term or clear your filters." />
        )
      )}
    </div>
  )
}
