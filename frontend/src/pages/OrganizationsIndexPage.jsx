import { useEffect, useState } from 'react'
import { fetchOrganizations } from '../api/taxonomies'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import OrganizationCard from '../components/cards/OrganizationCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

export default function OrganizationsIndexPage() {
  const [organizations, setOrganizations] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Organizations | Women Shaping Futures',
    description: 'Companies, foundations, universities, and institutions in the Women Shaping Futures network.',
    canonical: 'https://womenshapingfutures.org/organizations',
  })

  useEffect(() => {
    let active = true
    fetchOrganizations()
      .then((data) => active && setOrganizations(data))
      .catch(() => active && setError('Something went wrong loading organizations. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  return (
    <div>
      <PageHeader eyebrow="Network" title="Organizations" description="Companies, foundations, and institutions hiring, funding, and partnering with women across our network." />
      <div className="container-editorial py-14">
        {error && <EmptyState title="Couldn't load organizations" description={error} />}
        {!error && organizations === null && <PageLoader />}
        {!error && organizations !== null && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {organizations.map((org) => (
              <OrganizationCard key={org.id} organization={org} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
