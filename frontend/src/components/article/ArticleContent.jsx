import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'
import NewsletterForm from '../ui/NewsletterForm'
import { ArrowRight, Check, Quote } from 'lucide-react'

// Block text (paragraph/list-item/quote/callout) may contain a small
// allow-listed set of inline tags (b/strong/i/em/u/a/br) — sanitized
// server-side before storage (backend/app/services/content_blocks.py), so
// rendering it as HTML here is safe. Mock-mode demo content has no tags in
// it at all, so this renders identically to plain text either way.
function InlineHtml({ as: Tag = 'span', html, className }) {
  if (!html) return null
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />
}

// Inline-link styling for variant="article" — applied via a Tailwind
// arbitrary-descendant selector since CMS links arrive as raw `<a>`
// markup inside dangerouslySetInnerHTML, never as React elements this
// component could style directly. Focus visibility already comes from
// index.css's global `*:focus-visible` rule, so only color/underline are
// set here.
const ARTICLE_LINK_CLASSES =
  '[&_a]:text-burgundy-600 [&_a]:underline [&_a]:decoration-burgundy-300 [&_a]:underline-offset-2 hover:[&_a]:decoration-burgundy-600'

function Heading({ block, headingId, variant }) {
  const Tag = block.level === 4 ? 'h4' : block.level === 3 ? 'h3' : 'h2'
  const sizes = { 2: 'text-2xl sm:text-3xl', 3: 'text-xl sm:text-2xl', 4: 'text-lg sm:text-xl' }
  // variant="article" (ArticlePage only): stronger serif scale and
  // vertical rhythm so H2 reads as a real section break rather than
  // standard document text; H3/H4 keep their relative size so the
  // hierarchy beneath the now-larger H2 stays clear. Every other caller
  // (Legal/About/Contact pages) omits `variant`, so this renders exactly
  // as before.
  const articleSizes = {
    2: 'text-[1.75rem] leading-[1.15] sm:text-3xl lg:text-[2.125rem]',
    3: 'text-xl leading-snug sm:text-2xl',
    4: 'text-lg leading-snug sm:text-xl',
  }
  const isArticle = variant === 'article'
  const isResource = variant === 'resource'
  const useArticleScale = isArticle || isResource
  const sizeClass = (useArticleScale ? articleSizes : sizes)[block.level] || (useArticleScale ? articleSizes[2] : sizes[2])
  const spacingClass = useArticleScale && block.level === 2 ? (isResource ? 'mt-16' : 'mt-14') : 'mt-10'
  // `headingId`, when supplied by a caller (e.g. LegalPageLayout's "On
  // this page" nav), gives this heading a stable anchor; scroll-mt-28
  // keeps the sticky site header from covering it when a TOC link or
  // in-page hash jumps here. Absent any id, this renders exactly as
  // before — no behavior change for ArticlePage or any other caller.
  return (
    <Tag
      id={headingId || undefined}
      className={`${spacingClass} font-serif font-semibold text-charcoal ${sizeClass} ${headingId ? 'scroll-mt-28' : ''}`}
    >
      {block.text}
    </Tag>
  )
}

function Paragraph({ block, variant, isLeadParagraph }) {
  if (variant === 'article' || variant === 'resource') {
    // The first paragraph in the article gets a subtly larger, darker
    // introductory treatment (no drop cap) — everything after reads at
    // the same comfortable long-form size/line-height.
    const sizeClass = isLeadParagraph ? 'text-xl leading-[1.75]' : 'text-[1.1875rem] leading-[1.8]'
    return (
      <InlineHtml
        as="p"
        html={block.text}
        className={`mt-6 font-sans ${sizeClass} text-charcoal ${ARTICLE_LINK_CLASSES}`}
      />
    )
  }
  return <InlineHtml as="p" html={block.text} className="mt-5 font-sans text-lg leading-[1.85] text-charcoal-600" />
}

function ImageBlock({ block, variant }) {
  // `media` is the normalized reference the block editor saves (with real
  // generated WebP variants); `mediaPath` is the legacy/mock-mode fallback.
  const isArticle = variant === 'article' || variant === 'resource'
  return (
    <figure className={isArticle ? 'my-12' : 'my-10'}>
      <MediaImage
        media={block.media}
        variant="large"
        mediaPath={block.mediaPath}
        alt={block.alt}
        width={1400}
        height={933}
        aspect={3 / 2}
        className="aspect-[3/2] w-full object-cover"
      />
      {(block.caption || block.credit) && (
        <figcaption className={isArticle ? 'mt-3 text-sm leading-relaxed text-charcoal-600' : 'mt-2 text-sm text-charcoal-600'}>
          {block.caption} {block.credit && <span className={isArticle ? 'text-charcoal-600/60' : 'text-charcoal-600/70'}>— {block.credit}</span>}
        </figcaption>
      )}
    </figure>
  )
}

function PullQuote({ block, variant }) {
  if (variant === 'article') {
    return (
      <blockquote className="relative my-14 border-y border-taupe-200 py-10 text-center">
        <Quote className="mx-auto mb-4 text-burgundy-500/40" size={22} aria-hidden="true" />
        <InlineHtml as="p" html={block.text} className="font-serif text-2xl italic leading-snug text-charcoal sm:text-3xl" />
        {block.attribution && <cite className="mt-5 block font-sans text-sm not-italic text-charcoal-600">{block.attribution}</cite>}
      </blockquote>
    )
  }
  if (variant === 'resource') {
    return (
      <blockquote className="relative mx-auto my-10 max-w-[760px] border-y border-taupe-200 py-7 text-center">
        <Quote className="mx-auto mb-3 text-burgundy-500/40" size={20} aria-hidden="true" />
        <InlineHtml as="p" html={block.text} className="font-serif text-2xl italic leading-snug text-charcoal sm:text-3xl" />
        {block.attribution && <cite className="mt-4 block font-sans text-sm not-italic text-charcoal-600">{block.attribution}</cite>}
      </blockquote>
    )
  }
  return (
    <blockquote className="relative my-10 border-y border-taupe-200 py-8 text-center">
      <Quote className="mx-auto mb-3 text-burgundy-500/50" size={28} />
      <InlineHtml as="p" html={block.text} className="font-serif text-2xl font-medium italic leading-snug text-charcoal sm:text-3xl" />
      {block.attribution && <cite className="mt-4 block font-sans text-sm not-italic text-charcoal-600">{block.attribution}</cite>}
    </blockquote>
  )
}

function BlockQuote({ block, variant }) {
  if (variant === 'article') {
    return (
      <blockquote className="my-10 border-l-[3px] border-burgundy-500 py-1 pl-8">
        <InlineHtml as="p" html={block.text} className="font-serif text-2xl italic leading-snug text-charcoal" />
        {block.attribution && <cite className="mt-3 block font-sans text-sm not-italic text-charcoal-600">{block.attribution}</cite>}
      </blockquote>
    )
  }
  return (
    <blockquote className="my-8 border-l-2 border-burgundy-500 pl-6">
      <InlineHtml as="p" html={block.text} className="font-serif text-xl italic leading-snug text-charcoal" />
      {block.attribution && <cite className="mt-2 block font-sans text-sm not-italic text-charcoal-600">{block.attribution}</cite>}
    </blockquote>
  )
}

function ListBlock({ block, variant }) {
  const Tag = block.style === 'number' ? 'ol' : 'ul'
  if (variant === 'resource') {
    // A deliberately wider, custom-marker "editorial panel" treatment for
    // Resource detail pages only. `list-none` drops the browser bullet/
    // number — Safari+VoiceOver is known to also drop the implicit list
    // role along with it, so `role="list"` restores that explicitly.
    return (
      <Tag role="list" className="mt-6 max-w-[880px] list-none divide-y divide-taupe-200">
        {block.items.map((item, i) => (
          <li key={i} className="flex items-start gap-3 py-2.5 font-sans text-[1.0625rem] leading-[1.7] text-charcoal">
            {block.style === 'number' ? (
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-plum-600 text-xs font-semibold text-ivory">
                {i + 1}
              </span>
            ) : (
              <Check size={18} className="mt-0.5 shrink-0 text-plum-600" aria-hidden="true" />
            )}
            <InlineHtml as="span" html={item} className={ARTICLE_LINK_CLASSES} />
          </li>
        ))}
      </Tag>
    )
  }
  if (variant === 'article') {
    return (
      <Tag
        className={`mt-6 space-y-3 pl-5 font-sans text-[1.1875rem] leading-[1.8] text-charcoal ${ARTICLE_LINK_CLASSES} ${block.style === 'number' ? 'list-decimal' : 'list-disc'}`}
      >
        {block.items.map((item, i) => (
          <InlineHtml key={i} as="li" html={item} />
        ))}
      </Tag>
    )
  }
  return (
    <Tag className={`mt-5 space-y-2 pl-5 font-sans text-lg leading-relaxed text-charcoal-600 ${block.style === 'number' ? 'list-decimal' : 'list-disc'}`}>
      {block.items.map((item, i) => (
        <InlineHtml key={i} as="li" html={item} />
      ))}
    </Tag>
  )
}

function Highlight({ block, variant }) {
  if (variant === 'article') {
    return (
      <div className="my-10 border border-taupe-200 border-l-4 border-l-burgundy-500 bg-cream p-6 sm:p-8">
        {block.title && <p className="eyebrow mb-2">{block.title}</p>}
        <InlineHtml as="p" html={block.text} className="font-serif text-lg leading-relaxed text-charcoal sm:text-xl" />
      </div>
    )
  }
  if (variant === 'resource') {
    return (
      <div className="my-10 max-w-[820px] border border-taupe-200 border-l-4 border-l-plum-600 bg-blush-50 p-7 sm:p-8">
        {block.title && <p className="eyebrow mb-2">{block.title}</p>}
        <InlineHtml as="p" html={block.text} className="font-serif text-lg italic leading-relaxed text-charcoal sm:text-xl" />
      </div>
    )
  }
  return (
    <div className="my-8 border border-taupe-200 bg-cream p-6">
      {block.title && <p className="eyebrow mb-2">{block.title}</p>}
      <InlineHtml as="p" html={block.text} className="font-serif text-lg leading-relaxed text-charcoal" />
    </div>
  )
}

function NewsletterCta({ block }) {
  return (
    <div className="my-10 border border-plum-600/20 bg-plum-600 px-6 py-8 text-center sm:px-10">
      <h3 className="font-serif text-2xl font-semibold text-ivory">{block.heading || 'WSF Weekly'}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-ivory/85">{block.text}</p>
      <div className="mt-5 flex justify-center">
        <NewsletterForm variant="dark" source="article-inline" />
      </div>
    </div>
  )
}

function RelatedBlock({ block, articlesBySlug = {}, variant }) {
  // ArticlePage pre-resolves every referenced slug through
  // api/articles.js (fetchRelatedArticles) and passes the result down as
  // articlesBySlug. This component never looks up article content itself;
  // a slug ArticlePage couldn't resolve (e.g. it doesn't exist on the
  // backend) is simply omitted, never independently looked up here.
  const related = (block.articleSlugs || []).map((s) => articlesBySlug[s]).filter(Boolean)
  if (!related.length) return null
  if (variant === 'article') {
    return (
      <div className="my-12 border-y border-taupe-200 py-8">
        <p className="eyebrow mb-5">{block.heading || 'Related reading'}</p>
        <ul className="divide-y divide-taupe-200">
          {related.map((a) => (
            <li key={a.slug}>
              <Link
                to={`/${a.slug}`}
                className="group flex items-center justify-between gap-4 py-3 font-serif text-lg font-medium text-charcoal transition-colors hover:text-burgundy-600"
              >
                {a.title}
                <ArrowRight size={16} className="shrink-0 text-charcoal-600/40 transition-colors group-hover:text-burgundy-600" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      </div>
    )
  }
  return (
    <div className="my-10 border-y border-taupe-200 py-6">
      <p className="eyebrow mb-4">{block.heading || 'Related reading'}</p>
      <ul className="space-y-3">
        {related.map((a) => (
          <li key={a.slug}>
            <Link to={`/${a.slug}`} className="font-serif text-lg font-medium text-charcoal link-underline hover:text-burgundy-600">
              {a.title}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

function SponsorBlock({ block }) {
  return (
    <div className="my-8 border border-dashed border-taupe-300 bg-blush-50 p-5">
      <p className="text-xs font-semibold uppercase tracking-widest2 text-burgundy-600">{block.label || 'Sponsored content'}</p>
      <p className="mt-2 text-sm leading-relaxed text-charcoal-600">{block.text}</p>
    </div>
  )
}

function AdSlot({ block }) {
  return (
    <div className="my-10 flex h-24 items-center justify-center border border-dashed border-taupe-300 bg-taupe-100/60 text-xs uppercase tracking-wide text-charcoal-600/60 sm:h-32">
      Advertisement — {block.slot || 'article_middle'}
    </div>
  )
}

function ButtonBlock({ block }) {
  return (
    <div className="my-6">
      <a href={block.url} className="btn-primary" target={block.external ? '_blank' : undefined} rel="noreferrer">
        {block.label}
      </a>
    </div>
  )
}

// A self-contained snapshot of a published Article (title/excerpt/image
// captured when an editor selected it — see ArticleBlockEditor's
// articleCard block) rather than a live lookup, so a newsletter's sent
// content keeps reading correctly even if the source article later
// changes or is unpublished.
function ArticleCardBlock({ block }) {
  if (!block.articleSlug) return null
  return (
    <Link to={`/${block.articleSlug}`} className="group my-8 flex gap-4 border border-taupe-200 p-4 transition-colors hover:border-burgundy-500">
      {block.imageUrl && <MediaImage mediaPath={block.imageUrl} alt={block.title} width={240} height={168} aspect={10 / 7} className="w-28 shrink-0 object-cover sm:w-36" />}
      <div className="min-w-0">
        <p className="eyebrow">Read the story</p>
        <p className="mt-1 font-serif text-lg font-semibold text-charcoal group-hover:text-burgundy-600">{block.title}</p>
        {block.excerpt && <p className="mt-1 line-clamp-2 text-sm text-charcoal-600">{block.excerpt}</p>}
      </div>
    </Link>
  )
}

function FooterNoteBlock({ block }) {
  if (!block.text) return null
  return <InlineHtml as="p" html={block.text} className="mt-10 text-xs text-charcoal-600/70" />
}

function TableBlock({ block }) {
  return (
    <div className="my-8 overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b-2 border-charcoal">
            {block.headers.map((h) => (
              <th key={h} className="py-2 pr-4 font-semibold text-charcoal">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, i) => (
            <tr key={i} className="border-b border-taupe-200">
              {row.map((cell, j) => (
                <td key={j} className="py-2 pr-4 text-charcoal-600">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FaqBlock({ block }) {
  return (
    <div className="my-8 space-y-5">
      {block.items.map((item, i) => (
        <div key={i}>
          <h4 className="font-serif text-lg font-semibold text-charcoal">{item.q}</h4>
          <p className="mt-1 text-base text-charcoal-600">{item.a}</p>
        </div>
      ))}
    </div>
  )
}

function Divider({ variant }) {
  if (variant === 'article') {
    return <hr className="mx-auto my-16 w-16 border-t border-taupe-300" />
  }
  if (variant === 'resource') {
    return <hr className="mx-auto my-10 w-16 border-t border-taupe-300" />
  }
  return <hr className="my-10 border-t border-taupe-300" />
}

const RENDERERS = {
  heading: Heading,
  paragraph: Paragraph,
  image: ImageBlock,
  pullquote: PullQuote,
  blockquote: BlockQuote,
  list: ListBlock,
  highlight: Highlight,
  divider: Divider,
  newsletterCta: NewsletterCta,
  relatedBlock: RelatedBlock,
  sponsorBlock: SponsorBlock,
  ad: AdSlot,
  button: ButtonBlock,
  table: TableBlock,
  faq: FaqBlock,
  articleCard: ArticleCardBlock,
  footerNote: FooterNoteBlock,
}

// `headingIdForBlock(block, index)` is optional — when a caller supplies
// it, each heading block's rendered <h2-4> gets the id it returns (see
// Heading() above); every other block type ignores the prop entirely.
// Omit it (as every existing caller does) and rendering is byte-for-byte
// what it was before this prop existed.
//
// `variant="article"` is likewise optional, used only by ArticlePage for
// a more premium long-form reading treatment (larger serif headings,
// richer paragraph color/line-height, a stronger first paragraph, more
// editorial block styling). `variant="resource"` (ResourceDetailPage only)
// shares that same treatment for every block type except List, which
// instead gets a wider, custom-marker "editorial panel" look. Every
// renderer above falls through to its original, unchanged markup/classes
// whenever `variant` is omitted, so LegalPageLayout/AboutEditorialSections/
// ContactPage and any other existing caller render exactly as before.
export default function ArticleContent({ blocks = [], relatedArticlesBySlug, headingIdForBlock, variant }) {
  // -1 unless variant is "article" or "resource" (every other caller), so
  // `i === firstParagraphIndex` below is never true for them — no lead-
  // paragraph behavior change outside those two treatments.
  const firstParagraphIndex =
    variant === 'article' || variant === 'resource' ? blocks.findIndex((b) => b.type === 'paragraph') : -1
  return (
    <div>
      {blocks.map((block, i) => {
        const Renderer = RENDERERS[block.type]
        if (!Renderer) return null
        return (
          <Renderer
            key={i}
            block={block}
            articlesBySlug={relatedArticlesBySlug}
            headingId={headingIdForBlock ? headingIdForBlock(block, i) : undefined}
            variant={variant}
            isLeadParagraph={i === firstParagraphIndex}
          />
        )
      })}
    </div>
  )
}
