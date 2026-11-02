// AI Search / GEO Phase 4C — pure form helpers for the Topic/Series editors'
// shared editorial-depth fields (long-form content, Sources & references,
// the featured "Start here" Article). Node-testable; the backend stays
// authoritative (sanitize_content_blocks, SourceSchema, Article existence).
import { blankSource, sourcesToPayload } from './sources.js'

export function blankEditorialForm() {
  return { content: [], sources: [], featuredArticleId: null, featuredArticleSelection: null }
}

// Mapped admin Topic/Series (api/taxonomies.js mapTopicDetail/
// mapSeriesDetail) -> editor form fields.
export function editorialToForm(entity) {
  return {
    content: entity?.content || [],
    sources: (entity?.sources || []).map((s) => ({ ...blankSource(), ...s })),
    featuredArticleId: entity?.featuredArticleId ?? null,
    featuredArticleSelection: entity?.featuredArticleSelection || null,
  }
}

// Editor form -> the always-sent editorial part of the save payload
// (explicit values, so a save reflects exactly what the editor shows;
// null featuredArticleId clears the pick).
export function editorialToPayload(form) {
  return {
    content: form.content || [],
    sources: sourcesToPayload(form.sources),
    featuredArticleId: form.featuredArticleId ? Number(form.featuredArticleId) : null,
  }
}
