import { mapPerson } from '../../api/people'
import PersonCard from '../cards/PersonCard'
import SectionHeading from '../ui/SectionHeading'
import SectionCtaLink from './SectionCtaLink'

// "Women Moving Industries" (heading is CMS-editable): People, not Article
// cards. Items are resolved by the server (published profiles only).
export default function PeopleSpotlightModule({ module }) {
  const people = (module.initialData?.items || []).map(mapPerson)
  if (!people.length) return null
  return (
    <section className="border-t border-taupe-200 py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow={module.eyebrow || 'Women moving industries'} heading={module.heading} subheading={module.subheading} />
        <div className="mt-8 grid grid-cols-2 gap-x-6 gap-y-10 lg:grid-cols-4">
          {people.map((person) => (
            <PersonCard key={person.id} person={person} />
          ))}
        </div>
        <SectionCtaLink label={module.ctaLabel} url={module.ctaUrl} />
      </div>
    </section>
  )
}
