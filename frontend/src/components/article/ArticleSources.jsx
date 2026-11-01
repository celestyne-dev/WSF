// AI Search / GEO Phase 3A — the article's editor-entered sources and
// references (Article.sources, validated server-side: plain text + http(s)
// URLs only). Rendered as React text, never HTML. The same list, in the
// same order, is in the server-rendered first paint (backend/app/services/
// prerender.py's render_article_sources) and in the Article JSON-LD as
// schema.org `citation` (utils/articleStructuredData.js).
//
// Links are ordinary editorial citations — crawlable, opened in a new tab
// with rel="noopener noreferrer", never marked nofollow/sponsored/ugc.

// A source date is a calendar date (YYYY-MM-DD), so it's formatted in UTC —
// a local-time conversion would show the previous day west of Greenwich.
function formatSourceDate(value) {
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

export default function ArticleSources({ sources }) {
  const items = (sources || []).filter((s) => s?.title)
  if (!items.length) return null
  return (
    <section aria-labelledby="article-sources" className="mt-12 border-t border-taupe-200 pt-8">
      <h2 id="article-sources" className="font-serif text-xl font-semibold text-charcoal">
        Sources &amp; references
      </h2>
      <ol className="mt-4 list-decimal space-y-3 pl-5 text-sm leading-relaxed text-charcoal-600">
        {items.map((source, i) => {
          const dateLabel = source.publishedDate ? formatSourceDate(source.publishedDate) : null
          const meta = [source.author, source.publisher].filter(Boolean)
          return (
            <li key={`${source.url}-${i}`}>
              {source.url ? (
                <a href={source.url} target="_blank" rel="noopener noreferrer" className="font-medium text-burgundy-600 hover:underline">
                  {source.title}
                </a>
              ) : (
                source.title
              )}
              {(meta.length > 0 || dateLabel) && (
                <span className="block">
                  {meta.join(' · ')}
                  {meta.length > 0 && dateLabel && ' · '}
                  {dateLabel && <time dateTime={source.publishedDate}>{dateLabel}</time>}
                </span>
              )}
              {source.note && <span className="block">{source.note}</span>}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
