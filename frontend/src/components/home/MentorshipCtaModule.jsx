import CalloutModule from './CalloutModule'

export default function MentorshipCtaModule({ module }) {
  return <CalloutModule module={module} defaultCtaLabel="Explore mentorship" defaultCtaUrl="/mentorship" tone="light" />
}
