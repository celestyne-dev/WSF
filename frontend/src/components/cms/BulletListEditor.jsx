import { Plus, Trash2 } from 'lucide-react'

// A small reusable editor for a simple ordered list of plain-text bullet
// items — used wherever the CMS needs a scannable structured list (job
// responsibilities/requirements/qualifications/skills/benefits, etc.)
// rather than free-form rich content.
export default function BulletListEditor({ items, onChange, placeholder = 'Add an item…' }) {
  const list = items || []

  function updateItem(index, value) {
    const next = [...list]
    next[index] = value
    onChange(next)
  }

  function removeItem(index) {
    onChange(list.filter((_, i) => i !== index))
  }

  function addItem() {
    onChange([...list, ''])
  }

  return (
    <div className="space-y-2">
      {list.map((item, index) => (
        <div key={index} className="flex items-center gap-2">
          <input
            value={item}
            onChange={(e) => updateItem(index, e.target.value)}
            placeholder={placeholder}
            className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
          />
          <button type="button" onClick={() => removeItem(index)} aria-label="Remove item" className="shrink-0 text-charcoal-600 hover:text-rose-600">
            <Trash2 size={15} />
          </button>
        </div>
      ))}
      <button type="button" onClick={addItem} className="inline-flex items-center gap-1.5 text-xs font-semibold text-burgundy-600 hover:underline">
        <Plus size={13} /> Add item
      </button>
    </div>
  )
}
