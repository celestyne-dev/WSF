import { mapArticle } from '../../api/articles'
import { mapEvent } from '../../api/events'
import { mapJob } from '../../api/jobs'
import { mapLearningProgram } from '../../api/learning'
import { mapOpportunity } from '../../api/opportunities'
import { mapPerson } from '../../api/people'
import { mapResource } from '../../api/resources'
import ArticleCard from '../cards/ArticleCard'
import EventCard from '../cards/EventCard'
import JobCard from '../cards/JobCard'
import LearningProgramCard from '../cards/LearningProgramCard'
import OpportunityCard from '../cards/OpportunityCard'
import PersonCard from '../cards/PersonCard'
import ResourceCard from '../cards/ResourceCard'
import SectionHeading from '../ui/SectionHeading'
import SectionCtaLink from './SectionCtaLink'

// entity type -> [mapper, card renderer]; every card is the one that
// entity's own listing pages already use.
const ENTITY_RENDERERS = {
  articles: [mapArticle, (item, layout) => <ArticleCard article={item} variant={layout === 'compact' ? 'compact' : 'grid'} />],
  people: [mapPerson, (item) => <PersonCard person={item} />],
  opportunities: [mapOpportunity, (item) => <OpportunityCard opportunity={item} />],
  jobs: [mapJob, (item) => <JobCard job={item} />],
  events: [mapEvent, (item) => <EventCard event={item} />],
  resources: [mapResource, (item) => <ResourceCard resource={item} />],
  learning: [mapLearningProgram, (item) => <LearningProgramCard program={item} />],
}

const GRID = {
  grid: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  compact: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
}

/**
 * Content Collection — a configured set of one entity type. Items arrive
 * resolved from the server with public anonymous visibility already
 * applied (no extra request here); an empty result renders nothing.
 */
export default function ContentCollectionModule({ module }) {
  const entityType = module.resolved?.entityType || module.entityType
  const renderer = ENTITY_RENDERERS[entityType]
  const raw = module.resolved?.items || []
  if (!renderer || raw.length === 0) return null
  const [map, render] = renderer
  const layout = module.layout === 'compact' ? 'compact' : 'grid'
  const items = raw.map(map)
  return (
    <section className="border-t border-taupe-200 py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow={module.eyebrow} heading={module.heading} subheading={module.subheading} />
        <div className={`mt-8 grid gap-6 ${GRID[layout]}`}>
          {items.map((item) => (
            <div key={item.id ?? item.slug} className="min-w-0">
              {render(item, layout)}
            </div>
          ))}
        </div>
        <SectionCtaLink label={module.ctaLabel} url={module.ctaUrl} />
      </div>
    </section>
  )
}
