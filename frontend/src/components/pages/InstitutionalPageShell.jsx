import MediaImage from '../ui/MediaImage'

// Reusable outer body layout for institutional pages, paired with
// InstitutionalPageHero above it. Owns vertical rhythm and the optional
// hero-media band only — never page copy, which always comes from the
// CMS Page the caller already fetched.
//
// `heroMedia`, when present, renders as a framed, full-bleed-within-the-
// column editorial image (cropped to a wide aspect ratio, bordered) —
// deliberately not the old small `object-contain`, centered-on-cream
// treatment, which read as an isolated image floating in whitespace
// rather than part of the page's own layout.
//
// `maxWidthClassName` controls the inner content column's width: the
// default suits a single reading column (About/Contact's CMS intro);
// pass a wider value (or '' to defer entirely to the parent) for a
// layout — like LegalPageLayout's sidebar+content split — that manages
// its own internal width.
export default function InstitutionalPageShell({
  heroMedia,
  maxWidthClassName = 'mx-auto max-w-reading lg:max-w-3xl xl:max-w-4xl',
  children,
}) {
  return (
    <div className="container-editorial py-14 sm:py-16 lg:py-20">
      {heroMedia && (
        <figure className="mb-14 border border-taupe-200 bg-cream lg:mb-16">
          <MediaImage
            media={heroMedia}
            variant="large"
            width={1400}
            height={800}
            aspect={7 / 4}
            priority
            className="aspect-[7/4] w-full object-cover"
          />
        </figure>
      )}
      <div className={maxWidthClassName}>{children}</div>
    </div>
  )
}
