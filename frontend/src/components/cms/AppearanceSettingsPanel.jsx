import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { fetchAdminSettings, saveAdminSettings } from '../../api/admin'
import { applyCornerStyle, CORNER_STYLES, resolveCornerStyle } from '../../utils/appearance'

// Studio -> Settings -> Appearance. Phase 1: one controlled preset (corner
// style) — never raw CSS, colors or fonts. The preview below scopes the
// same CSS tokens the public site uses to its own box (data-wsf-corners on
// the preview element), so it shows the choice before saving without
// touching the rest of Studio.
export default function AppearanceSettingsPanel() {
  const [saved, setSaved] = useState(null)
  const [corner, setCorner] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchAdminSettings()
      .then((data) => {
        if (!active) return
        const value = resolveCornerStyle(data.appearance?.cornerStyle)
        setSaved(value)
        setCorner(value)
      })
      .catch(() => active && setError('Something went wrong loading Appearance. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  async function save() {
    setSaving(true)
    try {
      const data = await saveAdminSettings({ appearance: { cornerStyle: corner } })
      const value = resolveCornerStyle(data?.appearance?.cornerStyle || corner)
      setSaved(value)
      // Studio shares the document with the public site in this tab, so a
      // later visit to a public page in the same session matches at once.
      applyCornerStyle(value)
      toast.success('Appearance saved. Public pages use it from their next load.')
    } catch {
      toast.error('Could not save Appearance. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (error) return <p className="text-sm text-burgundy-600">{error}</p>
  if (!corner) return <p className="text-sm text-charcoal-600">Loading…</p>

  return (
    <div className="max-w-4xl space-y-8">
      <section>
        <h2 className="font-serif text-xl font-semibold text-charcoal">Corner style</h2>
        <p className="mt-1 text-sm text-charcoal-600">
          Sets how rounded the public site looks: cards, buttons, images (including author portraits), callouts, in-article CTAs and
          the header&apos;s dropdown menus. Avatars, icon circles, status dots and pills always stay circular.
        </p>
        <div role="radiogroup" aria-label="Corner style" className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CORNER_STYLES.map((option) => {
            const selected = corner === option.value
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setCorner(option.value)}
                className={`flex flex-col items-start gap-2 border p-4 text-left transition-colors ${
                  selected ? 'border-burgundy-600 bg-blush-50 ring-1 ring-burgundy-600' : 'border-taupe-200 bg-white hover:border-taupe-400'
                }`}
              >
                <span data-wsf-corners={option.value} className="block h-10 w-16 rounded-card border-2 border-charcoal-600 bg-cream" aria-hidden="true" />
                <span className="text-sm font-semibold text-charcoal">
                  {option.label} <span className="font-normal text-charcoal-600">· {option.radius}</span>
                  {saved === option.value && <span className="ml-1 text-xs font-medium text-burgundy-600">(current)</span>}
                </span>
                <span className="text-xs leading-snug text-charcoal-600">{option.description}</span>
              </button>
            )
          })}
        </div>
      </section>

      <section aria-label="Live preview">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-charcoal-600">Live preview</h3>
        <div data-wsf-corners={corner} className="mt-3 grid gap-5 border border-dashed border-taupe-300 bg-ivory p-5 sm:grid-cols-2">
          <article className="overflow-hidden rounded-card border border-taupe-200 bg-white">
            <div className="aspect-[3/2] bg-gradient-to-br from-blush-200 via-cream to-taupe-200" aria-hidden="true" />
            <div className="p-4">
              <p className="eyebrow">Card</p>
              <p className="mt-1 font-serif text-lg font-semibold text-charcoal">How women are reshaping leadership</p>
            </div>
          </article>
          <div className="space-y-4">
            <div className="aspect-[3/2] rounded-media bg-gradient-to-br from-plum-500 to-burgundy-500" role="img" aria-label="Image example" />
            <div className="flex flex-wrap gap-3">
              <span className="btn-primary">Button</span>
              <span className="btn-secondary">Secondary</span>
            </div>
          </div>
          <aside className="rounded-card border border-taupe-200 bg-cream p-5 sm:col-span-2">
            <p className="eyebrow">Panel / CTA</p>
            <p className="mt-1 font-serif text-xl font-semibold text-charcoal">Plan your next career move</p>
            <p className="mt-1 text-sm text-charcoal-600">In-article CTAs, callouts and panels follow the same corners.</p>
          </aside>
        </div>
      </section>

      <div className="flex items-center gap-3">
        <button type="button" onClick={save} disabled={saving || corner === saved} className="btn-primary disabled:opacity-50">
          {saving ? 'Saving…' : 'Save appearance'}
        </button>
        {corner !== saved && (
          <button type="button" onClick={() => setCorner(saved)} className="text-sm font-medium text-charcoal-600 hover:text-burgundy-600">
            Discard change
          </button>
        )}
      </div>
    </div>
  )
}
