// Heading anchors for "On this page" / "In this article" navigation.
// Ids are derived purely from each heading block's own text (never a
// separate CMS field, never an API call), so renaming a heading just
// works. Duplicates get a stable "-2", "-3", ... suffix in document order.
// Shared by LegalPage and ArticlePage.
export function slugifyHeading(text) {
  const base = (text || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .slice(0, 60)
  return base || 'section'
}

export function buildHeadingToc(blocks) {
  const seenCounts = new Map()
  const headings = []
  ;(Array.isArray(blocks) ? blocks : []).forEach((block, index) => {
    if (!block || block.type !== 'heading' || !(block.text || '').trim()) return
    const base = slugifyHeading(block.text)
    const seen = seenCounts.get(base) || 0
    seenCounts.set(base, seen + 1)
    const id = seen === 0 ? base : `${base}-${seen + 1}`
    headings.push({ id, text: block.text, level: block.level || 2, index })
  })
  return headings
}

// Article "In this article": H2/H3 only, shown only from three headings up
// (a short piece doesn't need navigation). Every heading still gets its id.
export const ARTICLE_TOC_MIN_HEADINGS = 3

export function buildArticleToc(blocks) {
  const all = buildHeadingToc(blocks)
  const entries = all.filter((h) => h.level === 2 || h.level === 3)
  return {
    idByIndex: new Map(all.map((h) => [h.index, h.id])),
    entries: entries.length >= ARTICLE_TOC_MIN_HEADINGS ? entries : [],
  }
}
