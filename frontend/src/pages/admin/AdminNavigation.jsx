import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { Plus, Save, ExternalLink } from 'lucide-react'
import { fetchAdminNavigation, saveMenu } from '../../api/navigation'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import NavigationItemRow from '../../components/cms/NavigationItemRow'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { EDITABLE_MENUS, newNavItem } from '../../constants/navigationItems'

export default function AdminNavigation() {
  const [menus, setMenus] = useState(undefined)
  const [error, setError] = useState(null)
  const [activeKey, setActiveKey] = useState(EDITABLE_MENUS[0].key)
  const [saving, setSaving] = useState(false)

  function load() {
    setError(null)
    fetchAdminNavigation()
      .then((data) => setMenus(data))
      .catch(() => setError('Something went wrong loading navigation. Please try again.'))
  }

  useEffect(load, [])

  const activeMeta = EDITABLE_MENUS.find((m) => m.key === activeKey)
  const activeMenu = menus?.find((m) => m.key === activeKey)
  const items = activeMenu?.items || []
  const heading = activeMenu?.heading || ''

  function updateMenuState(nextItems, nextHeading = heading) {
    setMenus((prev) =>
      prev.map((m) => (m.key === activeKey ? { ...m, items: nextItems, heading: nextHeading } : m))
    )
  }

  function updateItem(index, nextItem) {
    const next = [...items]
    next[index] = nextItem
    updateMenuState(next)
  }

  function removeItem(index) {
    const target = items[index]
    if (!window.confirm(`Remove "${target.label || 'this item'}" from the menu? This never deletes the Topic/Series/Page/content it links to.`)) return
    updateMenuState(items.filter((_, i) => i !== index))
  }

  function moveItem(index, direction) {
    const next = [...items]
    const target = index + direction
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    updateMenuState(next)
  }

  function addItem() {
    updateMenuState([...items, newNavItem('route')])
  }

  async function handleSave() {
    setSaving(true)
    try {
      const saved = await saveMenu(activeKey, heading, items)
      setMenus((prev) => {
        const others = prev.filter((m) => !saved.some((s) => s.key === m.key))
        return [...others, ...saved]
      })
      toast.success('Navigation published.')
    } catch (err) {
      const message = err?.response?.data?.error?.message
      toast.error(message || 'Something went wrong saving navigation. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (error) return <EmptyState title="Couldn't load navigation" description={error} />
  if (menus === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title="Navigation"
        description="Manage the primary menu, utility bar, and footer columns. Saving publishes that section immediately — other sections are untouched."
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

      <div className="mb-4 flex flex-wrap gap-2 border-b border-taupe-200 pb-3">
        {EDITABLE_MENUS.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setActiveKey(m.key)}
            className={`px-3 py-1.5 text-xs font-semibold uppercase tracking-wide ${
              activeKey === m.key ? 'bg-burgundy-600 text-ivory' : 'border border-taupe-300 text-charcoal-600 hover:border-burgundy-500'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {activeMeta.hasHeading && (
        <div className="mb-4 max-w-sm">
          <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Column heading</label>
          <input
            value={heading}
            onChange={(e) => updateMenuState(items, e.target.value)}
            className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
          />
        </div>
      )}

      <div className="space-y-2">
        {items.length === 0 && <EmptyState title="No items yet" description="Add the first item for this menu." />}
        {items.map((item, index) => (
          <NavigationItemRow
            key={item.id}
            item={item}
            depth={1}
            siblingCount={items.length}
            index={index}
            onChange={(next) => updateItem(index, next)}
            onRemove={removeItem}
            onMove={moveItem}
          />
        ))}
      </div>

      <button type="button" onClick={addItem} className="btn-secondary mt-4 !px-4 !py-2 text-xs">
        <Plus size={14} /> Add item
      </button>
    </div>
  )
}
