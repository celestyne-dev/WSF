import { mapLearningProgram } from '../../api/learning'
import LearningProgramCard from '../cards/LearningProgramCard'
import SectionHeading from '../ui/SectionHeading'
import SectionCtaLink from './SectionCtaLink'

// "From WSF Learning": published programs resolved by the server, shown with
// the shared card (format, lessons, duration, Free / WSF Circle / Premium,
// Included with WSF Lifetime). Access itself stays enforced by the API.
export default function LearningModule({ module }) {
  const programs = (module.initialData?.items || []).map(mapLearningProgram)
  if (!programs.length) return null
  return (
    <section className="border-t border-taupe-200 bg-cream py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow={module.eyebrow || 'From WSF Learning'} heading={module.heading} subheading={module.subheading} viewAllHref="/learning" />
        <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-3">
          {programs.map((program) => (
            <LearningProgramCard key={program.id} program={program} />
          ))}
        </div>
        <SectionCtaLink label={module.ctaLabel} url={module.ctaUrl} />
      </div>
    </section>
  )
}
