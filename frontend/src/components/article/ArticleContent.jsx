import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'
import NewsletterForm from '../ui/NewsletterForm'
import { Quote } from 'lucide-react'

// Block text (paragraph/list-item/quote/callout) may contain a small
// allow-listed set of inline tags (b/strong/i/em/u/a/br) — sanitized
// server-side before storage (backend/app/services/content_blocks.py), so
// rendering it as HTML here is safe. Mock-mode demo content has no tags in
// it at all, so this renders identically to plain text either way.
function InlineHtml({ as: Tag = 'span', html, className }) {
  if (!html) return null
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />
}

function Heading({ block }) {
  const Tag = block.level === 4 ? 'h4' : block.level === 3 ? 'h3' : 'h2'
  const sizes = { 2: 'text-2xl sm:text-3xl', 3: 'text-xl sm:text-2xl', 4: 'text-lg sm:text-xl' }
  return <Tag className={`mt-10 font-serif font-semibold text-charcoal ${sizes[block.level] || sizes[2]}`}>{block.text}</Tag>
}

function Paragraph({ block }) {
  return <InlineHtml as="p" html={block.text} className="mt-5 font-sans text-lg leading-[1.85] text-charcoal-600" />
}

function ImageBlock({ block }) {
  // `media` is the normalized reference the block editor saves (with real
  // generated WebP variants); `mediaPath` is the legacy/mock-mode fallback.
  return (
    <figure className="my-10">
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
        <figcaption className="mt-2 text-sm text-charcoal-600">
          {block.caption} {block.credit && <span className="text-charcoal-600/70">— {block.credit}</span>}
        </figcaption>
      )}
    </figure>
  )
}

function PullQuote({ block }) {
  return (
    <blockquote className="relative my-10 border-y border-taupe-200 py-8 text-center">
      <Quote className="mx-auto mb-3 text-burgundy-500/50" size={28} />
      <InlineHtml as="p" html={block.text} className="font-serif text-2xl font-medium italic leading-snug text-charcoal sm:text-3xl" />
      {block.attribution && <cite className="mt-4 block font-sans text-sm not-italic text-charcoal-600">{block.attribution}</cite>}
    </blockquote>
  )
}

function BlockQuote({ block }) {
  return (
    <blockquote className="my-8 border-l-2 border-burgundy-500 pl-6">
      <InlineHtml as="p" html={block.text} className="font-serif text-xl italic leading-snug text-charcoal" />
      {block.attribution && <cite className="mt-2 block font-sans text-sm not-italic text-charcoal-600">{block.attribution}</cite>}
    </blockquote>
  )
}

function ListBlock({ block }) {
  const Tag = block.style === 'number' ? 'ol' : 'ul'
  return (
    <Tag className={`mt-5 space-y-2 pl-5 font-sans text-lg leading-relaxed text-charcoal-600 ${block.style === 'number' ? 'list-decimal' : 'list-disc'}`}>
      {block.items.map((item, i) => (
        <InlineHtml key={i} as="li" html={item} />
      ))}
    </Tag>
  )
}

function Highlight({ block }) {
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

function RelatedBlock({ block, articlesBySlug = {} }) {
  // ArticlePage pre-resolves every referenced slug through
  // api/articles.js (fetchRelatedArticles) and passes the result down as
  // articlesBySlug. This component never looks up article content itself;
  // a slug ArticlePage couldn't resolve (e.g. it doesn't exist on the
  // backend) is simply omitted, never independently looked up here.
  const related = (block.articleSlugs || []).map((s) => articlesBySlug[s]).filter(Boolean)
  if (!related.length) return null
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

function Divider() {
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
}

export default function ArticleContent({ blocks = [], relatedArticlesBySlug }) {
  return (
    <div>
      {blocks.map((block, i) => {
        const Renderer = RENDERERS[block.type]
        if (!Renderer) return null
        return <Renderer key={i} block={block} articlesBySlug={relatedArticlesBySlug} />
      })}
    </div>
  )
}
