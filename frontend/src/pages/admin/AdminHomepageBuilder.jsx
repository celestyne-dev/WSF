import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { ChevronUp, ChevronDown, Eye, EyeOff, Save, Plus, Trash2, AlertTriangle, ExternalLink } from 'lucide-react'
import { fetchAdminHomepage, saveAdminHomepage } from '../../api/admin'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import HomepageModuleFields from '../../components/cms/HomepageModuleFields'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { HOMEPAGE_MODULE_REGISTRY, newModuleDefaults } from '../../constants/homepageModules'

let tempIdCounter = 0
function tempId() {
  tempIdCounter -= 1
  return tempIdCounter
}

export default function AdminHomepageBuilder() {
  const [modules, setModules] = useState(undefined)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [addOpen, setAddOpen] = useState(false)

  function load() {
    setError(null)
    fetchAdminHomepage()
      .then((data) => setModules([...data].sort((a, b) => a.order - b.order)))
      .catch(() => setError('Something went wrong loading the homepage builder. Please try again.'))
  }

  useEffect(load, [])

  function move(index, direction) {
    setModules((prev) => {
      const next = [...prev]
      const target = index + direction
      if (target < 0 || target >= next.length) return prev
      ;[next[index], next[target]] = [next[target], next[index]]
      return next.map((m, i) => ({ ...m, order: i + 1 }))
    })
  }

  function toggleEnabled(id) {
    setModules((prev) => prev.map((m) => (m.id === id ? { ...m, enabled: !m.enabled } : m)))
  }

  function updateModule(id, next) {
    setModules((prev) => prev.map((m) => (m.id === id ? next : m)))
  }

  function removeModule(id) {
    const target = modules.find((m) => m.id === id)
    if (!window.confirm(`Remove the "${HOMEPAGE_MODULE_REGISTRY[target.type]?.label || target.type}" section? This only removes it from the homepage — nothing it references is deleted.`)) {
      return
    }
    setModules((prev) => prev.filter((m) => m.id !== id).map((m, i) => ({ ...m, order: i + 1 })))
  }

  function addModule(type) {
    setModules((prev) => [...prev, { id: tempId(), ...newModuleDefaults(type), order: prev.length + 1, warnings: [] }])
    setAddOpen(false)
  }

  const hasHero = modules?.some((m) => m.type === 'hero')

  async function handleSave() {
    setSaving(true)
    try {
      const saved = await saveAdminHomepage(modules)
      setModules([...saved].sort((a, b) => a.order - b.order))
      toast.success('Homepage published.')
    } catch (err) {
      const message = err?.response?.data?.error?.message
      toast.error(message || 'Something went wrong saving the homepage layout. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (error) return <EmptyState title="Couldn't load the homepage builder" description={error} />
  if (modules === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title="Homepage Builder"
        description="Add, remove, reorder, and configure homepage sections. Saving publishes immediately to the live homepage."
        actions={
          <>
            <a href="/" target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
              <ExternalLink size={14} /> View live
            </a>
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
              <Save size={14} /> {saving ? 'Publishing…' : 'Save & publish'}
            </button>
          </>
        }
      />

      <div className="space-y-3">
        {modules.map((module, index) => {
          const spec = HOMEPAGE_MODULE_REGISTRY[module.type]
          return (
            <div key={module.id} className={`border bg-white p-4 transition-opacity ${module.enabled ? 'border-taupe-200' : 'border-taupe-200 opacity-60'}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <button type="button" onClick={() => move(index, -1)} disabled={index === 0} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-20">
                      <ChevronUp size={16} />
                    </button>
                    <button type="button" onClick={() => move(index, 1)} disabled={index === modules.length - 1} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-20">
                      <ChevronDown size={16} />
                    </button>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-burgundy-600">{spec?.label || module.type}</p>
                    <p className="text-sm text-charcoal-600">Position {index + 1}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => toggleEnabled(module.id)}
                    className="flex items-center gap-1.5 border border-taupe-300 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-charcoal-600 hover:border-burgundy-500"
                  >
                    {module.enabled ? <Eye size={13} /> : <EyeOff size={13} />}
                    {module.enabled ? 'Enabled' : 'Hidden'}
                  </button>
                  <button
                    type="button"
                    onClick={() => removeModule(module.id)}
                    aria-label="Remove section"
                    className="flex h-8 w-8 items-center justify-center text-charcoal-600 hover:text-rose-600"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              {module.warnings?.length > 0 && (
                <div className="mt-3 flex items-start gap-2 border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                  <ul className="space-y-0.5">
                    {module.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              <HomepageModuleFields module={module} onChange={(next) => updateModule(module.id, next)} />
            </div>
          )
        })}
      </div>

      <div className="relative mt-4">
        <button type="button" onClick={() => setAddOpen((o) => !o)} className="btn-secondary !px-4 !py-2 text-xs">
          <Plus size={14} /> Add section
        </button>
        {addOpen && (
          <ul className="absolute z-10 mt-1 max-h-72 w-64 overflow-y-auto border border-taupe-300 bg-white shadow-lg">
            {Object.entries(HOMEPAGE_MODULE_REGISTRY).map(([type, spec]) => {
              const disabled = spec.singleton && hasHero && type === 'hero'
              return (
                <li key={type}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => addModule(type)}
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-taupe-100 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {spec.label}
                    {disabled && <span className="text-xs text-charcoal-600">Already added</span>}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
