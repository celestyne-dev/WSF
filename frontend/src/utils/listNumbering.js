// The ONE numbering rule for numbered List blocks, used by the CMS editor
// (resolved numbers beside each item), ArticleContent (<ol start>) and the
// preview. The server prerender mirrors it in Python
// (backend app/services/content_blocks.py resolve_list_starts); both are
// tested against backend/tests/fixtures/list_numbering_cases.json.
//
// A numbered list block may carry `numberingMode`:
//   "continue" — continue from the most recent numbered list in the
//                article (non-list blocks in between do not reset it);
//                resolves to 1 when there is no earlier numbered list.
//   "restart"  — start at 1.
//   "custom"   — start at `startNumber` (an integer 1–100000, also as a
//                digit string; anything else resolves to 1, exactly like
//                backend content_blocks._custom_start).
// A block WITHOUT numberingMode (every list published before this existed)
// starts at 1 exactly as before — existing articles are never renumbered.
// Continue is always derived from the content, never stored as a number,
// so lengthening an earlier list renumbers later Continue lists correctly.
// Only non-blank items are rendered and counted; a numbered list with no
// real items renders nothing and is ignored by the sequence. Callout lists
// are their own contained sequence and never take part.

export const NUMBERING_MODES = ['continue', 'restart', 'custom']

// Reader-visible text of an inline-HTML list item: tags removed, the
// common entities decoded, non-breaking spaces as spaces. Mirrors backend
// content_blocks.visible_text so React, the prerender and numbering agree:
// "<strong></strong>" and "<br>" are blank; "<a href=…>Source</a>" is not.
const ENTITIES = { '&nbsp;': ' ', '&#160;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&#x27;': "'" }

export function visibleText(value) {
  if (typeof value !== 'string') return ''
  return value
    .replace(/<[^>]*>/g, '')
    .replace(/&(nbsp|amp|lt|gt|quot|#160|#39|#x27);/g, (m) => ENTITIES[m] ?? m)
    .replace(/\u00a0/g, ' ')
    .trim()
}

export function isBlankItem(item) {
  return visibleText(item) === ''
}

export function visibleItems(items) {
  return (Array.isArray(items) ? items : []).filter((item) => !isBlankItem(item))
}

// Same ceiling as the backend sanitizer and the CMS number input.
export const MAX_START_NUMBER = 100000

function customStart(value) {
  const n = typeof value === 'number' ? value : typeof value === 'string' && /^\d+$/.test(value.trim()) ? Number(value.trim()) : NaN
  return Number.isInteger(n) && n >= 1 && n <= MAX_START_NUMBER ? n : 1
}

// -> array (same length as blocks): the resolved start number for each
// rendered numbered list block, null for every other block.
export function resolveListStarts(blocks) {
  let lastEnd = 0
  return (Array.isArray(blocks) ? blocks : []).map((block) => {
    if (!block || block.type !== 'list' || block.style !== 'number') return null
    const count = visibleItems(block.items).length
    if (count === 0) return null
    let start
    if (block.numberingMode === 'continue') start = lastEnd + 1
    else if (block.numberingMode === 'custom') start = customStart(block.startNumber)
    else start = 1 // "restart", legacy (no mode) and any unknown value
    lastEnd = start + count - 1
    return start
  })
}
