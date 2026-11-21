// Studio-only review prompts for the core legal system Pages. It writes
// nothing and does not judge the wording: each item is a question to check
// against what WSF actually does. Ticking boxes is NOT evidence that a
// policy satisfies any law; qualified legal review is still needed.
// Backed by the read-only `flask legal-pages-audit` report.

const POLICY_CHECKLISTS = {
  privacy: [
    'What information WSF collects (accounts, forms, purchases)',
    'Why each kind of information is collected',
    'Accounts and sign-in',
    'Newsletter signups (single opt-in; signup time and wording version recorded)',
    'Purchases and payments (Paystack hosted checkout)',
    'Career Goals and other saved preferences',
    'Story submissions and nominations',
    'Event registrations',
    'Jobs and Opportunities (WSF links out; employers handle applications)',
    'Analytics and cookies (see the Cookie Policy)',
    'Third parties and processors actually used',
    'International transfers, if they apply',
    'How long data is kept',
    'How data is kept secure',
    'People’s rights and how to use them',
    'Opting out of marketing emails',
    'Children',
    'Contact and complaints',
    'How policy updates are announced',
  ],
  cookies: [
    'Essential technologies (sign-in, security, checkout, consent choice)',
    'Analytics technologies, only if enabled (WSF’s own events; no third-party analytics is active)',
    'Marketing technologies, only if enabled (embedded video players)',
    'Preference storage',
    'Provider of each technology',
    'Purpose of each technology',
    'Duration where known (do not invent cookie names or expiry times)',
    'How to change consent (“Cookie settings” in the footer)',
  ],
  terms: [
    'Accounts',
    'Digital products',
    'WSF Circle',
    'WSF Lifetime',
    'Learning',
    'Certificates of Completion (what they do and do not certify)',
    'Third-party Jobs and Opportunities',
    'External links',
    'Submissions',
    'Intellectual property',
    'Acceptable use',
    'Refunds and payment terms, where they actually apply',
    'Limitations and disclaimers',
    'Termination',
    'Governing law and disputes (needs legal review)',
  ],
  'editorial-policy': [
    'Sourcing and fact-checking',
    'Corrections',
    'Sponsored content and disclosures',
    'Use of AI in editorial work',
    'Independence and conflicts of interest',
  ],
}

export default function PolicyReviewPanel({ pageKey }) {
  const items = POLICY_CHECKLISTS[pageKey]
  if (!items) return null
  return (
    <details className="rounded-card border border-taupe-200 bg-cream p-4">
      <summary className="cursor-pointer text-sm font-semibold text-charcoal">Policy review prompts ({items.length})</summary>
      <p className="mt-2 text-xs text-charcoal-600">
        Questions to check this page against what WSF actually does. They write nothing and are not a compliance check;
        qualified legal review is still needed. A matching report is available from <code>flask legal-pages-audit</code>.
      </p>
      <ul className="mt-3 space-y-1.5 text-sm text-charcoal-700">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden="true" className="text-charcoal-600">–</span>
            <span>Does it cover: {item}?</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
