// Premium editorial hero for institutional pages (About, Contact,
// Privacy/Terms/Cookies/Editorial Policy) — never the article/homepage
// hero. All copy is caller-supplied (CMS-driven); this component only
// lays it out. Deliberately heavier than components/ui/PageHeader (bigger
// serif title, wider vertical rhythm) since these pages need to read as
// a considered institutional "front door", not a thin utility banner.
export default function InstitutionalPageHero({ eyebrow, title, description, children }) {
  return (
    <div className="border-b border-taupe-200 bg-cream">
      <div className="container-editorial py-16 sm:py-20 lg:py-24">
        <div className="max-w-3xl">
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h1 className="mt-3 font-serif text-4xl font-semibold leading-[1.1] text-charcoal sm:text-5xl lg:text-6xl">
            {title}
          </h1>
          {description && (
            <p className="mt-5 max-w-2xl text-lg leading-relaxed text-charcoal-600 sm:text-xl">{description}</p>
          )}
          {children}
        </div>
      </div>
    </div>
  )
}
