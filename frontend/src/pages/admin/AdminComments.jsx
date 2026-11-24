import { useCallback, useEffect, useId, useState } from 'react'
import { Link } from 'react-router-dom'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import CommentDialog from '../../components/comments/CommentDialog'
import {
  fetchModerationComment, fetchModerationQueue, liftCommenterRestriction, moderateComment, restrictCommenter,
} from '../../api/comments'
import { HELD_REASON_LABELS, HISTORY_LABELS, MODERATION_QUEUES, STATUS_LABELS, restrictionMessage } from '../../utils/comments'
import { formatDate } from '../../utils/format'

// Studio -> Comments: moderation queue (permission "comments.moderate",
// backend app/api/v1/comments.py). Every action is re-checked server-side
// and written to the Audit Log. Status is always shown as text, never by
// colour alone.

const btn = 'border border-taupe-300 bg-white px-3 py-1.5 text-xs font-semibold text-charcoal hover:border-burgundy-500 ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-burgundy-500 disabled:opacity-50'
const field = 'w-full border border-taupe-300 px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-burgundy-500'

function StatusText({ status }) {
  return (
    <span className="inline-block border border-taupe-300 bg-taupe-100 px-2 py-0.5 text-xs font-semibold text-charcoal">
      {STATUS_LABELS[status] || status}
    </span>
  )
}

function Detail({ id, onChanged }) {
  const [item, setItem] = useState(null)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState('')
  const [dialog, setDialog] = useState(null) // remove | hide | suspend | ban
  const [reason, setReason] = useState('')
  const [days, setDays] = useState(7)
  const [dialogError, setDialogError] = useState(null)
  const base = useId()

  const load = useCallback(async () => {
    const res = await fetchModerationComment(id)
    if (res.success) setItem(res.data)
    else setError(res.message)
  }, [id])

  useEffect(() => {
    let active = true
    fetchModerationComment(id).then((res) => {
      if (!active) return
      if (res.success) setItem(res.data)
      else setError(res.message)
    })
    return () => {
      active = false
    }
  }, [id])

  async function act(action, actionReason) {
    const res = await moderateComment(id, action, actionReason)
    if (!res.success) return res
    setMessage(`Done: ${STATUS_LABELS[res.data.status] || res.data.status}.`)
    await load()
    onChanged()
    return res
  }

  async function submitDialog(e) {
    e.preventDefault()
    setDialogError(null)
    let res
    if (dialog === 'remove' || dialog === 'hide') {
      if (dialog === 'remove' && !reason.trim()) return setDialogError('A reason is required to remove a comment.')
      res = await act(dialog, reason)
    } else {
      res = await restrictCommenter(item.author.userId, { kind: dialog === 'ban' ? 'ban' : 'suspension',
        days: dialog === 'suspend' ? Number(days) : undefined, reason })
      if (res.success) {
        setMessage(dialog === 'ban' ? 'Member banned from comments.' : `Member suspended from comments for ${days} days.`)
        await load()
        onChanged()
      }
    }
    if (!res.success) return setDialogError(res.message)
    setDialog(null)
    setReason('')
    return undefined
  }

  async function lift() {
    const res = await liftCommenterRestriction(item.author.userId)
    setMessage(res.success ? 'Comment restriction lifted.' : res.message)
    await load()
    onChanged()
  }

  if (error) return <p role="alert" className="text-sm text-rose-700">{error}</p>
  if (!item) return <PageLoader />
  const restricted = item.author?.restriction
  const titles = { remove: 'Remove comment', hide: 'Hide comment', suspend: 'Suspend from comments', ban: 'Ban from comments' }

  return (
    <div className="space-y-5">
      <p role="status" aria-live="polite" className="text-sm text-charcoal-600">{message}</p>
      <div>
        <p className="text-xs uppercase tracking-wide text-charcoal-600">
          On <Link to={`/${item.article.slug}#comments`} className="font-semibold text-burgundy-600 hover:underline">{item.article.title}</Link>
          {item.parentId ? ' · reply' : ''}
        </p>
        <p className="mt-2 text-sm"><span className="font-semibold">{item.author.name}</span> · {formatDate(item.createdAt)}
          {item.editedAt && ' · edited'}</p>
        <div className="mt-2"><StatusText status={item.status} /></div>
        <p className="mt-3 whitespace-pre-line break-words border border-taupe-200 bg-ivory p-3 text-sm">
          {item.body ?? <em>Text erased by its author.</em>}
        </p>
        {item.heldReasons?.length > 0 && (
          <ul className="mt-2 list-disc pl-5 text-xs text-charcoal-600">
            {item.heldReasons.map((r) => <li key={r}>{HELD_REASON_LABELS[r] || r}</li>)}
          </ul>
        )}
        {item.removalReason && <p className="mt-2 text-xs text-charcoal-600">Removal reason: {item.removalReason}</p>}
      </div>

      <div className="flex flex-wrap gap-2">
        {item.status !== 'published' && item.status !== 'deleted' && (
          <button type="button" className={btn} onClick={() => act('approve')}>
            {item.status === 'pending' ? 'Approve' : 'Restore'}
          </button>
        )}
        {(item.status === 'pending' || item.status === 'published') && (
          <button type="button" className={btn} onClick={() => { setReason(''); setDialogError(null); setDialog('hide') }}>Hide</button>
        )}
        {item.status !== 'removed' && item.status !== 'deleted' && (
          <button type="button" className={btn} onClick={() => { setReason(''); setDialogError(null); setDialog('remove') }}>Remove</button>
        )}
      </div>

      {item.author?.userId && (
        <div className="border-t border-taupe-200 pt-4">
          <p className="text-sm font-semibold">Member: {item.author.name}</p>
          {restricted && <p className="mt-1 text-sm">{restrictionMessage(restricted).replace('Your account', 'This account').replace('Your commenting', 'Commenting')}</p>}
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" className={btn} onClick={() => { setReason(''); setDialogError(null); setDialog('suspend') }}>Suspend from comments</button>
            <button type="button" className={btn} onClick={() => { setReason(''); setDialogError(null); setDialog('ban') }}>Ban from comments</button>
            {restricted && <button type="button" className={btn} onClick={lift}>Lift restriction</button>}
          </div>
          <p className="mt-1 text-xs text-charcoal-600">Restrictions only affect comments. The account itself stays active, and existing comments are not changed.</p>
        </div>
      )}

      <div className="border-t border-taupe-200 pt-4">
        <h3 className="text-sm font-semibold">Reports ({item.reports.length})</h3>
        {item.reports.length ? (
          <ul className="mt-2 space-y-1 text-sm">
            {item.reports.map((r, i) => (
              <li key={i}>{r.reason}{r.details ? ` — “${r.details}”` : ''} <span className="text-charcoal-600">· {r.reporter} · {formatDate(r.createdAt)}</span></li>
            ))}
          </ul>
        ) : <p className="mt-1 text-sm text-charcoal-600">No reports.</p>}
      </div>

      <div className="border-t border-taupe-200 pt-4">
        <h3 className="text-sm font-semibold">History</h3>
        <ol className="mt-2 space-y-1 text-sm">
          {item.history.map((e, i) => (
            <li key={i}>
              <span className="font-semibold">{HISTORY_LABELS[e.action] || e.action}</span>
              <span className="text-charcoal-600"> · {e.actor} · {formatDate(e.createdAt)}</span>
              {e.reason && <span className="text-charcoal-600"> · “{e.reason}”</span>}
              {e.action === 'auto_hidden' && e.meta && <span className="text-charcoal-600"> · {e.meta.reports} reports, threshold {e.meta.threshold}</span>}
            </li>
          ))}
        </ol>
      </div>

      <CommentDialog open={!!dialog} titleId={`${base}-dlg`} title={titles[dialog] || ''} onClose={() => setDialog(null)}>
        <form onSubmit={submitDialog} className="space-y-3">
          {dialog === 'suspend' && (
            <div>
              <label htmlFor={`${base}-days`} className="block text-sm font-semibold">Days (1–365)</label>
              <input id={`${base}-days`} type="number" min="1" max="365" value={days} onChange={(e) => setDays(e.target.value)} className={field} />
            </div>
          )}
          <div>
            <label htmlFor={`${base}-reason`} className="block text-sm font-semibold">
              Reason{dialog === 'hide' ? ' (optional)' : ''}
            </label>
            <textarea id={`${base}-reason`} value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={500}
              className={field} required={dialog !== 'hide'} />
          </div>
          {dialogError && <p role="alert" className="text-sm text-rose-700">{dialogError}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" className={btn} onClick={() => setDialog(null)}>Cancel</button>
            <button type="submit" className="btn-primary">{titles[dialog]}</button>
          </div>
        </form>
      </CommentDialog>
    </div>
  )
}

export default function AdminComments() {
  const [queue, setQueue] = useState('pending')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(undefined)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  const load = useCallback(async () => {
    const res = await fetchModerationQueue({ queue, page })
    if (res.success) {
      setData(res.data)
      setError(null)
    } else {
      setError(res.message)
    }
  }, [queue, page])

  useEffect(() => {
    let active = true
    fetchModerationQueue({ queue, page }).then((res) => {
      if (!active) return
      if (res.success) {
        setData(res.data)
        setError(null)
      } else {
        setError(res.message)
      }
    })
    return () => {
      active = false
    }
  }, [queue, page])

  return (
    <div>
      <AdminPageHeader title="Comments" description="Review held, reported and hidden article comments." />
      <div role="group" aria-label="Queue" className="mb-4 flex flex-wrap gap-2">
        {MODERATION_QUEUES.map((q) => (
          <button key={q.value} type="button" aria-pressed={queue === q.value}
            onClick={() => { setQueue(q.value); setPage(1); setSelected(null) }}
            className={`${btn} ${queue === q.value ? 'border-burgundy-500 bg-burgundy-50' : ''}`}>
            {q.label}{data?.counts?.[q.value] != null ? ` (${data.counts[q.value]})` : ''}
          </button>
        ))}
      </div>
      {error && <EmptyState title="Couldn't load comments" description={error} />}
      {!error && data === undefined && <PageLoader />}
      {!error && data && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div>
            {data.items.length ? (
              <ul className="divide-y divide-taupe-200 border border-taupe-200 bg-white">
                {data.items.map((c) => (
                  <li key={c.id}>
                    <button type="button" onClick={() => setSelected(c.id)} aria-current={selected === c.id ? 'true' : undefined}
                      className={`block w-full px-4 py-3 text-left text-sm hover:bg-taupe-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-burgundy-500 ${selected === c.id ? 'bg-taupe-100' : ''}`}>
                      <span className="flex flex-wrap items-center gap-2">
                        <StatusText status={c.status} />
                        <span className="font-semibold">{c.author.name}</span>
                        <span className="text-charcoal-600">on {c.article.title}</span>
                        {c.reportCount > 0 && <span className="text-xs font-semibold">· {c.reportCount} report{c.reportCount === 1 ? '' : 's'}</span>}
                      </span>
                      <span className="mt-1 line-clamp-2 block text-charcoal-600">{c.body ?? '(text erased by its author)'}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="Nothing here" description="No comments in this queue." />
            )}
            {data.totalPages > 1 && (
              <div className="mt-3 flex items-center gap-3 text-sm">
                <button type="button" className={btn} disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
                <span>Page {data.page} of {data.totalPages}</span>
                <button type="button" className={btn} disabled={page >= data.totalPages} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            )}
          </div>
          <aside aria-label="Selected comment" className="border border-taupe-200 bg-white p-4">
            {selected ? <Detail key={selected} id={selected} onChanged={load} /> : <p className="text-sm text-charcoal-600">Choose a comment to review it.</p>}
          </aside>
        </div>
      )}
    </div>
  )
}
