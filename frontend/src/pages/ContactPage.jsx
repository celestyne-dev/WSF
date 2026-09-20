import { Mail, MapPin } from 'lucide-react'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

export default function ContactPage() {
  useSeo({
    title: 'Contact | Women Shaping Futures',
    description: 'Get in touch with the Women Shaping Futures editorial, partnerships, and support teams.',
    canonical: 'https://womenshapingfutures.org/contact',
  })

  return (
    <div>
      <PageHeader eyebrow="Contact" title="Get in Touch" description="Reach the right team, faster." />
      <div className="container-editorial grid grid-cols-1 gap-6 py-14 sm:grid-cols-3">
        {[
          { team: 'Editorial', email: 'editorial@womenshapingfutures.org', note: 'Story tips, corrections, and press inquiries.' },
          { team: 'Partnerships', email: 'partnerships@womenshapingfutures.org', note: 'Sponsorships, advertising, and brand collaborations.' },
          { team: 'General', email: 'hello@womenshapingfutures.org', note: 'Everything else, including account support.' },
        ].map((c) => (
          <div key={c.team} className="border border-taupe-200 bg-white p-6">
            <h3 className="font-serif text-lg font-semibold text-charcoal">{c.team}</h3>
            <p className="mt-2 text-sm text-charcoal-600">{c.note}</p>
            <a href={`mailto:${c.email}`} className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-burgundy-600 hover:underline">
              <Mail size={14} /> {c.email}
            </a>
          </div>
        ))}
      </div>
      <div className="container-editorial flex items-center gap-2 pb-14 text-sm text-charcoal-600">
        <MapPin size={16} /> Nairobi, Kenya — serving a global audience
      </div>
    </div>
  )
}
