import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { loadHomepageModules } from '../features/site/siteSlice'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import HeroModule from '../components/home/HeroModule'
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
import SponsorPlacementStrip from '../components/sponsors/SponsorPlacementStrip'

// Maps each CMS module `type` to its renderer. Adding a new homepage block
// type in the CMS only requires registering it here — no page rewrite.
const MODULE_COMPONENTS = {
  hero: HeroModule,
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
}

export default function HomePage() {
  const dispatch = useDispatch()
  const { homepageModules, homepageStatus } = useSelector((s) => s.site)

  useEffect(() => {
    if (homepageStatus === 'idle') dispatch(loadHomepageModules())
  }, [homepageStatus, dispatch])

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
      {/* Real Sponsors CMS placements — separate from the "partners" module
          above (general, undisclosed collaborators), since these are paid
          and carry an explicit disclosure label. Renders nothing when no
          sponsor is configured for this placement. */}
      <SponsorPlacementStrip placementKey="homepage_featured" heading="Our Sponsors" />
    </div>
  )
}
