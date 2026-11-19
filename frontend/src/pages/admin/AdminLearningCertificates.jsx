import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchAdminCertificates, reissueCertificate, revokeCertificate } from '../../api/certificates'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const STATUS_FILTERS = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'Valid' },
  { value: 'revoked', label: 'Revoked' },
]

// Certificates are issued automatically on completion (never here). Staff
// may only revoke, or revoke and reissue to correct an error. The issued
// snapshot is never edited, so verification history stays honest.
export default function AdminLearningCertificates() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [refresh, setRefresh] = useState(0)
  const [action, setAction] = useState(null) // {kind, certificate}
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    fetchAdminCertificates({ q: query, status, page, perPage: 25 })
      .then((res) => {
        if (!active) return
        setResult(res)
        setError(null)
      })
      .catch(() => active && setError('Something went wrong loading certificates. Please try again.'))
    return () => {
      active = false
    }
  }, [query, status, page, refresh])

  async function submitAction(event) {
    event.preventDefault()
    if (!reason.trim()) return
    setBusy(true)
    try {
      if (action.kind === 'revoke') {
        await revokeCertificate(action.certificate.id, reason.trim())
        toast.success('Certificate revoked.')
      } else {
        const fresh = await reissueCertificate(action.certificate.id, reason.trim())
        toast.success(`Reissued as ${fresh.certificateNumber}.`)
      }
      setAction(null)
      setReason('')
      setRefresh((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Certificates"
        description="Certificates of Completion issued automatically when learners complete certificate-enabled WSF programs."
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input
            value={query}
            onChange={(e) => {
              setPage(1)
              setQuery(e.target.value)
            }}
            placeholder="Search name, email, number or program…"
            className="w-72 text-sm focus:outline-none"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setPage(1)
            setStatus(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {action && (
        <form onSubmit={submitAction} className="mb-6 border border-taupe-300 bg-cream p-4 text-sm">
          <p className="font-semibold text-charcoal">
            {action.kind === 'revoke' ? 'Revoke' : 'Revoke and reissue'} {action.certificate.certificateNumber}
          </p>
          <p className="mt-1 text-charcoal-600">
            {action.kind === 'revoke'
              ? 'The certificate stays on record and its verification page will show it as revoked. This cannot be undone.'
              : 'The existing certificate will remain in history as revoked and a replacement will be issued, using the learner’s current name and the program’s current details.'}
          </p>
          <label className="mt-3 block">
            <span className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Reason (required)</span>
            <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} autoFocus className="mt-1 w-full border border-taupe-300 bg-white px-3 py-2" />
          </label>
          <div className="mt-3 flex gap-3">
            <button type="submit" disabled={busy || !reason.trim()} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
              {action.kind === 'revoke' ? 'Revoke certificate' : 'Revoke and reissue'}
            </button>
            <button type="button" onClick={() => setAction(null)} className="btn-secondary !px-4 !py-2 text-xs">
              Cancel
            </button>
          </div>
        </form>
      )}

      {error && <EmptyState title="Couldn't load certificates" description={error} />}
      {!error && result === null && <PageLoader />}
      {!error && result !== null && (
        result.items.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Number</th>
                  <th className="px-4 py-3">Recipient</th>
                  <th className="px-4 py-3">Program</th>
                  <th className="px-4 py-3">Issued</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {result.items.map((c) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3 font-mono text-xs text-charcoal">{c.certificateNumber}</td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-charcoal">{c.recipientName}</p>
                      <p className="text-xs text-charcoal-600">{c.learnerEmail || '—'}</p>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{c.programTitle}</td>
                    <td className="px-4 py-3 text-charcoal-600">{c.issuedAt ? formatDate(c.issuedAt) : '—'}</td>
                    <td className="px-4 py-3">
                      {c.status === 'revoked' ? (
                        <span className="text-xs font-semibold text-rose-600" title={c.revocationReason || ''}>
                          Revoked{c.revokedAt ? ` ${formatDate(c.revokedAt)}` : ''}
                        </span>
                      ) : (
                        <span className="text-xs font-semibold text-emerald-700">Valid</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      <div className="flex flex-wrap gap-3">
                        <Link to={`/certificates/verify/${c.publicId}`} target="_blank" className="font-semibold text-burgundy-600 hover:underline">
                          View
                        </Link>
                        {c.status === 'active' && (
                          <>
                            <button type="button" onClick={() => { setReason(''); setAction({ kind: 'revoke', certificate: c }) }} className="font-semibold text-charcoal-600 hover:text-burgundy-600">
                              Revoke
                            </button>
                            <button type="button" onClick={() => { setReason(''); setAction({ kind: 'reissue', certificate: c }) }} className="font-semibold text-charcoal-600 hover:text-burgundy-600">
                              Reissue
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No certificates yet" description="Certificates appear here once learners complete certificate-enabled programs." />
        )
      )}

      {result?.pagination && result.pagination.totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-4">
          <button type="button" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60">
            Previous
          </button>
          <span className="text-sm text-charcoal-600">
            Page {result.pagination.page} of {result.pagination.totalPages}
          </span>
          <button
            type="button"
            disabled={page >= result.pagination.totalPages}
            onClick={() => setPage((p) => Math.min(result.pagination.totalPages, p + 1))}
            className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
