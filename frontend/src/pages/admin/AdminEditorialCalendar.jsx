import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { fetchEditorialCalendar } from '../../api/articles'
import { fetchAuthors, fetchTopics } from '../../api/taxonomies'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const STATUS_OPTIONS = ['approved', 'scheduled', 'published']
const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

// Mirrors StatusBadge's own approved/scheduled icon convention (not
// imported from there — a named export alongside StatusBadge's default
// component export would break React Fast Refresh for that file) so the
// desktop month-grid cells below stay distinguishable the same way
// StatusBadge already is: approved and scheduled share one color family,
// so the icon — not color alone — is what tells them apart.
const STATUS_ICONS = {
  approved: CheckCircle2,
  scheduled: Clock,
}

// bg-burgundy-500 and bg-emerald-500 are both already used elsewhere in
// the app, so this introduces no new Tailwind utility — just reuses the
// same color families StatusBadge uses for these statuses, compacted to a
// small dot since the grid cells are too small for a full badge.
const STATUS_DOT_COLOR = {
  approved: 'bg-burgundy-500',
  scheduled: 'bg-burgundy-500',
  published: 'bg-emerald-500',
}

// The date the calendar cares about: scheduled_at while scheduled,
// otherwise the effective publish date — see backend
// ArticleCalendarResource, which matches on this same "either" rule.
function itemDate(item) {
  return item.scheduledAt || item.publishDate
}

function startOfMonthGrid(monthDate) {
  const firstOfMonth = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
  const start = new Date(firstOfMonth)
  start.setDate(start.getDate() - start.getDay())
  start.setHours(0, 0, 0, 0)
  return start
}

function endOfMonthGrid(monthDate) {
  const lastOfMonth = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0)
  const end = new Date(lastOfMonth)
  end.setDate(end.getDate() + (6 - end.getDay()))
  end.setHours(23, 59, 59, 999)
  return end
}

function dayKey(date) {
  return date.toISOString().slice(0, 10)
}

export default function AdminEditorialCalendar() {
  const navigate = useNavigate()
  const [monthDate, setMonthDate] = useState(() => new Date())
  const [status, setStatus] = useState('')
  const [author, setAuthor] = useState('')
  const [topic, setTopic] = useState('')
  const [authors, setAuthors] = useState([])
  const [topics, setTopics] = useState([])
  const [items, setItems] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchAuthors({ pageSize: 200 }).then((res) => setAuthors(res.items)).catch(() => {})
    fetchTopics().then(setTopics).catch(() => {})
  }, [])

  const gridStart = useMemo(() => startOfMonthGrid(monthDate), [monthDate])
  const gridEnd = useMemo(() => endOfMonthGrid(monthDate), [monthDate])

  useEffect(() => {
    let active = true
    setError(null)
    setItems(undefined)
    fetchEditorialCalendar({
      start: gridStart.toISOString(),
      end: gridEnd.toISOString(),
      status: status || undefined,
      author: author || undefined,
      topic: topic || undefined,
    })
      .then((data) => active && setItems(data))
      .catch(() => active && setError('Something went wrong loading the editorial calendar. Please try again.'))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gridStart, gridEnd, status, author, topic])

  const itemsByDay = useMemo(() => {
    const map = new Map()
    for (const item of items || []) {
      const date = itemDate(item)
      if (!date) continue
      const key = dayKey(new Date(date))
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(item)
    }
    for (const list of map.values()) list.sort((a, b) => new Date(itemDate(a)) - new Date(itemDate(b)))
    return map
  }, [items])

  const upcoming = useMemo(() => {
    const now = new Date()
    const weekOut = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
    return (items || [])
      .filter((item) => {
        const d = itemDate(item)
        return d && new Date(d) >= now && new Date(d) <= weekOut
      })
      .sort((a, b) => new Date(itemDate(a)) - new Date(itemDate(b)))
      .slice(0, 8)
  }, [items])

  const days = useMemo(() => {
    const result = []
    const cursor = new Date(gridStart)
    while (cursor <= gridEnd) {
      result.push(new Date(cursor))
      cursor.setDate(cursor.getDate() + 1)
    }
    return result
  }, [gridStart, gridEnd])

  function goToMonth(offset) {
    setMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + offset, 1))
  }

  function openArticle(item) {
    navigate(`/admin/articles/${item.slug}`)
  }

  const monthLabel = monthDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
  const today = dayKey(new Date())

  return (
    <div>
      <AdminPageHeader
        title="Editorial Calendar"
        description="Upcoming and recent publication dates — scheduled and published articles only. Content Calendar, not public Events."
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => goToMonth(-1)} aria-label="Previous month" className="btn-secondary !px-2 !py-2">
            <ChevronLeft size={15} />
          </button>
          <p className="min-w-[10rem] text-center font-serif text-lg font-semibold text-charcoal">{monthLabel}</p>
          <button type="button" onClick={() => goToMonth(1)} aria-label="Next month" className="btn-secondary !px-2 !py-2">
            <ChevronRight size={15} />
          </button>
          <button type="button" onClick={() => setMonthDate(new Date())} className="btn-secondary !px-3 !py-2 text-xs">
            Today
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select value={author} onChange={(e) => setAuthor(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
            <option value="">All authors</option>
            {authors.map((a) => (
              <option key={a.slug} value={a.slug}>
                {a.name}
              </option>
            ))}
          </select>
          <select value={topic} onChange={(e) => setTopic(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
            <option value="">All topics</option>
            {topics.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <EmptyState title="Couldn't load the calendar" description={error} />}
      {!error && items === undefined && <PageLoader />}

      {!error && items !== undefined && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_260px]">
          {/* Month grid — hidden on small screens in favor of the agenda list below. */}
          <div className="hidden overflow-hidden border border-taupe-200 bg-white md:block">
            <div className="grid grid-cols-7 bg-taupe-100 text-center text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">
              {WEEKDAY_LABELS.map((label) => (
                <div key={label} className="px-2 py-2">
                  {label}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7">
              {days.map((day) => {
                const key = dayKey(day)
                const dayItems = itemsByDay.get(key) || []
                const inMonth = day.getMonth() === monthDate.getMonth()
                return (
                  <div
                    key={key}
                    className={`min-h-[110px] border-b border-r border-taupe-200 p-1.5 ${inMonth ? 'bg-white' : 'bg-taupe-50 text-charcoal-600/50'} ${key === today ? 'ring-1 ring-inset ring-burgundy-400' : ''}`}
                  >
                    <p className="text-[11px] font-semibold">{day.getDate()}</p>
                    <div className="mt-1 space-y-1">
                      {dayItems.slice(0, 3).map((item) => {
                        const StatusIcon = STATUS_ICONS[item.status]
                        return (
                          <button
                            key={item.id}
                            type="button"
                            onClick={() => openArticle(item)}
                            className="flex w-full items-center gap-1 truncate bg-blush-100 px-1.5 py-0.5 text-left text-[11px] text-charcoal hover:bg-blush-200"
                            title={`${item.title} — ${item.status}`}
                          >
                            <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${STATUS_DOT_COLOR[item.status] || 'bg-taupe-400'}`} aria-hidden="true" />
                            {StatusIcon && <StatusIcon size={10} className="shrink-0" aria-hidden="true" />}
                            <span className="truncate">{item.title}</span>
                          </button>
                        )
                      })}
                      {dayItems.length > 3 && <p className="text-[10px] text-charcoal-600/70">+{dayItems.length - 3} more</p>}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Agenda list — the only view on mobile, and a readable alternative to tiny calendar cells. */}
          <div className="border border-taupe-200 bg-white md:hidden">
            {[...itemsByDay.entries()]
              .filter(([key]) => {
                const d = new Date(key)
                return d.getMonth() === monthDate.getMonth()
              })
              .map(([key, dayItems]) => (
                <div key={key} className="border-b border-taupe-200 p-3 last:border-b-0">
                  <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                    {formatDate(key, { weekday: 'short', month: 'short', day: 'numeric' })}
                  </p>
                  <div className="mt-2 space-y-2">
                    {dayItems.map((item) => (
                      <button key={item.id} type="button" onClick={() => openArticle(item)} className="flex w-full items-center justify-between gap-2 border border-taupe-200 p-2 text-left text-sm">
                        <span className="truncate">{item.title}</span>
                        <StatusBadge status={item.status} />
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            {items.length === 0 && <p className="p-4 text-sm text-charcoal-600">Nothing scheduled or published this month.</p>}
          </div>

          <div className="space-y-4">
            <div className="border border-taupe-200 bg-white p-4">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <Clock size={13} /> Upcoming (next 7 days)
              </p>
              <div className="mt-3 space-y-2">
                {upcoming.length === 0 && <p className="text-xs text-charcoal-600/70">Nothing scheduled in the next 7 days.</p>}
                {upcoming.map((item) => (
                  <button key={item.id} type="button" onClick={() => openArticle(item)} className="block w-full border border-taupe-200 p-2 text-left hover:border-burgundy-300">
                    <p className="truncate text-sm font-medium text-charcoal">{item.title}</p>
                    <p className="mt-0.5 flex items-center justify-between text-[11px] text-charcoal-600">
                      <span>{formatDate(itemDate(item), { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
                      <StatusBadge status={item.status} />
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
