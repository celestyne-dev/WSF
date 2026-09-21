import { useEffect, useState } from 'react'
import { fetchAuthors } from '../api/taxonomies'
import { fetchAudienceStats } from '../api/site'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import MediaImage from '../components/ui/MediaImage'

export default function AboutPage() {
  const [authors, setAuthors] = useState([])
  const [stats, setStats] = useState(null)

  useEffect(() => {
    let active = true
    fetchAuthors()
      .then((data) => active && setAuthors(data))
      .catch(() => {})
    fetchAudienceStats()
      .then((data) => active && setStats(data))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: 'About Women Shaping Futures',
    description: 'Women Shaping Futures is a global media, opportunity, and community platform for ambitious women.',
    canonical: 'https://womenshapingfutures.org/about',
  })

  return (
    <div>
      <PageHeader
        eyebrow="About Us"
        title="A platform built to move women forward"
        description={
          stats
            ? `Women Shaping Futures started in 2019 as a small LinkedIn page sharing stories of women in business. Today, we're a global editorial and opportunity platform reaching more than ${new Intl.NumberFormat('en-US').format(stats.linkedinFollowers)} people across ${stats.countriesReached} countries, with particularly strong readership in the United States.`
            : "Women Shaping Futures started in 2019 as a small LinkedIn page sharing stories of women in business. Today, we're a global editorial and opportunity platform reaching women worldwide."
        }
      />

      <div className="container-editorial max-w-reading py-14">
        <h2 className="font-serif text-2xl font-semibold text-charcoal">Our mission</h2>
        <p className="mt-4 text-lg leading-relaxed text-charcoal-600">
          We exist to amplify women's stories, connect women with opportunity, and equip them with the resources to lead, grow, and shape their own
          futures. We believe representation matters — but representation without access to jobs, mentors, and capital is incomplete. That's why
          we built more than a media brand: a platform spanning journalism, community, opportunity, and education.
        </p>

        <h2 className="mt-10 font-serif text-2xl font-semibold text-charcoal">What we do</h2>
        <ul className="mt-4 list-disc space-y-2 pl-5 text-base text-charcoal-600">
          <li><strong className="text-charcoal">Inspire</strong> — profiles, interviews, and stories of women shaping their industries.</li>
          <li><strong className="text-charcoal">Inform</strong> — original journalism, guides, and expert-driven advice.</li>
          <li><strong className="text-charcoal">Connect</strong> — a directory of people, mentors, organizations, and events.</li>
          <li><strong className="text-charcoal">Educate</strong> — resources, workshops, and learning tracks.</li>
          <li><strong className="text-charcoal">Create opportunity</strong> — jobs, grants, scholarships, and fellowships.</li>
        </ul>

        <h2 className="mt-10 font-serif text-2xl font-semibold text-charcoal">Editorial standards</h2>
        <p className="mt-4 text-lg leading-relaxed text-charcoal-600">
          Every story we publish is fact-checked and edited to a professional publishing standard. Sponsored content is always clearly disclosed and
          never disguised as independent editorial. Read our full Editorial Policy for details on sourcing, corrections, and disclosure.
        </p>
      </div>

      <div className="border-t border-taupe-200 bg-cream py-14">
        <div className="container-editorial">
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Our team</h2>
          <div className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
            {authors.map((a) => (
              <div key={a.id} className="text-center">
                <MediaImage mediaPath={a.photo} alt={a.name} width={200} height={200} aspect={1} className="mx-auto h-20 w-20 rounded-full object-cover" />
                <p className="mt-2 font-serif text-sm font-semibold text-charcoal">{a.name}</p>
                <p className="text-xs text-charcoal-600">{a.role}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
