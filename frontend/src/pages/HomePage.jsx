import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { loadHomepageModules, clearHomepageBootstrapLead } from '../features/site/siteSlice'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import HeroModule from '../components/home/HeroModule'
import FeaturedStoriesModule from '../components/home/FeaturedStoriesModule'
import LatestStoriesModule from '../components/home/LatestStoriesModule'
import FeaturedWomanModule from '../components/home/FeaturedWomanModule'
import SeriesFeatureModule from '../components/home/SeriesFeatureModule'
import OpportunitiesModule from '../components/home/OpportunitiesModule'
import JobsModule from '../components/home/JobsModule'
import TopicCollectionModule from '../components/home/TopicCollectionModule'
import ResourcesModule from '../components/home/ResourcesModule'
import EventsModule from '../components/home/EventsModule'
import NewsletterModule from '../components/home/NewsletterModule'
import PartnersModule from '../components/home/PartnersModule'
import CommunityCtaModule from '../components/home/CommunityCtaModule'
import MentorshipCtaModule from '../components/home/MentorshipCtaModule'
import EditorialCalloutModule from '../components/home/EditorialCalloutModule'
import SponsorPlacementModule from '../components/home/SponsorPlacementModule'

// Maps each CMS module `type` to its renderer. Adding a new homepage block
// type in the CMS only requires registering it here (and in the shared
// HOMEPAGE_MODULE_TYPES allow-list on the backend) — no page rewrite. An
// unrecognized `type` (should never happen — the backend validates against
// the same registry) is skipped rather than crashing the page.
const MODULE_COMPONENTS = {
  hero: HeroModule,
  featured_stories: FeaturedStoriesModule,
  latest_stories: LatestStoriesModule,
  featured_woman: FeaturedWomanModule,
  series_feature: SeriesFeatureModule,
  opportunities: OpportunitiesModule,
  jobs: JobsModule,
  topic_collection: TopicCollectionModule,
  resources: ResourcesModule,
  events: EventsModule,
  newsletter: NewsletterModule,
  partners: PartnersModule,
  community_cta: CommunityCtaModule,
  mentorship_cta: MentorshipCtaModule,
  editorial_callout: EditorialCalloutModule,
  sponsor_placement: SponsorPlacementModule,
}

export default function HomePage() {
  const dispatch = useDispatch()
  const { homepageModules, homepageStatus } = useSelector((s) => s.site)

  useEffect(() => {
    if (homepageStatus === 'idle') dispatch(loadHomepageModules())
  }, [homepageStatus, dispatch])

  // WSF SEO Phase 2D correction — `state.site.leadArticle` only ever
  // means "the server's homepage bootstrap resolved this Article for
  // THIS hard load" (see store/index.js's preloadedState and
  // HeroModule.jsx, which reads it before falling back to its own
  // fetch). It must not outlive this one homepage visit: this effect's
  // only job is to dispatch the narrow clearHomepageBootstrapLead()
  // reducer on unmount, so a later SPA navigation back to "/" finds it
  // already null and HeroModule takes its normal fetchArticleBySlug
  // path instead of reusing a stale bootstrap Article. Deliberately its
  // own effect with a dependency array of just `dispatch` — never tied
  // to homepageStatus or anything else that changes while the page is
  // still mounted, and never run on mount (only its cleanup matters).
  useEffect(() => {
    return () => {
      dispatch(clearHomepageBootstrapLead())
    }
  }, [dispatch])

  useSeo({
    title: 'Women Shaping Futures — Stories, Opportunity & Growth for Women Worldwide',
    description:
      'Women Shaping Futures is a global media and opportunity platform amplifying women’s stories and connecting women to jobs, mentorship, and growth.',
    canonical: 'https://womenshapingfutures.org/',
  })

  if (homepageStatus === 'loading' || homepageStatus === 'idle') return <PageLoader />

  return (
    <div>
      {homepageModules.map((module) => {
        const Component = MODULE_COMPONENTS[module.type]
        if (!Component) return null
        return <Component key={module.id} module={module} />
      })}
    </div>
  )
}
