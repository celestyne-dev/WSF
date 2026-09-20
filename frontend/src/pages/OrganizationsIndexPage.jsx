import { organizations } from '../mock/organizations'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import OrganizationCard from '../components/cards/OrganizationCard'

export default function OrganizationsIndexPage() {
  useSeo({
    title: 'Organizations | Women Shaping Futures',
    description: 'Companies, foundations, universities, and institutions in the Women Shaping Futures network.',
    canonical: 'https://womenshapingfutures.org/organizations',
  })

  return (
    <div>
      <PageHeader eyebrow="Network" title="Organizations" description="Companies, foundations, and institutions hiring, funding, and partnering with women across our network." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {organizations.map((org) => (
            <OrganizationCard key={org.id} organization={org} />
          ))}
        </div>
      </div>
    </div>
  )
}
