import CalloutModule from './CalloutModule'

export default function CommunityCtaModule({ module }) {
  return <CalloutModule module={module} defaultCtaLabel="Join the community" defaultCtaUrl="/community" tone="dark" />
}
