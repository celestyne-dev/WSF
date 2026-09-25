import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, AlertTriangle } from 'lucide-react'
import { fetchNominationsList } from '../../api/nominations'
import { fetchCountries } from '../../api/geography'
import { fetchTopics, fetchSeries } from '../../api/taxonomies'
import { fetchAdminUsers } from '../../api/admin'
import { NOMINATION_STATUSES, VERIFICATION_STATES } from '../../constants/nominations'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

export default function AdminNominations() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [country, setCountry] = useState('')
  const [topic, setTopic] = useState('')
  const [seriesId, setSeriesId] = useState('')
  const [organization, setOrganization] = useState('')
  const [verificationState, setVerificationState] = useState('')
  const [assignedReviewerId, setAssignedReviewerId] = useState('')

  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [series, setSeries] = useState([])
  const [reviewers, setReviewers] = useState([])
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchCountries().then(setCountries).catch(() => {})
    fetchTopics().then(setTopics).catch(() => {})
    fetchSeries().then(setSeries).catch(() => {})
    fetchAdminUsers().then(setReviewers).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchNominationsList({
      q: query || undefined,
      status: status || undefined,
      country: country || undefined,
      topic: topic || undefined,
      seriesId: seriesId || undefined,
      organization: organization || undefined,
      verificationState: verificationState || undefined,
      assignedReviewerId: assignedReviewerId || undefined,
      pageSize: 100,
    })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading nominations. Please try again.'))
    return () => {
      active = false
    }
  }, [query, status, country, topic, seriesId, organization, verificationState, assignedReviewerId])

  return (
    <div>
      <AdminPageHeader title="Nominations" description="Nominations received from the public, awaiting editorial review." />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search reference, nominee, nominator…" className="w-64 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {NOMINATION_STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select value={country} onChange={(e) => setCountry(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All countries</option>
          {countries.map((c) => (
            <option key={c.code} value={c.code}>{c.name}</option>
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
        <input value={organization} onChange={(e) => setOrganization(e.target.value)} placeholder="Organization…" className="border border-taupe-300 bg-white px-3 py-2 text-sm" />
        <select value={verificationState} onChange={(e) => setVerificationState(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All verification states</option>
          {VERIFICATION_STATES.map((v) => (
            <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select value={assignedReviewerId} onChange={(e) => setAssignedReviewerId(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All reviewers</option>
          {reviewers.map((u) => (
            <option key={u.id} value={u.id}>{u.name}</option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load nominations" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[1080px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Reference</th>
                  <th className="px-4 py-3">Nominee</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Role / Organization</th>
                  <th className="px-4 py-3">Series</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Reviewer</th>
                  <th className="px-4 py-3">Submitted</th>
                  <th className="px-4 py-3">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/nominations/${row.id}`} className="hover:text-burgundy-600">
                        {row.reference || `#${row.id}`}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      <Link to={`/admin/nominations/${row.id}`} className="flex items-center gap-1.5 hover:text-burgundy-600">
                        {row.nomineeName}
                        {row.possibleDuplicate && (
                          <span title="Possible existing nominee — check related nominations">
                            <AlertTriangle size={13} className="text-amber-600" />
                          </span>
                        )}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.country?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{[row.professionalTitle, row.organizationName].filter(Boolean).join(' — ') || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.series?.name || '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.assignedReviewer?.fullName || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.submittedAt ? formatDate(row.submittedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.updatedAt ? formatDate(row.updatedAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No nominations match those filters" description="Try a different search term or clear your filters." />
        )
      )}
    </div>
  )
}
