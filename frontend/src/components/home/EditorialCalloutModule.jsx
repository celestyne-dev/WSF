import CalloutModule from './CalloutModule'

/**
 * A simple editorial CTA/callout — heading, description, optional image,
 * one CTA. Deliberately the plainest module in the registry: no rich
 * text, no arbitrary HTML (see spec's "no arbitrary HTML builder").
 */
export default function EditorialCalloutModule({ module }) {
  return <CalloutModule module={module} tone="light" />
}
