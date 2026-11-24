import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import {
  deleteComment, editComment, fetchArticleComments, fetchCommentForm, postComment, reportComment, setReplyEmails,
} from '../../api/comments'
import {
  COMMENT_MAX_LENGTH, REPORT_REASONS, canEditNow, closedMessage, commentCountLabel, editMinutesLeft,
  postResultMessage, replyTargetId, restrictionMessage,
} from '../../utils/comments'
import { formatDate } from '../../utils/format'
import CommentDialog from './CommentDialog'

// First-party article comments (backend app/api/v1/comments.py). Loaded
// after the article itself (ArticlePage lazy-loads this file below the
// article body), so it never affects the article's server/React first
// paint. Logged-out readers see published comments and a sign-in prompt;
// nothing member-specific is ever in the server HTML.

const fieldClass = 'w-full rounded-card border border-taupe-300 bg-white px-3 py-2 text-sm text-charcoal ' +
  'focus:border-burgundy-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-burgundy-500'
const buttonClass = 'text-xs font-semibold text-charcoal-600 underline-offset-2 hover:text-burgundy-600 ' +
  'hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-burgundy-500'

function Avatar({ author }) {
  if (author?.avatarUrl) {
    return <img src={author.avatarUrl} alt="" width="36" height="36" className="h-9 w-9 shrink-0 rounded-full object-cover" />
  }
  const initial = (author?.name || '?').trim().charAt(0).toUpperCase()
  return (
    <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-taupe-200 text-sm font-semibold text-charcoal-600">
      {initial}
    </span>
  )
}

function CommentForm({ slug, parentId = null, label, submitLabel, onPosted, autoFocus = false, onCancel }) {
  const [body, setBody] = useState('')
  const [formToken, setFormToken] = useState(null)
  const [website, setWebsite] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const id = useId()
  const textRef = useRef(null)

  const loadToken = useCallback(async () => {
    const res = await fetchCommentForm(slug)
    if (res.success) setFormToken(res.data.formToken)
    else setError(res.message)
  }, [slug])

  useEffect(() => {
    let active = true
    fetchCommentForm(slug).then((res) => {
      if (!active) return
      if (res.success) setFormToken(res.data.formToken)
      else setError(res.message)
    })
    return () => {
      active = false
    }
  }, [slug])

  useEffect(() => {
    if (autoFocus) textRef.current?.focus()
  }, [autoFocus])

  async function submit(e) {
    e.preventDefault()
    if (!body.trim()) {
      setError('Please write a comment.')
      textRef.current?.focus()
      return
    }
    setBusy(true)
    setError(null)
    const res = await postComment(slug, { body, parentId, formToken, website })
    setBusy(false)
    if (!res.success) {
      setError(res.message)
      if (res.code === 'comment_form_expired' || res.code === 'comment_form_invalid') loadToken()
      return
    }
    setBody('')
    loadToken()
    onPosted?.(res.data)
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-2">
      <label htmlFor={`${id}-body`} className="block text-sm font-semibold text-charcoal">{label}</label>
      <textarea
        id={`${id}-body`}
        ref={textRef}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={parentId ? 3 : 4}
        maxLength={COMMENT_MAX_LENGTH}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={fieldClass}
      />
      {/* Honeypot: no person ever fills this in. Hidden from assistive
          technology (aria-hidden) and from keyboard focus (tabIndex -1), not
          just visually; the server refuses any submission that fills it. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
        <label htmlFor={`${id}-website`}>Leave this field empty</label>
        <input id={`${id}-website`} name="website" type="text" tabIndex={-1} autoComplete="off"
          value={website} onChange={(e) => setWebsite(e.target.value)} />
      </div>
      {error && <p id={`${id}-error`} role="alert" className="text-sm text-rose-700">{error}</p>}
      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy || !formToken} className="btn-primary disabled:opacity-60">
          {busy ? 'Posting…' : submitLabel}
        </button>
        {onCancel && <button type="button" onClick={onCancel} className={buttonClass}>Cancel</button>}
      </div>
    </form>
  )
}

function EditForm({ comment, onSaved, onCancel }) {
  const [body, setBody] = useState(comment.body)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const id = useId()
  const ref = useRef(null)
  useEffect(() => ref.current?.focus(), [])

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    const res = await editComment(comment.id, body)
    setBusy(false)
    if (!res.success) return setError(res.message)
    onSaved(res.data)
    return undefined
  }

  return (
    <form onSubmit={save} className="mt-2 space-y-2">
      <label htmlFor={`${id}-edit`} className="sr-only">Edit your comment</label>
      <textarea id={`${id}-edit`} ref={ref} value={body} onChange={(e) => setBody(e.target.value)} rows={3}
        maxLength={COMMENT_MAX_LENGTH} className={fieldClass} aria-describedby={`${id}-hint`} />
      <p id={`${id}-hint`} className="text-xs text-charcoal-600">
        You can edit for about {editMinutesLeft(comment)} more minute{editMinutesLeft(comment) === 1 ? '' : 's'}.
      </p>
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy} className="btn-primary disabled:opacity-60">Save</button>
        <button type="button" onClick={onCancel} className={buttonClass}>Cancel</button>
      </div>
    </form>
  )
}

function CommentItem({ comment, canInteract, signedIn, open, onReply, onChanged, onAnnounce, slug, replyingTo, replyForm = null }) {
  const [editing, setEditing] = useState(false)
  const [dialog, setDialog] = useState(null) // 'delete' | 'report'
  const [reason, setReason] = useState('spam')
  const [details, setDetails] = useState('')
  const [dialogError, setDialogError] = useState(null)
  const baseId = useId()

  if (comment.placeholder) {
    return (
      <li id={`comment-${comment.id}`} className="py-4">
        <p className="text-sm italic text-charcoal-600">{comment.body}</p>
        {comment.replies?.length > 0 && <Replies {...{ comment, canInteract, signedIn, open, onReply, onChanged, onAnnounce, slug, replyingTo }} />}
        {replyForm}
      </li>
    )
  }

  async function confirmDelete() {
    const res = await deleteComment(comment.id)
    if (!res.success) return setDialogError(res.message)
    setDialog(null)
    onAnnounce('Your comment was deleted.')
    onChanged()
    return undefined
  }

  async function sendReport(e) {
    e.preventDefault()
    const res = await reportComment(comment.id, { reason, details: reason === 'other' ? details : undefined })
    if (!res.success) return setDialogError(res.message)
    setDialog(null)
    onAnnounce('Thanks for letting us know. A moderator will take a look.')
    onChanged()
    return undefined
  }

  const pending = comment.status === 'pending'
  const hidden = comment.isOwn && comment.status === 'hidden'
  return (
    <li id={`comment-${comment.id}`} className="py-4">
      <article aria-labelledby={`${baseId}-who`} className="flex gap-3">
        <Avatar author={comment.author} />
        <div className="min-w-0 flex-1">
          <p className="text-sm">
            <span id={`${baseId}-who`} className="font-semibold text-charcoal">{comment.author?.name}</span>
            <span className="text-charcoal-600"> · <time dateTime={comment.createdAt}>{formatDate(comment.createdAt)}</time></span>
            {comment.edited && <span className="text-charcoal-600"> · edited</span>}
          </p>
          {pending && (
            <p className="mt-1 inline-block rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-900">
              Awaiting approval — only you can see this
            </p>
          )}
          {hidden && (
            <p className="mt-1 inline-block rounded-full border border-taupe-300 bg-taupe-100 px-2 py-0.5 text-xs font-semibold text-charcoal-600">
              Hidden while a moderator reviews it
            </p>
          )}
          {editing ? (
            <EditForm comment={comment} onCancel={() => setEditing(false)}
              onSaved={(data) => { setEditing(false); onAnnounce(data.status === 'pending' ? 'Saved. Your edit is waiting for a moderator.' : 'Your edit was saved.'); onChanged() }} />
          ) : (
            <p className="mt-1 whitespace-pre-line break-words text-[0.95rem] leading-relaxed text-charcoal">{comment.body}</p>
          )}
          {!editing && (
            <div className="mt-2 flex flex-wrap gap-4">
              {canInteract && open && comment.status === 'published' && (
                <button type="button" className={buttonClass} onClick={() => onReply(replyTargetId(comment))}
                  aria-expanded={replyingTo === replyTargetId(comment)}>
                  Reply<span className="sr-only"> to {comment.author?.name}</span>
                </button>
              )}
              {comment.isOwn && canEditNow(comment) && canInteract && (
                <button type="button" className={buttonClass} onClick={() => setEditing(true)}>Edit</button>
              )}
              {comment.isOwn && (
                <button type="button" className={buttonClass} onClick={() => { setDialogError(null); setDialog('delete') }}>Delete</button>
              )}
              {signedIn && !comment.isOwn && comment.status === 'published' && canInteract && (
                comment.reportedByMe
                  ? <span className="text-xs text-charcoal-600">Reported</span>
                  : <button type="button" className={buttonClass} onClick={() => { setDialogError(null); setDialog('report') }}>Report</button>
              )}
            </div>
          )}
        </div>
      </article>

      <CommentDialog open={dialog === 'delete'} titleId={`${baseId}-del`} title="Delete this comment?" onClose={() => setDialog(null)}>
        <p className="text-sm text-charcoal-600">
          {comment.replies?.length ? 'Replies stay; your comment will show as “Comment deleted”.' : 'This can’t be undone.'}
        </p>
        {dialogError && <p role="alert" className="mt-2 text-sm text-rose-700">{dialogError}</p>}
        <div className="mt-5 flex justify-end gap-3">
          <button type="button" className={buttonClass} onClick={() => setDialog(null)} autoFocus>Cancel</button>
          <button type="button" className="btn-primary" onClick={confirmDelete}>Delete comment</button>
        </div>
      </CommentDialog>

      <CommentDialog open={dialog === 'report'} titleId={`${baseId}-rep`} title="Report this comment" onClose={() => setDialog(null)}>
        <form onSubmit={sendReport}>
          <fieldset>
            <legend className="text-sm text-charcoal-600">Why are you reporting it?</legend>
            <div className="mt-2 space-y-1">
              {REPORT_REASONS.map((r) => (
                <label key={r.value} className="flex items-center gap-2 text-sm">
                  <input type="radio" name={`${baseId}-reason`} value={r.value} checked={reason === r.value}
                    onChange={() => setReason(r.value)} />
                  {r.label}
                </label>
              ))}
            </div>
          </fieldset>
          {reason === 'other' && (
            <div className="mt-3">
              <label htmlFor={`${baseId}-details`} className="block text-sm font-semibold">Tell us more (optional)</label>
              <textarea id={`${baseId}-details`} value={details} maxLength={500} rows={3}
                onChange={(e) => setDetails(e.target.value)} className={`${fieldClass} mt-1`} />
            </div>
          )}
          {dialogError && <p role="alert" className="mt-2 text-sm text-rose-700">{dialogError}</p>}
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" className={buttonClass} onClick={() => setDialog(null)}>Cancel</button>
            <button type="submit" className="btn-primary">Send report</button>
          </div>
        </form>
      </CommentDialog>

      {comment.replies?.length > 0 && !comment.parentId && (
        <Replies {...{ comment, canInteract, signedIn, open, onReply, onChanged, onAnnounce, slug, replyingTo }} />
      )}
      {replyForm}
    </li>
  )
}

function Replies({ comment, ...rest }) {
  return (
    <ul aria-label={`Replies to ${comment.author?.name || 'this comment'}`} className="ml-12 mt-1 divide-y divide-taupe-100 border-l-2 border-taupe-200 pl-4">
      {comment.replies.map((reply) => <CommentItem key={reply.id} comment={reply} {...rest} />)}
    </ul>
  )
}

export default function CommentsSection({ slug }) {
  const sessionChecked = useSelector((s) => s.auth.sessionChecked)
  const accessToken = useSelector((s) => s.auth.accessToken)
  const location = useLocation()
  const [data, setData] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [replyingTo, setReplyingTo] = useState(null)
  const [announcement, setAnnouncement] = useState('')
  const [emailBusy, setEmailBusy] = useState(false)

  const load = useCallback(async () => {
    const res = await fetchArticleComments(slug)
    if (res.success) {
      setData(res.data)
      setLoadError(null)
    } else {
      setLoadError(res.message)
    }
  }, [slug])

  useEffect(() => {
    if (!sessionChecked) return undefined
    let active = true
    fetchArticleComments(slug).then((res) => {
      if (!active) return
      if (res.success) {
        setData(res.data)
        setLoadError(null)
      } else {
        setLoadError(res.message)
      }
    })
    return () => {
      active = false
    }
  }, [sessionChecked, accessToken, slug])

  const signedIn = !!accessToken && !!data?.viewer
  const restriction = data?.viewer?.restriction || null
  const canInteract = signedIn && !restriction
  const open = !!data?.open

  function posted(result) {
    setReplyingTo(null)
    setAnnouncement(postResultMessage(result.status))
    load()
  }

  async function toggleEmails(e) {
    setEmailBusy(true)
    const res = await setReplyEmails(e.target.checked)
    setEmailBusy(false)
    if (res.success) {
      setData((d) => ({ ...d, viewer: { ...d.viewer, replyEmails: res.data.replyEmails } }))
      setAnnouncement(res.data.replyEmails ? 'We’ll email you when someone replies to your comments.' : 'Reply emails are off.')
    } else {
      setAnnouncement(res.message)
    }
  }

  const replyThread = replyingTo != null ? data?.comments.find((c) => c.id === replyingTo) : null

  return (
    <section aria-labelledby="comments-heading" className="mt-16 border-t border-taupe-200 pt-8" id="comments">
      <h2 id="comments-heading" className="font-serif text-2xl font-semibold text-charcoal">
        {commentCountLabel(data?.count)}
      </h2>
      <p role="status" aria-live="polite" className="sr-only">{announcement}</p>
      {announcement && <p className="mt-3 text-sm text-charcoal-600" aria-hidden="true">{announcement}</p>}

      {!data && !loadError && <p className="mt-4 text-sm text-charcoal-600">Loading comments…</p>}
      {loadError && <p role="alert" className="mt-4 text-sm text-rose-700">{loadError}</p>}

      {data && (
        <>
          <div className="mt-5 rounded-card border border-taupe-200 bg-ivory p-5">
            {!open ? (
              <p className="text-sm text-charcoal-600">{closedMessage(data.state)}</p>
            ) : !signedIn ? (
              <p className="text-sm text-charcoal-600">
                <Link to="/login" state={{ from: `${location.pathname}#comments` }} className="font-semibold text-burgundy-600 hover:underline">
                  Sign in
                </Link>{' '}
                to join the conversation. Don’t have an account?{' '}
                <Link to="/register" state={{ from: `${location.pathname}#comments` }} className="font-semibold text-burgundy-600 hover:underline">
                  Create one
                </Link>.
              </p>
            ) : restriction ? (
              <p role="note" className="text-sm font-semibold text-charcoal">{restrictionMessage(restriction)}</p>
            ) : (
              <>
                <p className="mb-3 text-xs text-charcoal-600">
                  By commenting you agree to our{' '}
                  <Link to="/terms" className="font-semibold text-burgundy-600 hover:underline">Community Guidelines</Link>{' '}
                  and{' '}
                  <Link to="/privacy" className="font-semibold text-burgundy-600 hover:underline">Privacy Policy</Link>.
                </p>
                <CommentForm slug={slug} label="Add a comment" submitLabel="Post comment" onPosted={posted} />
                {data.viewer?.replyNotificationsAvailable && (
                  <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
                    <input type="checkbox" checked={!!data.viewer.replyEmails} disabled={emailBusy} onChange={toggleEmails} />
                    Email me when someone replies to my comments
                  </label>
                )}
              </>
            )}
          </div>

          {data.comments.length > 0 ? (
            <ul aria-label="Comments" className="mt-6 divide-y divide-taupe-200">
              {data.comments.map((comment) => (
                <CommentItem key={comment.id} comment={comment} canInteract={canInteract} signedIn={signedIn} open={open}
                  slug={slug} replyingTo={replyingTo} onReply={(id) => setReplyingTo((cur) => (cur === id ? null : id))}
                  onChanged={load} onAnnounce={setAnnouncement}
                  replyForm={replyThread && replyThread.id === comment.id && canInteract && open ? (
                    <div className="mt-3 ml-12 border-l-2 border-burgundy-500 pl-4">
                      <CommentForm slug={slug} parentId={replyThread.id} autoFocus
                        label={`Reply to ${replyThread.author?.name || 'this thread'}`} submitLabel="Post reply"
                        onPosted={posted} onCancel={() => setReplyingTo(null)} />
                    </div>
                  ) : null} />
              ))}
            </ul>
          ) : (
            <p className="mt-6 text-sm text-charcoal-600">{open ? 'No comments yet. Start the conversation.' : 'No comments.'}</p>
          )}
        </>
      )}
    </section>
  )
}
