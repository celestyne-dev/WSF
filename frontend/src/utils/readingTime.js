const WORDS_PER_MINUTE = 225
const MIN_READING_TIME_MINUTES = 1

const TAG_RE = /<[^>]*>/g
const WHITESPACE_RE = /\s+/

// CMS block text may contain a small allow-listed set of inline HTML tags
// (see components/article/ArticleContent.jsx's own InlineHtml comment) —
// stripped here so tag markup is never counted as reading words.
function countWords(text) {
  if (!text) return 0
  const stripped = String(text).replace(TAG_RE, ' ').trim()
  if (!stripped) return 0
  return stripped.split(WHITESPACE_RE).filter(Boolean).length
}

// Only block types whose own field is genuinely prose. Deliberately
// excludes image/media blocks, IDs, URLs, and structural metadata (ad
// slots, tables, buttons, sponsor/newsletter blocks, article-card
// snapshots, dividers, …) — none of that is something a reader "reads"
// in the word-count sense this estimate is for.
function wordsInBlock(block) {
  if (!block || typeof block !== 'object') return 0
  switch (block.type) {
    case 'paragraph':
    case 'heading':
    case 'pullquote':
    case 'blockquote':
    case 'highlight':
    case 'footerNote':
      return countWords(block.text)
    case 'list':
      return (block.items || []).reduce((sum, item) => sum + countWords(item), 0)
    case 'faq':
      return (block.items || []).reduce((sum, item) => sum + countWords(item?.q) + countWords(item?.a), 0)
    default:
      return 0
  }
}

/**
 * Resolves a displayable reading time, in whole minutes, for an article.
 *
 * An editor-supplied, positive `article.readingTime` is always
 * authoritative. Otherwise, estimates from `article.content` at roughly
 * 225 words/minute, counting only genuinely textual blocks (see
 * wordsInBlock above) and stripping inline HTML first. Always at least
 * 1 minute, even for very short or content-less articles.
 *
 * Returns null only when there's no article to resolve a time for at
 * all, so a caller can decide how to render that (vs. a real article
 * whose time is simply still being estimated at 1 minute).
 */
export function resolveReadingTime(article) {
  if (!article) return null
  const explicit = Number(article.readingTime)
  if (Number.isFinite(explicit) && explicit > 0) {
    return Math.round(explicit)
  }
  const totalWords = (article.content || []).reduce((sum, block) => sum + wordsInBlock(block), 0)
  return Math.max(MIN_READING_TIME_MINUTES, Math.round(totalWords / WORDS_PER_MINUTE))
}
