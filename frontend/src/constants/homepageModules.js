// Mirrors backend/app/models/cms.py's HOMEPAGE_MODULE_TYPES /
// HOMEPAGE_MODULE_ITEM_COUNT_BOUNDS / HOMEPAGE_SPONSOR_PLACEMENT_KEYS —
// the controlled registry both AdminHomepageBuilder's "Add section" menu
// and its per-module field UI key off of. Keeping the two lists in sync is
// a manual convention (like RESERVED_SLUGS), not shared code, since the
// frontend has no build step that reads Python.
//
// `contentSource` tells the module editor which selector(s) to render:
//  - 'manual-hero'      Article (lead) + Articles (secondary), or a fully
//                        editorial fallback (heading/media/CTA only)
//  - 'manual-articles'  ordered multi-select of Articles
//  - 'manual-person'    single Person
//  - 'manual-series'    single Series
//  - 'manual-topic'     single Topic
//  - 'manual-orgs'      ordered multi-select of Organizations
//  - 'dynamic'          no selection — backend query, only itemCount/heading
//  - 'cta'              heading/subheading/media/CTA only, no content query
//  - 'sponsor'          a single controlled placement key
//  - 'none'             heading/subheading only (newsletter)
export const HOMEPAGE_MODULE_REGISTRY = {
  hero: { label: 'Hero', singleton: true, contentSource: 'manual-hero', hasCta: true, hasSecondaryCta: true, hasMedia: true },
  featured_stories: { label: 'Featured Stories', contentSource: 'manual-articles', hasItemCount: true, itemCountBounds: [1, 8] },
  latest_stories: { label: 'Latest Stories', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 12] },
  featured_woman: { label: 'Women / People Spotlight', contentSource: 'manual-person' },
  series_feature: { label: 'Series Feature', contentSource: 'manual-series', hasItemCount: true, itemCountBounds: [1, 6] },
  topic_collection: { label: 'Topic Stories', contentSource: 'manual-topic', hasItemCount: true, itemCountBounds: [1, 6] },
  opportunities: { label: 'Opportunities', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 6] },
  jobs: { label: 'Jobs / Careers', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 6] },
  events: { label: 'Events', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 6] },
  resources: { label: 'Resources', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 6] },
  newsletter: { label: 'Newsletter CTA', contentSource: 'none' },
  partners: { label: 'Partner Logos', contentSource: 'manual-orgs' },
  community_cta: { label: 'Community CTA', contentSource: 'cta', hasCta: true, hasMedia: true },
  mentorship_cta: { label: 'Mentorship CTA', contentSource: 'cta', hasCta: true, hasMedia: true },
  editorial_callout: { label: 'Editorial Callout', contentSource: 'cta', hasCta: true, hasMedia: true },
  sponsor_placement: { label: 'Sponsor Placement', contentSource: 'sponsor' },
}

export const HOMEPAGE_SPONSOR_PLACEMENT_KEYS = ['homepage_featured']

export function newModuleDefaults(type) {
  return { type, enabled: true, heading: null, subheading: null, config: {} }
}
