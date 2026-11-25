import { useId, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import useSeo from '../hooks/useSeo'
import { downloadAccountExport, requestAccountDeletion, submitPrivacyRequest } from '../api/accountPrivacy'
import { resendEmailVerification } from '../api/auth'
import { logout } from '../features/auth/authSlice'
import CommentDialog from '../components/comments/CommentDialog'

// Account -> Privacy & data (Step 16): download your data (JSON), delete
// your account (14-day grace period), and other privacy requests. The
// server enforces everything; this page only explains and asks.
export default function AccountPrivacyPage() {
  useSeo({ title: 'Privacy & data | Women Shaping Futures', robots: 'noindex, nofollow' })
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const ids = useId()
  const [exporting, setExporting] = useState(false)
  const [exportMessage, setExportMessage] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [removeComments, setRemoveComments] = useState(false)
  const [deleteError, setDeleteError] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [requestType, setRequestType] = useState('access')
  const [details, setDetails] = useState('')
  const [requestMessage, setRequestMessage] = useState('')
  const user = useSelector((st) => st.auth.user)
  const [verifyMessage, setVerifyMessage] = useState('')

  async function handleVerify() {
    const res = await resendEmailVerification()
    setVerifyMessage(res.success ? 'We’ve emailed you a confirmation link. It works once, for 24 hours.' : res.message)
  }

  async function handleExport() {
    setExporting(true)
    const res = await downloadAccountExport()
    setExporting(false)
    setExportMessage(res.success ? 'Your data file has downloaded.' : res.message)
  }

  async function handleDelete(e) {
    e.preventDefault()
    setDeleting(true)
    setDeleteError(null)
    const res = await requestAccountDeletion({ password, removeComments })
    setDeleting(false)
    if (!res.success) return setDeleteError(res.message)
    setConfirmOpen(false)
    dispatch(logout())
    const when = new Date(res.scheduledFor).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
    toast.success(`Your account will be deleted on ${when}. We've emailed you a link in case you change your mind.`)
    navigate('/', { replace: true })
    return undefined
  }

  async function handleRequest(e) {
    e.preventDefault()
    const res = await submitPrivacyRequest({ requestType, details })
    setRequestMessage(res.success ? 'Thanks. We aim to reply within 30 days.' : res.message)
    if (res.success) setDetails('')
  }

  const label = 'text-xs font-semibold uppercase tracking-wide text-charcoal-600'
  const field = 'mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

  return (
    <div className="max-w-[720px] space-y-12">
      {user && !user.emailVerified && (
        <section aria-labelledby={`${ids}-verify`} className="border border-taupe-200 bg-white p-4">
          <h2 id={`${ids}-verify`} className="font-serif text-xl font-semibold text-charcoal">Confirm your email address</h2>
          <p className="mt-2 text-sm text-charcoal-600">
            Until you confirm it, newsletter and story records sent from {user.email} aren’t included in your data file or
            deleted with your account, because we can’t be sure they’re yours.
          </p>
          <button type="button" onClick={handleVerify} className="btn-secondary mt-3">Send me a confirmation link</button>
          <p role="status" aria-live="polite" className="mt-2 text-sm text-charcoal-600">{verifyMessage}</p>
        </section>
      )}

      <section aria-labelledby={`${ids}-export`}>
        <h2 id={`${ids}-export`} className="font-serif text-2xl font-semibold text-charcoal">Download your data</h2>
        <p className="mt-2 text-sm text-charcoal-600">
          A file (JSON) with your account details, preferences, saved items, registrations, learning, purchases and payment
          records, comments, newsletter and cookie choices. Passwords and other security data are never included.
        </p>
        <p className="mt-2 text-sm text-charcoal-600">
          Nominations, contact enquiries and mentorship applications are kept separately from your account and aren’t in
          this file. To see or delete them, send a privacy request below; we check it’s really you first.
        </p>
        <button type="button" onClick={handleExport} disabled={exporting} className="btn-primary mt-4 disabled:opacity-60">
          {exporting ? 'Preparing…' : 'Download my data'}
        </button>
        <p role="status" aria-live="polite" className="mt-2 text-sm text-charcoal-600">{exportMessage}</p>
      </section>

      <section aria-labelledby={`${ids}-delete`}>
        <h2 id={`${ids}-delete`} className="font-serif text-2xl font-semibold text-charcoal">Delete your account</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-charcoal-600">
          <li>You’ll be signed out everywhere straight away and can’t use the account while deletion is pending.</li>
          <li>The account is permanently deleted after 14 days. Until then you can cancel by signing in or with the link we email you.</li>
          <li>Your published comments stay as “Former member” unless you choose to remove them below.</li>
          <li>Payment records are kept for 6 years, without the link to your account. Stories already published stay, with your name removed from our records.</li>
          <li>Your WSF Weekly subscription is separate: unsubscribe with the link in any newsletter.</li>
          <li>
            Your certificates are deleted with the account and their verification links stop working.{' '}
            <Link to="/account/learning" className="font-semibold text-burgundy-600 hover:underline">Download them first</Link> from My Certificates.
          </li>
        </ul>
        <button type="button" onClick={() => { setDeleteError(null); setConfirmOpen(true) }} className="btn-secondary mt-4">
          Delete my account…
        </button>
      </section>

      <section aria-labelledby={`${ids}-request`}>
        <h2 id={`${ids}-request`} className="font-serif text-2xl font-semibold text-charcoal">Other privacy requests</h2>
        <p className="mt-2 text-sm text-charcoal-600">
          Ask us about your data or to correct it. See our <Link to="/privacy" className="font-semibold text-burgundy-600 hover:underline">Privacy Policy</Link>.
        </p>
        <form onSubmit={handleRequest} className="mt-4 space-y-3">
          <div>
            <label htmlFor={`${ids}-type`} className={label}>Request</label>
            <select id={`${ids}-type`} value={requestType} onChange={(e) => setRequestType(e.target.value)} className={field}>
              <option value="access">A copy of my data / a question about it</option>
              <option value="correction">Correct something</option>
              <option value="other">Something else</option>
            </select>
          </div>
          <div>
            <label htmlFor={`${ids}-details`} className={label}>Details</label>
            <textarea id={`${ids}-details`} required maxLength={2000} rows={4} value={details} onChange={(e) => setDetails(e.target.value)} className={field} />
          </div>
          <button type="submit" className="btn-primary">Send request</button>
          <p role="status" aria-live="polite" className="text-sm text-charcoal-600">{requestMessage}</p>
        </form>
      </section>

      <CommentDialog open={confirmOpen} titleId={`${ids}-confirm`} title="Delete your account?" onClose={() => setConfirmOpen(false)}>
        <form onSubmit={handleDelete} className="space-y-3">
          <p className="text-sm text-charcoal-600">
            It will be permanently deleted in 14 days. You can cancel until then. Your certificates and their verification
            links will stop working, so download any you want to keep first.
          </p>
          <label className="flex items-start gap-2 text-sm text-charcoal">
            <input type="checkbox" checked={removeComments} onChange={(e) => setRemoveComments(e.target.checked)} className="mt-1" />
            Also remove my comments (their text is erased; replies from others stay)
          </label>
          <div>
            <label htmlFor={`${ids}-password`} className={label}>Your password</label>
            <input id={`${ids}-password`} type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className={field} />
          </div>
          {deleteError && <p role="alert" className="text-sm text-rose-700">{deleteError}</p>}
          <div className="flex justify-end gap-3">
            <button type="button" className="text-xs font-semibold text-charcoal-600 hover:underline" onClick={() => setConfirmOpen(false)}>Keep my account</button>
            <button type="submit" disabled={deleting || !password} className="btn-primary disabled:opacity-60">
              {deleting ? 'Scheduling…' : 'Delete my account'}
            </button>
          </div>
        </form>
      </CommentDialog>
    </div>
  )
}
