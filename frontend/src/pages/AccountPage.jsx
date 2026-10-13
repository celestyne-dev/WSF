import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { fetchSavedItems } from '../api/saved'
import { fetchMyEventRegistrations } from '../api/eventRegistrations'
import { fetchMyLearningEnrollments } from '../api/learningEnrollments'
import { fetchMyCommunityMembership } from '../api/community'
import { fetchMyCircleMembership } from '../api/circle'
import { getRoleLabel } from '../constants/roles'
import useSeo from '../hooks/useSeo'

const SAVED_TYPE_LABEL = {
  article: 'stories',
  job: 'jobs',
  opportunity: 'opportunities',
  resource: 'resources',
  event: 'events',
  learning_program: 'learning',
}

// A compact editorial summary tile — the overview's unit of composition.
// Deliberately plain (one border, no shadow, no icon) so a 2-column grid
// of these doesn't read as a stack of SaaS dashboard cards.
function OverviewTile({ title, children, action }) {
  return (
    <section className="border border-taupe-200 bg-white p-5">
      <h3 className="font-serif text-lg font-semibold text-charcoal">{title}</h3>
      <div className="mt-2 text-sm text-charcoal-600">{children}</div>
      {action && <div className="mt-3">{action}</div>}
    </section>
  )
}

function TileLink({ to, children }) {
  return (
    <Link to={to} className="text-sm font-semibold text-burgundy-600 hover:underline">
      {children}
    </Link>
  )
}

// Deliberately a tiny summary, not the full collection (spec: "do NOT
// overload /account with the entire Saved collection") — one count fetch,
// perPage: 1 so the items payload stays minimal since only `counts` and
// `pagination.totalItems` are used here.
function SavedTile() {
  const [totalSaved, setTotalSaved] = useState(null)
  const [typeCounts, setTypeCounts] = useState({})

  useEffect(() => {
    let cancelled = false
    fetchSavedItems({ perPage: 1 }).then((result) => {
      if (cancelled) return
      setTotalSaved(result.pagination?.totalItems ?? 0)
      setTypeCounts(result.counts || {})
    })
    return () => {
      cancelled = true
    }
  }, [])

  const topTypeCounts = Object.entries(typeCounts)
    .filter(([, count]) => count > 0)
    .slice(0, 3)

  return (
    <OverviewTile title="Saved for later" action={<TileLink to="/account/saved">View saved →</TileLink>}>
      {totalSaved !== null && totalSaved > 0 ? (
        <p>
          <span className="font-semibold text-charcoal">{totalSaved}</span> saved item{totalSaved === 1 ? '' : 's'}
          {topTypeCounts.length > 0 && (
            <span className="text-charcoal-600/70">
              {' '}
              ({topTypeCounts.map(([type, count]) => `${count} ${SAVED_TYPE_LABEL[type] || type}`).join(', ')})
            </span>
          )}
        </p>
      ) : (
        <p>Keep stories, jobs, opportunities, resources, events and learning programs you want to return to.</p>
      )}
    </OverviewTile>
  )
}

// Same "tiny summary, not the full collection" principle as SavedTile
// above — one count fetch (perPage: 1), only `pagination.totalItems` is
// actually used here.
function EventsTile() {
  const [upcomingCount, setUpcomingCount] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchMyEventRegistrations({ when: 'upcoming', perPage: 1 }).then((result) => {
      if (!cancelled) setUpcomingCount(result.pagination?.totalItems ?? 0)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <OverviewTile title="My Events" action={<TileLink to="/account/events">View events →</TileLink>}>
      {upcomingCount !== null && upcomingCount > 0 ? (
        <p>
          <span className="font-semibold text-charcoal">{upcomingCount}</span> upcoming registration
          {upcomingCount === 1 ? '' : 's'}
        </p>
      ) : (
        <p>Events you've registered for with Women Shaping Futures.</p>
      )}
    </OverviewTile>
  )
}

// Same "tiny summary, not the full collection" principle as the tiles
// above — two count-only fetches (perPage: 1, one per state), only
// `pagination.totalItems` from each is used.
function LearningTile() {
  const [counts, setCounts] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetchMyLearningEnrollments({ state: 'current', perPage: 1 }),
      fetchMyLearningEnrollments({ state: 'completed', perPage: 1 }),
    ]).then(([current, completed]) => {
      if (cancelled) return
      setCounts({
        inProgress: current.pagination?.totalItems ?? 0,
        completed: completed.pagination?.totalItems ?? 0,
      })
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <OverviewTile title="My Learning" action={<TileLink to="/account/learning">View learning →</TileLink>}>
      {counts && (counts.inProgress > 0 || counts.completed > 0) ? (
        <p>
          <span className="font-semibold text-charcoal">{counts.inProgress}</span> in progress
          {counts.completed > 0 && (
            <>
              {' · '}
              <span className="font-semibold text-charcoal">{counts.completed}</span> completed
            </>
          )}
        </p>
      ) : (
        <p>Programs you're learning with Women Shaping Futures.</p>
      )}
    </OverviewTile>
  )
}

// Same "tiny summary" principle as the tiles above, plus the spec's
// explicit "handle API failure quietly and resiliently — no unhandled
// promise rejection" requirement: a failed fetch falls back to the same
// safe "not joined" copy rather than throwing or blanking the page.
function CommunityTile() {
  const [membership, setMembership] = useState(undefined)

  useEffect(() => {
    let cancelled = false
    fetchMyCommunityMembership()
      .then((result) => {
        if (!cancelled) setMembership(result)
      })
      .catch(() => {
        if (!cancelled) setMembership(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const member = membership?.member
  const isActive = member?.status === 'active'
  const isInactive = member && ['left', 'inactive'].includes(member.status)
  const isOtherState = member && !isActive && !isInactive

  if (isActive) {
    return (
      <OverviewTile title="WSF Community" action={<TileLink to="/account/community">Manage profile →</TileLink>}>
        <p>
          You're a <span className="font-semibold text-charcoal">{member.membershipType}</span>.
        </p>
      </OverviewTile>
    )
  }
  if (isInactive) {
    return (
      <OverviewTile title="WSF Community" action={<TileLink to="/account/community">Rejoin →</TileLink>}>
        <p>You're not currently an active Community member.</p>
      </OverviewTile>
    )
  }
  if (isOtherState) {
    return (
      <OverviewTile title="WSF Community" action={<TileLink to="/account/community">View details →</TileLink>}>
        <p>Your Community membership is managed by our team.</p>
      </OverviewTile>
    )
  }
  return (
    <OverviewTile
      title="WSF Community"
      action={<TileLink to="/community">{membership?.joined === false ? 'Join the WSF Community →' : 'Explore the WSF Community →'}</TileLink>}
    >
      <p>A WSF account and WSF Community membership are separate.</p>
    </OverviewTile>
  )
}

// Same "tiny summary + resilient failure" principle as CommunityTile
// above — GET /circle/me, falls back to the safe "no membership" copy on
// any fetch failure rather than throwing or blanking the page.
function CircleTile() {
  const [membership, setMembership] = useState(undefined)

  useEffect(() => {
    let cancelled = false
    fetchMyCircleMembership()
      .then((result) => {
        if (!cancelled) setMembership(result)
      })
      .catch(() => {
        if (!cancelled) setMembership(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const subscription = membership?.subscription
  const status = subscription?.status

  if (status === 'active') {
    return (
      <OverviewTile title="WSF Circle" action={<TileLink to="/account/membership">Manage membership →</TileLink>}>
        <p>
          <span className="font-semibold text-burgundy-600">Active</span>
          {subscription.plan?.name && <> &middot; {subscription.plan.name}</>}
        </p>
      </OverviewTile>
    )
  }
  if (status === 'pending') {
    return (
      <OverviewTile title="WSF Circle" action={<TileLink to="/account/membership">View details →</TileLink>}>
        <p>Membership pending.</p>
      </OverviewTile>
    )
  }
  if (status === 'past_due') {
    return (
      <OverviewTile title="WSF Circle" action={<TileLink to="/account/membership">View details →</TileLink>}>
        <p>Membership needs attention.</p>
      </OverviewTile>
    )
  }
  if (status === 'cancelled' || status === 'expired' || status === 'revoked') {
    return (
      <OverviewTile title="WSF Circle" action={<TileLink to="/circle">Explore membership options →</TileLink>}>
        <p>Not currently active.</p>
      </OverviewTile>
    )
  }
  return (
    <OverviewTile title="WSF Circle" action={<TileLink to="/circle">Explore WSF Circle →</TileLink>}>
      <p>You are not currently a WSF Circle member.</p>
    </OverviewTile>
  )
}

// /account (index) — the account workspace's overview/dashboard. Profile
// editing and password changes now live on their own dedicated pages
// (/account/profile, /account/security); this page only shows a compact
// account-details summary plus activity/membership tiles that link out to
// their own full pages (spec: "do NOT overload /account").
export default function AccountPage() {
  const user = useSelector((s) => s.auth.user)
  const countries = useSelector((s) => s.site.countries)

  useSeo({ title: 'My Account | Women Shaping Futures', robots: 'noindex, nofollow' })

  const countryName = countries.find((c) => c.code === user.countryCode)?.name

  return (
    <div>
      <h2 className="font-serif text-2xl font-semibold text-charcoal">Overview</h2>

      <section className="mt-4 border border-taupe-200 bg-cream p-5">
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Email</dt>
            <dd className="mt-1 text-sm text-charcoal">{user.email}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Account type</dt>
            <dd className="mt-1 text-sm text-charcoal">{getRoleLabel(user.role)}</dd>
          </div>
          {countryName && (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Country</dt>
              <dd className="mt-1 text-sm text-charcoal">{countryName}</dd>
            </div>
          )}
        </dl>
        <div className="mt-4 flex flex-wrap gap-5 border-t border-taupe-200 pt-4">
          <TileLink to="/account/profile">Edit profile →</TileLink>
          <TileLink to="/account/security">Security →</TileLink>
        </div>
      </section>

      <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2">
        <SavedTile />
        <EventsTile />
        <LearningTile />
        <CommunityTile />
        <CircleTile />
      </div>
    </div>
  )
}
