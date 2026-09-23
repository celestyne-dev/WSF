import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Download } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchMembers, exportMembers } from '../../api/community'
import { fetchCountries } from '../../api/geography'
import { fetchTopics } from '../../api/taxonomies'
import { MEMBERSHIP_STATUSES, MEMBERSHIP_TYPES } from '../../constants/community'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

export default function AdminMembers() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [membershipType, setMembershipType] = useState('')
  const [country, setCountry] = useState('')
  const [interest, setInterest] = useState('')
  const [directoryOptIn, setDirectoryOptIn] = useState('')
  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [rows, setRows] = useState(undefined)
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    fetchCountries().then(setCountries).catch(() => {})
    fetchTopics().then(setTopics).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchMembers({
      q: query, status, membershipType, country, interest,
      directoryOptIn, pageSize: 100,
    })
      .then((res) => {
        if (!active) return
        setRows(res.items)
        setMeta(res.meta)
      })
      .catch(() => active && setError('Something went wrong loading members. Please try again.'))
    return () => {
      active = false
    }
  }, [query, status, membershipType, country, interest, directoryOptIn])

  async function handleExport() {
    setExporting(true)
    try {
      await exportMembers({ status: status || undefined })
    } catch (err) {
      const message =
        err?.response?.status === 403
          ? "You don't have permission to export members."
          : 'Something went wrong exporting members. Please try again.'
      toast.error(message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Members"
        description="Everyone who has joined the WSF community, and their current membership status."
        actions={
          <button type="button" onClick={handleExport} disabled={exporting} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
            <Download size={14} /> {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, email, organization…" className="w-64 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {MEMBERSHIP_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={membershipType} onChange={(e) => setMembershipType(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All membership types</option>
          {MEMBERSHIP_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select value={country} onChange={(e) => setCountry(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All countries</option>
          {countries.map((c) => (
            <option key={c.code} value={c.code}>{c.name}</option>
          ))}
        </select>
        <select value={interest} onChange={(e) => setInterest(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All interests</option>
          {topics.map((t) => (
            <option key={t.slug} value={t.slug}>{t.name}</option>
          ))}
        </select>
        <select value={directoryOptIn} onChange={(e) => setDirectoryOptIn(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">Directory: any</option>
          <option value="true">Directory: opted in</option>
          <option value="false">Directory: not opted in</option>
        </select>
      </div>

      {error && <EmptyState title="Couldn't load members" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Title / Organization</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Joined</th>
                  <th className="px-4 py-3">Directory</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/members/${row.id}`} className="hover:text-burgundy-600">
                        {row.fullName}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.email}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.country?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {[row.professionalTitle, row.organizationName].filter(Boolean).join(' at ') || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.membershipType}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.appliedAt ? formatDate(row.appliedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.directoryOptIn ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No members match those filters" description="Try a different search term or clear your filters." />
        )
      )}
      {meta && rows?.length > 0 && (
        <p className="mt-3 text-xs text-charcoal-600/60">{meta.total} member{meta.total === 1 ? '' : 's'} total.</p>
      )}
    </div>
  )
}
