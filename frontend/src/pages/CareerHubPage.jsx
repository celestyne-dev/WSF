import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Search, Sparkles } from 'lucide-react'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import {
  fetchCareerHub,
  fetchCareerHubMeta,
  fetchMyCareerGoals,
  fetchRecommendedForMyGoals,
  saveMyCareerGoals,
  skipCareerGoalsPrompt,
} from '../api/careerHub'
import CareerGoalsPicker from '../components/account/CareerGoalsPicker'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import FilterSelect from '../components/ui/FilterSelect'
import Pagination from '../components/ui/Pagination'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'
import CareerHubCard from '../components/cards/CareerHubCard'
import { trackEvent } from '../utils/analytics'
import {
  buildHubSearch,
  describeResults,
  hubRequestParams,
  isFiltering,
  parseHubParams,
  updateHubState,
} from '../utils/careerHub'

const CANONICAL = 'https://womenshapingfutures.org/career-hub'
// Kept identical to the server prerender (app/services/spa_shell.py's
// CAREER_HUB_* constants) so crawlers and visitors read the same copy.
const EYEBROW = 'Career Hub'
const TITLE = 'Practical tools for your next career move.'
const DESCRIPTION =
  "Playbooks, workbooks, templates, courses and challenges from WSF — organised by the career problem you're solving, with free, WSF Circle and premium options."

function CardGrid({ cards, onOpen }) {
  return (
    <ul className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((card) => (
        <li key={card.id} className="min-w-0">
          <CareerHubCard card={card} onOpen={onOpen} />
        </li>
      ))}
    </ul>
  )
}

// Signed-in personalization: a skippable one-time goal prompt, then a
// deterministic "Recommended for your goals" strip (backend picks by the
// goals' Topics; no AI). Renders nothing for anonymous visitors, while
// loading, or when there is nothing to recommend.
function ForYourGoals({ goalOptions, onOpen }) {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [mine, setMine] = useState(null)
  const [draft, setDraft] = useState([])
  const [recommended, setRecommended] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!accessToken) return undefined
    let active = true
    fetchMyCareerGoals()
      .then((data) => {
        if (!active) return
        setMine(data)
        if (data.goals.length) {
          fetchRecommendedForMyGoals()
            .then((items) => active && setRecommended(items))
            .catch(() => {})
        }
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [accessToken])

  if (!accessToken || !mine || goalOptions.length === 0) return null

  async function save() {
    setSaving(true)
    try {
      const data = await saveMyCareerGoals(draft)
      setMine(data)
      trackEvent('career_goals_saved', { goals: draft, source: 'career_hub_prompt' })
      setRecommended(await fetchRecommendedForMyGoals())
    } catch {
      toast.error('We couldn’t save your goals. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function skip() {
    setMine({ ...mine, prompted: true })
    trackEvent('career_goals_skipped', { source: 'career_hub_prompt' })
    skipCareerGoalsPrompt().catch(() => {})
  }

  if (mine.goals.length === 0) {
    if (mine.prompted) return null
    return (
      <section aria-labelledby="career-hub-goals-prompt" className="mt-12 border border-taupe-200 bg-white p-6">
        <h2 id="career-hub-goals-prompt" className="font-serif text-xl font-semibold text-charcoal">What are you working towards?</h2>
        <p className="mt-1 text-sm text-charcoal-600">Pick your goals and we’ll suggest tools for them. You can change this any time in your account.</p>
        <div className="mt-4">
          <CareerGoalsPicker goals={goalOptions} value={draft} onChange={setDraft} disabled={saving} />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button type="button" onClick={save} disabled={saving || draft.length === 0} className="btn-primary disabled:opacity-60">
            Save my goals
          </button>
          <button type="button" onClick={skip} className="text-sm font-semibold text-charcoal-600 hover:text-burgundy-600">
            Skip for now
          </button>
        </div>
      </section>
    )
  }

  if (recommended.length === 0) return null
  return (
    <section aria-labelledby="career-hub-for-you" className="mt-12">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="career-hub-for-you" className="font-serif text-2xl font-semibold text-charcoal">Recommended for your goals</h2>
        <Link to="/account/profile#career-goals" className="text-sm font-semibold text-burgundy-600 hover:underline">
          Edit goals
        </Link>
      </div>
      <p className="mt-1 text-sm text-charcoal-600">Based on: {mine.goals.map((g) => g.label).join(', ')}</p>
      <div className="mt-6">
        <CardGrid cards={recommended} onOpen={onOpen} />
      </div>
    </section>
  )
}

export default function CareerHubPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [meta, setMeta] = useState(null)
  // Results are stored with the request they answer, so a stale response is
  // never shown for a newer filter state (and no setState runs synchronously
  // inside the fetch effect).
  const [response, setResponse] = useState({ key: null, data: null, error: null })
  const resultsHeading = useRef(null)

  // The URL is the single source of truth: parse it (validated against the
  // server vocabulary once loaded) on every render.
  const state = useMemo(() => parseHubParams(searchParams, meta), [searchParams, meta])
  const filtering = isFiltering(state)
  const [draftQuery, setDraftQuery] = useState(state.q)
  // Keep the search box in sync when the URL changes (back/forward, reset).
  const [syncedQuery, setSyncedQuery] = useState(state.q)
  if (syncedQuery !== state.q) {
    setSyncedQuery(state.q)
    setDraftQuery(state.q)
  }

  useSeo({ title: 'WSF Career Hub — Practical Tools for Your Next Career Move | Women Shaping Futures', description: DESCRIPTION, canonical: CANONICAL })
  useBreadcrumbStructuredData([{ label: 'Career Hub' }], CANONICAL)

  useEffect(() => {
    trackEvent('career_hub_view')
    let active = true
    fetchCareerHubMeta()
      .then((data) => active && setMeta(data))
      .catch(() => active && setMeta({ goals: [], formats: [], access: [], sorts: [], newThisMonth: [] }))
    return () => {
      active = false
    }
  }, [])

  const requestKey = JSON.stringify(hubRequestParams(state))
  useEffect(() => {
    let active = true
    fetchCareerHub(JSON.parse(requestKey))
      .then((data) => active && setResponse({ key: requestKey, data, error: null }))
      .catch((err) => {
        if (!active) return
        if (err?.apiError?.code === 'invalid_filter') {
          // A stale shared link: drop the filters rather than show an error.
          setSearchParams('', { replace: true })
          return
        }
        setResponse({ key: requestKey, data: null, error: 'Something went wrong loading the Career Hub. Please try again.' })
      })
    return () => {
      active = false
    }
  }, [requestKey, setSearchParams])
  const current = response.key === requestKey ? response : { data: null, error: null }
  const results = current.data
  const error = current.error

  function apply(patch, { scroll = false } = {}) {
    const next = updateHubState(state, patch)
    setSearchParams(buildHubSearch(next).replace(/^\?/, ''))
    for (const [filter, value] of Object.entries(patch)) {
      if (filter !== 'page') trackEvent('career_hub_filter', { filter, value: value || null })
    }
    if (scroll) resultsHeading.current?.focus()
  }

  function reset() {
    setSearchParams('')
    trackEvent('career_hub_filter', { filter: 'reset', value: null })
  }

  const openCard = (card) => trackEvent('career_hub_item_click', { sourceType: card.sourceType, slug: card.slug }, { entityType: card.sourceType, entityId: card.sourceId })
  const goals = meta?.goals || []
  const featuredGoals = goals.filter((g) => g.featured)
  const newThisMonth = !filtering && state.page === 1 ? meta?.newThisMonth || [] : []
  const total = results?.pagination?.totalItems ?? 0

  return (
    <div>
      <section className="border-b border-taupe-200 bg-cream">
        <div className="container-editorial py-14 sm:py-20">
          <p className="eyebrow">{EYEBROW}</p>
          <h1 className="mt-3 max-w-3xl font-serif text-4xl font-semibold leading-tight text-charcoal sm:text-5xl">{TITLE}</h1>
          <p className="mt-4 max-w-2xl text-base text-charcoal-600 sm:text-lg">{DESCRIPTION}</p>

          {featuredGoals.length > 0 && (
            <div className="mt-8">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Start with a goal</h2>
              <ul className="mt-3 flex flex-wrap gap-2">
                {featuredGoals.map((goal) => {
                  const active = state.goal === goal.slug
                  return (
                    <li key={goal.slug}>
                      <button
                        type="button"
                        aria-pressed={active}
                        onClick={() => apply({ goal: active ? '' : goal.slug }, { scroll: true })}
                        className={`min-h-[44px] border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy-600 ${active ? 'border-plum-600 bg-plum-600 text-ivory' : 'border-taupe-300 bg-white text-charcoal hover:border-burgundy-500'}`}
                      >
                        {goal.label}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </div>
      </section>

      <div className="container-editorial py-10">
        <form
          role="search"
          aria-label="Search and filter the Career Hub"
          onSubmit={(e) => {
            e.preventDefault()
            apply({ q: draftQuery }, { scroll: true })
          }}
          className="flex flex-wrap items-end gap-3 border-b border-taupe-200 pb-8"
        >
          <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600 sm:max-w-xs">
            Search
            <span className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2 focus-within:border-burgundy-500">
              <Search size={16} className="shrink-0 text-charcoal-600" aria-hidden="true" />
              <input
                type="search"
                value={draftQuery}
                onChange={(e) => setDraftQuery(e.target.value)}
                maxLength={100}
                className="w-full min-w-0 text-sm font-normal normal-case text-charcoal focus:outline-none"
              />
            </span>
          </label>
          <button type="submit" className="btn-primary min-h-[44px] !px-4 !py-2 text-xs">
            Search
          </button>
          <FilterSelect label="Goal" value={state.goal} onChange={(v) => apply({ goal: v })} options={goals.map((g) => ({ value: g.slug, label: g.label }))} />
          <FilterSelect label="Format" value={state.format} onChange={(v) => apply({ format: v })} options={(meta?.formats || []).map((f) => ({ value: f.slug, label: f.label }))} />
          <FilterSelect label="Access" value={state.access} onChange={(v) => apply({ access: v })} options={(meta?.access || []).map((a) => ({ value: a.slug, label: a.label }))} />
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            Sort
            <select
              value={state.sort}
              onChange={(e) => apply({ sort: e.target.value })}
              className="min-w-[10rem] border border-taupe-300 bg-white px-3 py-2 text-sm font-normal normal-case text-charcoal focus:border-burgundy-500 focus:outline-none"
            >
              {(meta?.sorts?.length ? meta.sorts : [{ slug: 'newest', label: 'Newest' }]).map((s) => (
                <option key={s.slug} value={s.slug}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          {filtering && (
            <button type="button" onClick={reset} className="min-h-[44px] text-sm font-semibold text-burgundy-600 underline-offset-4 hover:underline">
              Reset filters
            </button>
          )}
        </form>

        {!filtering && state.page === 1 && <ForYourGoals goalOptions={goals} onOpen={openCard} />}

        {newThisMonth.length > 0 && (
          <section aria-labelledby="career-hub-new" className="mt-12">
            <h2 id="career-hub-new" className="font-serif text-2xl font-semibold text-charcoal">
              New this month
            </h2>
            <div className="mt-6">
              <CardGrid cards={newThisMonth} onOpen={openCard} />
            </div>
          </section>
        )}

        <section aria-labelledby="career-hub-results" className="mt-12">
          <h2 id="career-hub-results" ref={resultsHeading} tabIndex={-1} className="font-serif text-2xl font-semibold text-charcoal focus:outline-none">
            {filtering ? 'Matching tools' : 'All tools'}
          </h2>
          <p className="sr-only" aria-live="polite">
            {results ? describeResults(total, state, meta) : ''}
          </p>
          <div className="mt-6">
            {error && <EmptyState title="Couldn't load the Career Hub" description={error} />}
            {!error && results === null && <PageLoader />}
            {!error && results !== null &&
              (results.items.length ? (
                <>
                  <CardGrid cards={results.items} onOpen={openCard} />
                  <Pagination pagination={results.pagination} onPageChange={(page) => apply({ page }, { scroll: true })} />
                </>
              ) : state.page > 1 && total > 0 ? (
                <EmptyState
                  title="There are no more tools on this page."
                  action={
                    <button type="button" onClick={() => apply({ page: 1 }, { scroll: true })} className="btn-secondary mt-6 !px-4 !py-2 text-xs">
                      Back to the first page
                    </button>
                  }
                />
              ) : (
                <EmptyState
                  title="No tools match these filters yet."
                  description="Try a different goal, format or search term."
                  action={
                    filtering ? (
                      <button type="button" onClick={reset} className="btn-secondary mt-6 !px-4 !py-2 text-xs">
                        Reset filters
                      </button>
                    ) : null
                  }
                />
              ))}
          </div>
        </section>

        <section className="mt-16 border border-plum-600/20 bg-plum-700 px-6 py-10 text-ivory sm:px-10">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ivory/80">
            <Sparkles size={14} aria-hidden="true" /> WSF Circle
          </p>
          <h2 className="mt-3 max-w-2xl font-serif text-3xl font-semibold">Go further with WSF Circle.</h2>
          <p className="mt-3 max-w-2xl text-sm text-ivory/85 sm:text-base">
            Members get the Circle tools, courses and challenges marked “Included with WSF Circle”, plus member-only opportunities, events and
            community. Premium tools can still be bought on their own.
          </p>
          <Link to="/circle" className="mt-6 inline-flex min-h-[44px] items-center gap-2 bg-ivory px-5 py-2 text-sm font-semibold text-plum-700 hover:bg-cream">
            Explore WSF Circle <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </section>
      </div>
    </div>
  )
}
