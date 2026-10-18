import { useEffect, useState } from 'react'
import { fetchPublicPage } from '../api/pages'
import { resolveMediaImage } from '../utils/media'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import AboutEditorialSections from '../components/pages/AboutEditorialSections'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

// Groups CMS content blocks by their leading heading block: each section
// runs from one heading up to (not including) the next. Purely structural
// — any blocks before the first heading become a headerless section — so
// this has no dependency on how many sections a page has.
function groupContentByHeading(blocks = []) {
  const sections = []
  let current = null
  for (const block of blocks) {
    if (block.type === 'heading') {
      current = { heading: block, blocks: [] }
      sections.push(current)
    } else {
      if (!current) {
        current = { heading: null, blocks: [] }
        sections.push(current)
      }
      current.blocks.push(block)
    }
  }
  return sections
}

// Tags each section by content shape rather than heading wording, so
// renaming a CMS heading never breaks the layout: the first paragraph-led
// section gets the "mission" treatment, the section holding a list block
// becomes the capability-card grid, and the last remaining paragraph-led
// section becomes the closing "standards" band. Anything else is tagged
// "generic" and still renders (see AboutEditorialSections) instead of
// being silently dropped.
function tagSections(sections) {
  const listIndex = sections.findIndex((s) => s.blocks.some((b) => b.type === 'list'))
  const paragraphIndices = sections
    .map((s, i) => ({ s, i }))
    .filter(({ s }) => !s.blocks.some((b) => b.type === 'list'))
    .map(({ i }) => i)
  const missionIndex = paragraphIndices.length > 0 ? paragraphIndices[0] : -1
  const standardsIndex = paragraphIndices.length > 1 ? paragraphIndices[paragraphIndices.length - 1] : -1

  return sections.map((section, i) => ({
    section,
    kind: i === listIndex ? 'list' : i === missionIndex ? 'mission' : i === standardsIndex ? 'standards' : 'generic',
  }))
}

// A true Pages CMS page — title, subtitle, hero media, content, and SEO
// all come from the "about" Page record (/admin/pages) and nothing else.
// No audience stats, no founder details, no hard-coded mission/"what we
// do" copy: an editor's save in AdminPageEditor is exactly what renders
// here, just laid out as a considered editorial brand page instead of a
// plain document. The right-hand hero panel and the 01/02/03 card
// numerals are the only non-CMS marks on the page, and both are purely
// decorative/structural (aria-hidden or brand words), never facts.
export default function AboutPage() {
  const [page, setPage] = useState(undefined)

  useEffect(() => {
    let active = true
    fetchPublicPage('about')
      .then((res) => active && setPage(res))
      .catch(() => active && setPage(null))
    return () => {
      active = false
    }
  }, [])

  useSeo({
    // CMS SEO fields win; the Page's own title/subtitle are the next
    // fallback (both are editor-controlled), and only below that does
    // useSeo() reach for the global Site Settings SEO defaults.
    title: page?.seo?.title || page?.title,
    description: page?.seo?.description || page?.subtitle,
    canonical: 'https://womenshapingfutures.org/about',
    image: page?.heroMedia ? resolveMediaImage(page.heroMedia, { variant: 'large' }).src : undefined,
  })
  // Home > (the real public CMS page display title, page.title — same
  // string shown as this page's own H1) — matches the server's own
  // breadcrumb for this page (spa_shell.py's _render_system_page_shell,
  // same page.title, never the resolved SEO/meta title), so this hook
  // finds and reuses the server-rendered tag rather than appending a
  // duplicate, and removes it on navigating away.
  useBreadcrumbStructuredData(page ? [{ label: page?.title }] : null, 'https://womenshapingfutures.org/about')

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  const taggedSections = tagSections(groupContentByHeading(page.content))

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream">
        <div className="container-editorial grid grid-cols-1 gap-10 py-12 sm:py-16 lg:grid-cols-12 lg:items-center lg:gap-16 lg:py-20">
          <div className="lg:col-span-7">
            <p className="eyebrow">About Us</p>
            <h1 className="mt-3 font-serif text-4xl font-semibold leading-[1.08] text-charcoal sm:text-5xl lg:text-[3.25rem]">
              {page.title}
            </h1>
            {page.subtitle && (
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-charcoal-600 sm:text-xl">{page.subtitle}</p>
            )}
          </div>

          {/* Purely decorative editorial composition — brand words and
              rules only, never factual content, so it's hidden from
              assistive tech and disappears below desktop rather than
              trying to squeeze in on a narrow screen. */}
          <div aria-hidden="true" className="hidden lg:col-span-5 lg:block">
            <div className="border-l-2 border-burgundy-500 pl-10">
              <p className="font-serif text-3xl italic leading-tight text-plum-700">Women</p>
              <p className="mt-2 font-serif text-3xl italic leading-tight text-charcoal/60">Stories</p>
              <p className="mt-2 font-serif text-3xl italic leading-tight text-plum-700">Opportunity</p>
              <p className="mt-2 font-serif text-3xl italic leading-tight text-charcoal/60">Growth</p>
              <div className="mt-8 h-px w-16 bg-taupe-300" />
              <p className="mt-6 font-sans text-xs font-semibold uppercase tracking-widest2 text-charcoal-600/60">
                Stories &bull; Opportunity &bull; Growth
              </p>
            </div>
          </div>
        </div>
      </div>

      <AboutEditorialSections heroMedia={page.heroMedia} sections={taggedSections} />
    </div>
  )
}
