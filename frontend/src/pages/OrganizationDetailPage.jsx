import { useParams } from 'react-router-dom'
import { Globe } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { getOrganizationBySlug } from '../mock/organizations'
import { getCountryName } from '../mock/geography'
import { jobs } from '../mock/jobs'
import { opportunities } from '../mock/opportunities'
import { people } from '../mock/people'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import JobCard from '../components/cards/JobCard'
import OpportunityCard from '../components/cards/OpportunityCard'
import PersonCard from '../components/cards/PersonCard'
import NotFoundPage from './NotFoundPage'

export default function OrganizationDetailPage() {
  const { slug } = useParams()
  const org = getOrganizationBySlug(slug)
  if (!org) return <NotFoundPage />

  const orgJobs = jobs.filter((j) => j.companySlug === slug)
  const orgOpportunities = opportunities.filter((o) => o.organizationSlug === slug)
  const orgPeople = people.filter((p) => p.organizationSlug === slug)

  useSeo({
    title: `${org.name} | Women Shaping Futures`,
    description: org.description,
    canonical: `https://womenshapingfutures.org/organizations/${org.slug}`,
  })

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Organizations', to: '/organizations' }, { label: org.name }]} />
          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            <MediaImage mediaPath={org.logo} alt={`${org.name} logo`} width={200} height={200} aspect={1} className="h-24 w-24 border border-taupe-200 object-cover" />
            <div>
              <h1 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{org.name}</h1>
              <p className="mt-1 text-base text-charcoal-600">
                {org.industry} &middot; {getCountryName(org.countryCode)} &middot; {org.type}
              </p>
              <div className="mt-3 flex gap-4">
                {org.website && (
                  <a href={org.website} target="_blank" rel="noreferrer" aria-label="Website" className="text-charcoal-600 hover:text-burgundy-600">
                    <Globe size={17} />
                  </a>
                )}
                {org.social.linkedin && (
                  <a href={`https://linkedin.com/company/${org.social.linkedin}`} target="_blank" rel="noreferrer" aria-label="LinkedIn" className="text-charcoal-600 hover:text-burgundy-600">
                    <SocialIcon name="linkedin" size={17} />
                  </a>
                )}
                {org.social.twitter && (
                  <a href={`https://twitter.com/${org.social.twitter}`} target="_blank" rel="noreferrer" aria-label="Twitter" className="text-charcoal-600 hover:text-burgundy-600">
                    <SocialIcon name="twitter" size={17} />
                  </a>
                )}
              </div>
            </div>
          </div>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-charcoal-600">{org.description}</p>
        </div>
      </div>

      <div className="container-editorial space-y-14 py-14">
        {orgPeople.length > 0 && (
          <div>
            <p className="eyebrow mb-5">People at {org.name}</p>
            <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
              {orgPeople.map((p) => (
                <PersonCard key={p.slug} person={p} />
              ))}
            </div>
          </div>
        )}
        {orgJobs.length > 0 && (
          <div>
            <p className="eyebrow mb-5">Open roles</p>
            <div className="grid grid-cols-1 gap-4">
              {orgJobs.map((j) => (
                <JobCard key={j.id} job={j} />
              ))}
            </div>
          </div>
        )}
        {orgOpportunities.length > 0 && (
          <div>
            <p className="eyebrow mb-5">Opportunities</p>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
              {orgOpportunities.map((o) => (
                <OpportunityCard key={o.id} opportunity={o} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
