import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, Archive } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchCategoriesAdmin, createCategory, updateCategory, setCategoryStatus, deleteCategory } from '../../api/taxonomies'
import { RESERVED_SLUGS } from '../../constants/routes'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

function slugify(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

const STATUSES = ['draft', 'published', 'archived']

function CategoryFormModal({ initial, onClose, onSaved }) {
  const isNew = !initial
  const [name, setName] = useState(initial?.name || '')
  const [slug, setSlug] = useState(initial?.slug || '')
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [description, setDescription] = useState(initial?.description || '')
  const [sortOrder, setSortOrder] = useState(initial?.sortOrder || 0)
  const [status, setStatus] = useState(initial?.status || 'draft')
  const [saving, setSaving] = useState(false)

  function handleNameChange(value) {
    setName(value)
    if (!slugTouched) setSlug(slugify(value))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!slug) {
      toast.error('Slug is required.')
      return
    }
    if (RESERVED_SLUGS.includes(slug)) {
      toast.error(`"${slug}" is a reserved system route and cannot be used as a category slug.`)
      return
    }
    setSaving(true)
    try {
      const payload = { name, slug, description: description || null, sortOrder: Number(sortOrder) || 0, status }
      const saved = isNew ? await createCategory(payload) : await updateCategory(initial.id, payload)
      toast.success(`Category ${isNew ? 'created' : 'updated'}.`)
      onSaved(saved)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong saving this category. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/70 p-4" role="dialog" aria-modal="true">
      <form onSubmit={handleSubmit} className="w-full max-w-md space-y-4 bg-ivory p-6 shadow-card">
        <h3 className="font-serif text-lg font-semibold text-charcoal">{isNew ? 'New category' : `Edit: ${initial.name}`}</h3>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Name</label>
          <input value={name} onChange={(e) => handleNameChange(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" required />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Slug</label>
          <input
            value={slug}
            onChange={(e) => {
              setSlugTouched(true)
              setSlug(slugify(e.target.value))
            }}
            className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
            required
          />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Description</label>
          <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Order</label>
            <input type="number" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Status</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm">
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn-secondary !px-4 !py-2 text-xs">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
            {saving ? 'Saving…' : isNew ? 'Create' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default function AdminCategories() {
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(undefined) // undefined = closed, null = new, object = editing

  function load() {
    setError(null)
    fetchCategoriesAdmin({ per_page: 100 })
      .then((res) => setRows(res.items))
      .catch(() => setError('Something went wrong loading categories. Please try again.'))
  }

  useEffect(load, [])

  function handleSaved() {
    setEditing(undefined)
    load()
  }

  async function handleArchive(row) {
    try {
      await setCategoryStatus(row.id, 'archived')
      toast.success('Category archived.')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong archiving this category.')
    }
  }

  async function handleDelete(row) {
    if (!window.confirm(`Delete ${row.name}? This can't be undone.`)) return
    try {
      await deleteCategory(row.id)
      toast.success('Category deleted.')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || "This category is referenced by articles and can't be deleted. Try archiving instead.")
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Categories"
        description="A single classification value for Articles — no hierarchy, no public detail page."
        actions={
          <button type="button" onClick={() => setEditing(null)} className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New category
          </button>
        }
      />

      {error && <EmptyState title="Couldn't load categories" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Usage</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">{row.name}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.usageCount ?? 0}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        <button type="button" onClick={() => setEditing(row)} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
                          <Pencil size={15} />
                        </button>
                        {row.status !== 'archived' && (
                          <button type="button" onClick={() => handleArchive(row)} aria-label="Archive" className="text-charcoal-600 hover:text-burgundy-600">
                            <Archive size={15} />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDelete(row)}
                          disabled={row.usageCount > 0}
                          aria-label="Delete"
                          className="text-charcoal-600 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-30"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No categories yet" description="Create a category to start classifying articles." />
        )
      )}

      {editing !== undefined && <CategoryFormModal initial={editing} onClose={() => setEditing(undefined)} onSaved={handleSaved} />}
    </div>
  )
}
