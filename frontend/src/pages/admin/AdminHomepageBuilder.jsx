import { useState } from 'react'
import { toast } from 'react-toastify'
import { ChevronUp, ChevronDown, Eye, EyeOff, Save } from 'lucide-react'
import { homepageModules } from '../../mock/homepageModules'
import AdminPageHeader from '../../components/cms/AdminPageHeader'

const TYPE_LABELS = {
  hero: 'Hero',
  latest_stories: 'Latest Stories Grid',
  featured_woman: 'Featured Woman Spotlight',
  series_feature: 'Series Feature',
  opportunities: 'Opportunities',
  jobs: 'Jobs',
  topic_collection: 'Topic Collection',
  resources: 'Resources',
  events: 'Events',
  newsletter: 'Newsletter Signup',
  partners: 'Partner Logos',
}

export default function AdminHomepageBuilder() {
  const [modules, setModules] = useState([...homepageModules].sort((a, b) => a.order - b.order))

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

  function updateHeading(id, field, value) {
    setModules((prev) => prev.map((m) => (m.id === id ? { ...m, [field]: value } : m)))
  }

  return (
    <div>
      <AdminPageHeader
        title="Homepage Builder"
        description="Reorder, enable, and edit each homepage module. Changes here update the live homepage — no code required."
        actions={
          <button type="button" onClick={() => toast.success('Homepage layout saved.')} className="btn-primary !px-4 !py-2 text-xs">
            <Save size={14} /> Save layout
          </button>
        }
      />

      <div className="space-y-3">
        {modules.map((module, index) => (
          <div key={module.id} className={`border bg-white p-4 transition-opacity ${module.enabled ? 'border-taupe-200' : 'border-taupe-200 opacity-50'}`}>
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
                  <p className="text-xs font-semibold uppercase tracking-wide text-burgundy-600">{TYPE_LABELS[module.type] || module.type}</p>
                  <p className="text-sm text-charcoal-600">Position {index + 1}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => toggleEnabled(module.id)}
                className="flex items-center gap-1.5 border border-taupe-300 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-charcoal-600 hover:border-burgundy-500"
              >
                {module.enabled ? <Eye size={13} /> : <EyeOff size={13} />}
                {module.enabled ? 'Enabled' : 'Hidden'}
              </button>
            </div>

            {(module.heading !== null && module.heading !== undefined) && (
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <input
                  value={module.heading || ''}
                  onChange={(e) => updateHeading(module.id, 'heading', e.target.value)}
                  placeholder="Section heading"
                  className="border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
                />
                <input
                  value={module.subheading || ''}
                  onChange={(e) => updateHeading(module.id, 'subheading', e.target.value)}
                  placeholder="Section subheading"
                  className="border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
