import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import NewsletterForm from '../components/ui/NewsletterForm'

const TRACKS = [
  { title: 'Find a Mentor', description: 'Get matched with a woman in your industry, one step ahead of where you are now.' },
  { title: 'Become a Mentor', description: 'Give back an hour a month to someone building the career you’ve already built.' },
  { title: 'Mentorship Circles', description: 'Small peer groups of 5-6 women, meeting monthly, for structured accountability.' },
  { title: 'Mentorship Programmes', description: 'Structured, cohort-based mentorship in partnership with employers and universities.' },
]

export default function MentorshipPage() {
  useSeo({
    title: 'Mentorship | Women Shaping Futures',
    description: 'Find a mentor, become a mentor, or join a WSF mentorship circle.',
    canonical: 'https://womenshapingfutures.org/mentorship',
  })

  return (
    <div>
      <PageHeader eyebrow="Mentorship" title="Mentorship at WSF" description="We're building a structured mentorship programme connecting women across industries and career stages. Join the waitlist to be first in line." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          {TRACKS.map((t) => (
            <div key={t.title} className="border border-taupe-200 bg-white p-6">
              <h3 className="font-serif text-xl font-semibold text-charcoal">{t.title}</h3>
              <p className="mt-2 text-sm text-charcoal-600">{t.description}</p>
            </div>
          ))}
        </div>
        <div className="mt-14 border-t border-taupe-200 pt-10 text-center">
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Join the mentorship waitlist</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-charcoal-600">Be the first to know when applications open for mentors and mentees.</p>
          <div className="mt-5 flex justify-center">
            <NewsletterForm source="mentorship-waitlist" />
          </div>
        </div>
      </div>
    </div>
  )
}
