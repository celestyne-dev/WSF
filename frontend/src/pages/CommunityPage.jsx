import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import NewsletterForm from '../components/ui/NewsletterForm'

const FEATURES = [
  'Member profiles and a searchable member directory',
  'Private discussion groups by industry and career stage',
  'Saved articles, jobs, and opportunities',
  'Members-only networking events',
  'Early access to event registration and premium resources',
]

export default function CommunityPage() {
  useSeo({
    title: 'Community | Women Shaping Futures',
    description: 'The Women Shaping Futures community — connect with women across industries and career stages.',
    canonical: 'https://womenshapingfutures.org/community',
  })

  return (
    <div>
      <PageHeader eyebrow="Community" title="The WSF Community" description="More than 130,000 women follow Women Shaping Futures across social media. We're building a home for that community on our own platform." />
      <div className="container-editorial grid grid-cols-1 gap-10 py-14 lg:grid-cols-2">
        <div>
          <h2 className="font-serif text-2xl font-semibold text-charcoal">What's coming</h2>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-base text-charcoal-600">
            {FEATURES.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
        <div className="border border-taupe-200 bg-cream p-8 text-center">
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Be first in line</h2>
          <p className="mt-2 text-sm text-charcoal-600">Join the newsletter to be notified when community membership opens.</p>
          <div className="mt-5 flex justify-center">
            <NewsletterForm source="community-waitlist" />
          </div>
        </div>
      </div>
    </div>
  )
}
