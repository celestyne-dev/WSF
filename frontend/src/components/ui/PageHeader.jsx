export default function PageHeader({ eyebrow, title, description, children }) {
  return (
    <div className="border-b border-taupe-200 bg-cream py-12 sm:py-16">
      <div className="container-editorial">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="mt-2 font-serif text-4xl font-semibold text-charcoal sm:text-5xl">{title}</h1>
        {description && <p className="mt-3 max-w-2xl text-base text-charcoal-600 sm:text-lg">{description}</p>}
        {children}
      </div>
    </div>
  )
}
