import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Download } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchSubscribers, exportSubscribers, importSuppressions } from '../../api/newsletter'
import { SUBSCRIBER_STATUSES, SUBSCRIBER_STATUS_LABELS } from '../../constants/newsletter'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'


// External unsubscribe reconciliation: the CSV an external sending service
// gives you (any file with an "email" column, or one address per line).
function SuppressionImport({ onDone }) {
  const [provider, setProvider] = useState('')
  const [kind, setKind] = useState('unsubscribed')
  const [csv, setCsv] = useState('')
  const [filename, setFilename] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  async function readFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setFilename(file.name)
    setCsv(await file.text())
  }

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    try {
      const data = await importSuppressions({ provider, csv, filename, kind })
      setResult(data)
      setCsv('')
      onDone()
    } catch (err) {
      toast.error(err?.apiError?.message || 'The import failed. Please check the file.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="mb-5 border border-taupe-200 bg-white p-4">
      <summary className="cursor-pointer text-sm font-semibold text-charcoal">Import unsubscribes from a sending service</summary>
      <form onSubmit={submit} className="mt-3 space-y-3">
        <p className="text-xs text-charcoal-600">
          Addresses in the file are suppressed in WSF (never reactivated). Unknown addresses are recorded as unsubscribed so
          they can never be exported. Importing the same file twice changes nothing.
        </p>
        <div>
          <label htmlFor="sup-provider" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Service the list came from</label>
          <input id="sup-provider" required maxLength={100} value={provider} onChange={(e) => setProvider(e.target.value)} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm sm:w-80" />
          <label htmlFor="sup-kind" className="mt-3 block text-xs font-semibold uppercase tracking-wide text-charcoal-600">What the list contains</label>
          <select id="sup-kind" value={kind} onChange={(e) => setKind(e.target.value)} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm sm:w-80">
            <option value="unsubscribed">Unsubscribes</option>
            <option value="bounced">Hard bounces</option>
            <option value="complained">Spam complaints</option>
          </select>
        </div>
        <div>
          <label htmlFor="sup-file" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">CSV file</label>
          <input id="sup-file" type="file" accept=".csv,text/csv,text/plain" onChange={readFile} className="mt-1 block text-sm" />
        </div>
        <div>
          <label htmlFor="sup-text" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">…or paste addresses</label>
          <textarea id="sup-text" rows={4} value={csv} onChange={(e) => setCsv(e.target.value)} className="mt-1 w-full border border-taupe-300 px-3 py-2 font-mono text-xs" />
        </div>
        <button type="submit" disabled={busy || !provider.trim() || !csv.trim()} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
          {busy ? 'Importing…' : 'Import unsubscribes'}
        </button>
        {result && (
          <p role="status" className="text-xs text-charcoal">
            {result.rows} rows: {result.newlySuppressed} newly suppressed, {result.alreadySuppressed} already suppressed,
            {' '}{result.addedUnknown} unknown addresses recorded as unsubscribed, {result.invalid} invalid.
          </p>
        )}
      </form>
    </details>
  )
}

export default function AdminSubscribers() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setError(null)
    fetchSubscribers({ status, q: query, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading subscribers. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query, reload])

  async function handleExport() {
    setExporting(true)
    try {
      await exportSubscribers()
    } catch (err) {
      const message =
        err?.response?.status === 403
          ? "You don't have permission to export subscribers."
          : 'Something went wrong exporting subscribers. Please try again.'
      toast.error(message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Subscribers"
        description="WSF's master list for WSF Weekly. Only confirmed subscribers are ever exported for sending."
        actions={
          <button type="button" onClick={handleExport} disabled={exporting} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
            <Download size={14} /> {exporting ? 'Exporting…' : 'Export confirmed subscribers (CSV)'}
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search email or name…" className="w-64 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {SUBSCRIBER_STATUSES.map((s) => (
            <option key={s} value={s}>
              {SUBSCRIBER_STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </div>

      <SuppressionImport onDone={() => setReload((n) => n + 1)} />

      {error && <EmptyState title="Couldn't load subscribers" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Subscribed</th>
                  <th className="px-4 py-3">Unsubscribed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/newsletter/subscribers/${row.id}`} className="hover:text-burgundy-600">
                        {row.email}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{[row.firstName, row.lastName].filter(Boolean).join(' ') || '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                      <span className="ml-2 text-xs text-charcoal-600">{SUBSCRIBER_STATUS_LABELS[row.status]}</span>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.source || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.subscribedAt ? formatDate(row.subscribedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.unsubscribedAt ? formatDate(row.unsubscribedAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No subscribers match those filters" description="Try a different search term or clear your filters." />
        )
      )}
    </div>
  )
}
