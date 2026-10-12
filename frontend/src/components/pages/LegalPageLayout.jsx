import { useMemo, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import ArticleContent from '../article/ArticleContent'
import { formatDate } from '../../utils/format'

function TocList({ headings, onNavigate }) {
  return (
    <ul className="space-y-2.5 text-sm">
      {headings.map((h) => (
        <li key={h.id}>
          <a
            href={`#${h.id}`}
            onClick={onNavigate}
            className={`block text-charcoal-600 transition-colors hover:text-burgundy-600 ${
              h.level >= 3 ? 'pl-4 text-[13px]' : ''
            }`}
          >
            {h.text}
          </a>
        </li>
      ))}
    </ul>
  )
}

// Desktop: sticky "On this page" sidebar (~240px) beside a narrow
// document column (capped at 760px — legal copy's own readable measure,
// independent of InstitutionalPageShell's wider editorial container).
// Mobile/tablet: the same nav collapses into a disclosure above the
// document so nothing pushes content below the fold on a small screen.
//
// `headings` is the already-built TOC (see LegalPage.jsx's
// buildHeadingToc — anchor-id generation is CMS-content-specific and
// deliberately lives at the page level, not in this reusable layout).
// This component's only job with it is to render the nav and line each
// heading *block* in `content` back up to its matching id, in document
// order, so ArticleContent's existing renderer gets the anchor without
// this component re-deriving slugs itself.
export default function LegalPageLayout({ headings = [], effectiveDate, content = [] }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const idByBlockIndex = useMemo(() => {
    const map = new Map()
    let cursor = 0
    content.forEach((block, i) => {
      if (block.type === 'heading') {
        map.set(i, headings[cursor]?.id)
        cursor += 1
      }
    })
    return map
  }, [content, headings])

  const hasToc = headings.length > 0

  return (
    <div className={hasToc ? 'lg:grid lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-14' : ''}>
      {hasToc && (
        <>
          <div className="mb-8 border border-taupe-200 lg:hidden">
            <button
              type="button"
              onClick={() => setMobileNavOpen((v) => !v)}
              aria-expanded={mobileNavOpen}
              aria-controls="legal-toc-mobile"
              className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-charcoal"
            >
              On this page
              <ChevronDown
                size={18}
                className={`text-charcoal-600 transition-transform ${mobileNavOpen ? 'rotate-180' : ''}`}
                aria-hidden="true"
              />
            </button>
            {mobileNavOpen && (
              <nav id="legal-toc-mobile" aria-label="On this page" className="border-t border-taupe-200 px-4 py-4">
                <TocList headings={headings} onNavigate={() => setMobileNavOpen(false)} />
              </nav>
            )}
          </div>

          <aside className="hidden lg:block lg:border-r lg:border-taupe-200 lg:pr-8">
            <nav aria-label="On this page" className="sticky top-28">
              <p className="eyebrow mb-4">On this page</p>
              <TocList headings={headings} />
            </nav>
          </aside>
        </>
      )}

      <div className="max-w-[760px]">
        {effectiveDate && (
          <p className="mb-8 border-b border-taupe-200 pb-6 text-sm text-charcoal-600">
            Last updated: <span className="font-medium text-charcoal">{formatDate(effectiveDate)}</span>
          </p>
        )}
        <ArticleContent blocks={content} headingIdForBlock={(block, i) => idByBlockIndex.get(i)} />
      </div>
    </div>
  )
}
