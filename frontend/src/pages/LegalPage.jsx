import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

// CMS-managed legal content in production (Page/PageSection models). Content
// here stands in for what an admin would author in Settings > Legal Pages.
const DOCS = {
  privacy: {
    title: 'Privacy Policy',
    intro: 'This Privacy Policy explains what information Women Shaping Futures collects, how we use it, and the choices you have.',
    sections: [
      { heading: 'Information we collect', body: 'We collect information you provide directly (such as newsletter sign-ups, story submissions, and account details) and information collected automatically (such as pages visited and device data).' },
      { heading: 'How we use your information', body: 'We use your information to deliver our newsletter, personalize content, respond to inquiries, and improve our platform.' },
      { heading: 'Your choices', body: 'You may unsubscribe from our newsletter at any time and request deletion of your personal data by contacting privacy@womenshapingfutures.org.' },
    ],
  },
  terms: {
    title: 'Terms of Use',
    intro: 'By accessing Women Shaping Futures, you agree to these Terms of Use.',
    sections: [
      { heading: 'Use of content', body: 'Content on this site is for personal, non-commercial use. Republishing requires written permission.' },
      { heading: 'User submissions', body: 'By submitting a story or nomination, you grant Women Shaping Futures a license to edit and publish the content if selected.' },
      { heading: 'Limitation of liability', body: 'Women Shaping Futures is not liable for outcomes related to third-party jobs, opportunities, or events listed on this platform.' },
    ],
  },
  cookies: {
    title: 'Cookie Policy',
    intro: 'We use cookies to operate our website, remember your preferences, and understand how our platform is used.',
    sections: [
      { heading: 'Essential cookies', body: 'Required for core site functionality, such as navigation and account access.' },
      { heading: 'Analytics cookies', body: 'Help us understand traffic patterns so we can improve our content and platform.' },
      { heading: 'Managing cookies', body: 'You can control cookies through your browser settings at any time.' },
    ],
  },
  'editorial-policy': {
    title: 'Editorial Policy',
    intro: 'Women Shaping Futures is committed to accurate, fair, and transparent journalism.',
    sections: [
      { heading: 'Sourcing & fact-checking', body: 'Every published article is reviewed by an editor and fact-checked against primary sources where possible.' },
      { heading: 'Sponsored content disclosure', body: 'Sponsored articles are clearly labeled and never presented as independent editorial judgment.' },
      { heading: 'Corrections', body: 'We correct errors promptly and transparently. Report a correction to editorial@womenshapingfutures.org.' },
    ],
  },
}

export default function LegalPage({ docKey }) {
  const doc = DOCS[docKey] || DOCS.privacy

  useSeo({
    title: `${doc.title} | Women Shaping Futures`,
    description: doc.intro,
    canonical: `https://womenshapingfutures.org/${docKey}`,
  })

  return (
    <div>
      <PageHeader eyebrow="Legal" title={doc.title} description={doc.intro} />
      <div className="container-editorial max-w-reading space-y-8 py-14">
        {doc.sections.map((s) => (
          <div key={s.heading}>
            <h2 className="font-serif text-xl font-semibold text-charcoal">{s.heading}</h2>
            <p className="mt-2 text-base leading-relaxed text-charcoal-600">{s.body}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
