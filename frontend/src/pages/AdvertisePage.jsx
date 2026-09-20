import { Link } from 'react-router-dom'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

const SLOTS = [
  { key: 'header_leaderboard', label: 'Header Leaderboard', description: 'Site-wide placement below the utility bar.' },
  { key: 'homepage_top', label: 'Homepage Top', description: 'First placement below the lead story.' },
  { key: 'homepage_middle', label: 'Homepage Middle', description: 'Between editorial modules on the homepage.' },
  { key: 'article_top', label: 'Article Top', description: 'Above the fold on every article page.' },
  { key: 'article_sidebar', label: 'Article Sidebar', description: 'Persistent sidebar placement on desktop.' },
  { key: 'jobs_sidebar', label: 'Jobs Sidebar', description: 'High-intent placement for employer brands.' },
  { key: 'newsletter_banner', label: 'Newsletter Banner', description: 'Featured banner in every WSF Weekly send.' },
]

export default function AdvertisePage() {
  useSeo({
    title: 'Advertise | Women Shaping Futures',
    description: 'Advertising placements across Women Shaping Futures — homepage, articles, jobs, and our weekly newsletter.',
    canonical: 'https://womenshapingfutures.org/advertise',
  })

  return (
    <div>
      <PageHeader eyebrow="Advertise" title="Advertise With Women Shaping Futures" description="Direct, sponsorship, and house-campaign placements across a trusted editorial platform." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {SLOTS.map((slot) => (
            <div key={slot.key} className="border border-taupe-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-burgundy-600">{slot.key}</p>
              <h3 className="mt-1 font-serif text-lg font-semibold text-charcoal">{slot.label}</h3>
              <p className="mt-1 text-sm text-charcoal-600">{slot.description}</p>
            </div>
          ))}
        </div>
        <p className="mt-10 text-sm text-charcoal-600">
          For rates and availability, visit our{' '}
          <Link to="/partnerships" className="font-semibold text-burgundy-600 hover:underline">
            Partnerships page
          </Link>{' '}
          or request a media kit.
        </p>
      </div>
    </div>
  )
}
