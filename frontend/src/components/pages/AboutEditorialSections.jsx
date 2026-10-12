import MediaImage from '../ui/MediaImage'
import ArticleContent from '../article/ArticleContent'

// Mirrors ArticleContent's own InlineHtml: block text/list items may
// contain a small allow-listed set of inline tags, sanitized server-side
// before storage, so rendering them as HTML here is safe.
function InlineHtml({ as: Tag = 'span', html, className }) {
  if (!html) return null
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />
}

function HeroMediaBand({ media }) {
  return (
    <div className="container-editorial pt-14 sm:pt-16 lg:pt-20">
      <figure className="border border-taupe-200 bg-cream lg:ml-[10%]">
        <MediaImage
          media={media}
          variant="large"
          width={1400}
          height={700}
          aspect={2}
          priority
          className="aspect-[2/1] w-full object-cover"
        />
      </figure>
    </div>
  )
}

// First paragraph-led CMS section ("Our mission" in current content, but
// identified by shape, not wording) — a wide, high-impact 4/8 split with a
// thin burgundy rule standing in for a bullet, and the CMS paragraph set
// in larger reading type than the rest of the page.
function MissionSection({ section }) {
  const paragraphs = section.blocks.filter((b) => b.type === 'paragraph')
  const other = section.blocks.filter((b) => b.type !== 'paragraph')
  return (
    <div className="container-editorial py-14 sm:py-16 lg:py-20">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:gap-12">
        <div className="lg:col-span-4">
          {section.heading?.text && (
            <h2 className="font-serif text-2xl font-semibold leading-tight text-charcoal sm:text-3xl">
              {section.heading.text}
            </h2>
          )}
          <div className="mt-5 h-px w-12 bg-burgundy-500" />
        </div>
        <div className="border-t border-taupe-200 pt-8 lg:col-span-8 lg:border-l lg:border-t-0 lg:pl-12 lg:pt-0">
          {paragraphs.map((block, i) => (
            <InlineHtml
              key={i}
              as="p"
              html={block.text}
              className={`font-serif text-xl leading-[1.7] text-charcoal sm:text-2xl ${i > 0 ? 'mt-6' : ''}`}
            />
          ))}
          {other.length > 0 && (
            <div className="mt-6">
              <ArticleContent blocks={other} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Section holding a `list` block ("What we do") — each CMS list item
// becomes an editorial capability tile in a 2-column grid rather than a
// plain bulleted list. Semantics stay list-like (ul/li) under the grid
// styling; the 01/02/03 numerals are decorative ordering, not content, so
// they're hidden from assistive tech.
function CapabilitiesSection({ section }) {
  const intro = section.blocks.filter((b) => b.type === 'paragraph')
  const listBlocks = section.blocks.filter((b) => b.type === 'list')
  const other = section.blocks.filter((b) => b.type !== 'paragraph' && b.type !== 'list')
  return (
    <div className="border-t border-taupe-200 bg-ivory">
      <div className="container-editorial py-14 sm:py-16 lg:py-20">
        <div className="max-w-2xl">
          {section.heading?.text && (
            <h2 className="font-serif text-2xl font-semibold text-charcoal sm:text-3xl">{section.heading.text}</h2>
          )}
          {intro.map((block, i) => (
            <InlineHtml key={i} as="p" html={block.text} className="mt-4 text-lg leading-relaxed text-charcoal-600" />
          ))}
        </div>

        {listBlocks.map((block, bi) => {
          const items = block.items || []
          return (
            <ul key={bi} className="mt-10 grid grid-cols-1 gap-px border border-taupe-200 bg-taupe-200 sm:grid-cols-2">
              {items.map((item, i) => {
                const lastOdd = items.length % 2 === 1 && i === items.length - 1
                return (
                  <li key={i} className={`p-6 sm:p-8 ${i % 2 === 0 ? 'bg-ivory' : 'bg-cream'} ${lastOdd ? 'sm:col-span-2' : ''}`}>
                    <p aria-hidden="true" className="font-serif text-sm text-burgundy-600">
                      {String(i + 1).padStart(2, '0')}
                    </p>
                    <InlineHtml as="p" html={item} className="mt-3 font-serif text-lg leading-snug text-charcoal" />
                  </li>
                )
              })}
            </ul>
          )
        })}

        {other.length > 0 && (
          <div className="mt-10 max-w-2xl">
            <ArticleContent blocks={other} />
          </div>
        )}
      </div>
    </div>
  )
}

// Last remaining paragraph-led section ("Editorial standards") — a
// full-width, dark plum trust band so it reads as a distinct closing
// statement rather than just "one more paragraph" under the fold.
function StandardsSection({ section }) {
  const paragraphs = section.blocks.filter((b) => b.type === 'paragraph')
  const other = section.blocks.filter((b) => b.type !== 'paragraph')
  return (
    <div className="border-y border-taupe-200 bg-plum-700">
      <div className="container-editorial py-14 sm:py-16 lg:py-20">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-12">
          <div className="lg:col-span-4">
            <p className="font-sans text-xs font-semibold uppercase tracking-widest2 text-ivory/60">Our standards</p>
            {section.heading?.text && (
              <h2 className="mt-2 font-serif text-2xl font-semibold text-ivory sm:text-3xl">{section.heading.text}</h2>
            )}
          </div>
          <div className="lg:col-span-8">
            {paragraphs.map((block, i) => (
              <InlineHtml
                key={i}
                as="p"
                html={block.text}
                className={`font-sans text-lg leading-relaxed text-ivory/85 [&_a]:text-ivory [&_a]:underline ${i > 0 ? 'mt-5' : ''}`}
              />
            ))}
            {other.length > 0 && (
              <div className="mt-5 text-ivory/85">
                <ArticleContent blocks={other} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// Fallback for any section that isn't the mission/capabilities/standards
// treatment above (rare for current content, but guarantees an editor
// adding a fourth section never loses it) — plain, on-brand, unstyled
// beyond a readable column width.
function GenericSection({ section }) {
  return (
    <div className="container-editorial py-10">
      <div className="mx-auto max-w-reading">
        {section.heading?.text && (
          <h2 className="font-serif text-2xl font-semibold text-charcoal sm:text-3xl">{section.heading.text}</h2>
        )}
        <ArticleContent blocks={section.blocks} />
      </div>
    </div>
  )
}

// Renders the About page body from CMS content already grouped and
// tagged by AboutPage.jsx's groupContentByHeading/tagSections — this
// component only knows how to lay out each tagged kind, never how to
// derive it, so the CMS-parsing logic stays in one place.
export default function AboutEditorialSections({ heroMedia, sections = [] }) {
  return (
    <div>
      {heroMedia && <HeroMediaBand media={heroMedia} />}
      {sections.map(({ section, kind }, i) => {
        if (kind === 'mission') return <MissionSection key={i} section={section} />
        if (kind === 'list') return <CapabilitiesSection key={i} section={section} />
        if (kind === 'standards') return <StandardsSection key={i} section={section} />
        return <GenericSection key={i} section={section} />
      })}
    </div>
  )
}
