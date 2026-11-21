import { newCollectionConfig, newPathwayCard } from '../utils/homepageCollections'

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
//  - 'pathways'         eyebrow + 2–8 editor-written destination cards
//  - 'collection'       one entity type, manual picks or automatic query
//    (both: see utils/homepageCollections.js)
export const HOMEPAGE_MODULE_REGISTRY = {
  hero: { label: 'Hero', singleton: true, contentSource: 'manual-hero', hasCta: true, hasSecondaryCta: true, hasMedia: true },
  featured_stories: { label: 'Featured Stories', contentSource: 'manual-articles', hasItemCount: true, itemCountBounds: [1, 8] },
  latest_stories: { label: 'Fresh This Week / Latest Stories', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 12] },
  featured_woman: { label: 'Women / People Spotlight', contentSource: 'manual-person' },
  series_feature: { label: 'Series Feature', contentSource: 'manual-series', hasItemCount: true, itemCountBounds: [1, 6] },
  topic_collection: { label: 'Topic Stories', contentSource: 'manual-topic', hasItemCount: true, itemCountBounds: [1, 6] },
  opportunities: { label: 'Funding & Opportunities', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 6], sorts: [['featured', 'Featured open opportunities'], ['closing_soon', 'Closing soonest'], ['upcoming', 'Opening soon (upcoming)']] },
  jobs: { label: 'Jobs / Jobs Closing Soon', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 6], sorts: [['featured', 'Featured open jobs'], ['closing_soon', 'Closing soonest']] },
  events: { label: 'Events', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 6] },
  resources: { label: 'Resources', contentSource: 'dynamic', hasItemCount: true, itemCountBounds: [1, 6] },
  newsletter: { label: 'WSF Weekly (newsletter)', contentSource: 'none', hasBenefits: true },
  partners: { label: 'Partner Logos', contentSource: 'manual-orgs' },
  community_cta: { label: 'Community CTA', contentSource: 'cta', hasCta: true, hasMedia: true },
  mentorship_cta: { label: 'Mentorship CTA', contentSource: 'cta', hasCta: true, hasMedia: true },
  editorial_callout: { label: 'Editorial Callout', contentSource: 'cta', hasCta: true, hasMedia: true },
  sponsor_placement: { label: 'Sponsor Placement', contentSource: 'sponsor' },
  career_pathways: { label: 'Career Pathways / Start Here', contentSource: 'pathways', hasCta: true, ctaOptional: true, subheadingLabel: 'Intro text' },
  content_collection: { label: 'Content Collection', contentSource: 'collection', hasCta: true, ctaOptional: true, subheadingLabel: 'Description' },
  // Editorial-platform modules (backend services/homepage_editorial.py).
  // Every Article module takes part in first-placement-wins de-duplication:
  // a story placed by an earlier module is skipped here on the public page.
  career_moves: { label: 'Career Moves', contentSource: 'editorial-articles', sources: [['manual', 'Pick articles'], ['topic', 'Newest from topics']], hasItemCount: true, itemCountBounds: [1, 8], hasCta: true, ctaOptional: true },
  right_now: { label: 'Right Now (timely)', contentSource: 'editorial-articles', sources: [['manual', 'Pick articles'], ['series', 'Newest in a series'], ['topic', 'Newest from topics']], hasItemCount: true, itemCountBounds: [1, 8], hasCta: true, ctaOptional: true },
  expert_guidance: { label: 'Expert-Backed Guidance', contentSource: 'editorial-articles', sources: [['expert', 'Articles with a recorded reviewer/expert'], ['manual', 'Pick articles']], hasItemCount: true, itemCountBounds: [1, 8], hasCta: true, ctaOptional: true },
  community_stories: { label: 'Community Stories (e.g. Her Career Story)', contentSource: 'editorial-articles', sources: [['community', 'Published from reader story submissions'], ['series', 'Newest in a series'], ['manual', 'Pick articles']], hasItemCount: true, itemCountBounds: [1, 8], hasCta: true, ctaOptional: true },
  handpicked: { label: 'Handpicked', contentSource: 'editorial-articles', sources: [['editorial', 'Editor picks, then featured, then newest']], hasItemCount: true, itemCountBounds: [1, 8], hasCta: true, ctaOptional: true, personalized: true },
  people_spotlight: { label: 'Women Moving Industries (People)', contentSource: 'people-spotlight', sources: [['featured', 'Featured people'], ['manual', 'Pick people']], hasItemCount: true, itemCountBounds: [1, 8], hasCta: true, ctaOptional: true },
  learning: { label: 'From WSF Learning', contentSource: 'learning', sources: [['featured', 'Featured programs'], ['newest', 'Newest programs'], ['manual', 'Pick programs']], hasItemCount: true, itemCountBounds: [1, 6], hasCta: true, ctaOptional: true },
  mission: { label: 'Mission', contentSource: 'mission', hasCta: true, ctaOptional: true },
}

export const HOMEPAGE_SPONSOR_PLACEMENT_KEYS = ['homepage_featured']

export function newModuleDefaults(type) {
  const base = { type, enabled: true, heading: null, subheading: null, selectionMode: null, config: {} }
  if (type === 'career_pathways') return { ...base, config: { eyebrow: null, cards: [newPathwayCard(), newPathwayCard()] } }
  if (type === 'content_collection') return { ...base, selectionMode: 'automatic', config: newCollectionConfig('articles', 'automatic') }
  const spec = HOMEPAGE_MODULE_REGISTRY[type]
  if (spec?.sources) return { ...base, config: { source: spec.sources[0][0], itemCount: Math.min(4, spec.itemCountBounds[1]) } }
  return base
}
