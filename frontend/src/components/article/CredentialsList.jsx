// AI Search / GEO Phase 4B — a profile's editor-entered credentials &
// qualifications (Person/Author.credentials). React text only, never HTML.
// The same list, same order and same section `id`, is in the server-
// rendered first paint (backend prerender.py's render_credentials) and in
// the page's JSON-LD as `hasCredential`. An entry records what the profile
// states — no verification badge or wording, ever.
export default function CredentialsList({ credentials, id }) {
  const items = (credentials || []).filter((c) => c?.name)
  if (!items.length) return null
  return (
    <section aria-labelledby={id} className="mt-10">
      <h2 id={id} className="font-serif text-2xl font-semibold text-charcoal">
        Credentials &amp; qualifications
      </h2>
      <ul className="mt-4 space-y-4">
        {items.map((credential, i) => {
          const meta = [credential.category, credential.issuer].filter(Boolean)
          return (
            <li key={`${credential.name}-${credential.issuer || ''}-${i}`}>
              <p className="text-base font-semibold text-charcoal">{credential.name}</p>
              {meta.length > 0 && <p className="mt-1 text-sm text-charcoal-600">{meta.join(' · ')}</p>}
              {/^https?:\/\//i.test(credential.url || '') && (
                <p className="mt-1 text-sm">
                  <a href={credential.url} target="_blank" rel="noopener noreferrer" className="font-medium text-burgundy-600 hover:underline">
                    Credential details
                  </a>
                </p>
              )}
              {credential.note && <p className="mt-1 text-sm text-charcoal-600/80">{credential.note}</p>}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
