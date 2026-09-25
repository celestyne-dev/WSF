import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, Merge, Search } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchTags, createTag, updateTag, deleteTag, mergeTags } from '../../api/taxonomies'
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

function TagFormModal({ initial, onClose, onSaved }) {
  const isNew = !initial
  const [name, setName] = useState(initial?.name || '')
  const [status, setStatus] = useState(initial?.status || 'published')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const saved = isNew ? await createTag({ name }) : await updateTag(initial.id, { name, status })
      toast.success(`Tag ${isNew ? 'created' : 'updated'}.`)
      onSaved(saved)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong saving this tag. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/70 p-4" role="dialog" aria-modal="true">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 bg-ivory p-6 shadow-card">
        <h3 className="font-serif text-lg font-semibold text-charcoal">{isNew ? 'New tag' : `Rename: ${initial.name}`}</h3>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" required />
          {name && <p className="mt-1 text-xs text-charcoal-600/60">Slug: {slugify(name)}</p>}
        </div>
        {!isNew && (
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Status</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm">
              {['published', 'archived'].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        )}
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

function MergeModal({ tags, onClose, onMerged }) {
  const [fromId, setFromId] = useState('')
  const [toId, setToId] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!fromId || !toId || fromId === toId) {
      toast.error('Choose two different tags to merge.')
      return
    }
    setSaving(true)
    try {
      await mergeTags(Number(fromId), Number(toId))
      toast.success('Tags merged.')
      onMerged()
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong merging these tags. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/70 p-4" role="dialog" aria-modal="true">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 bg-ivory p-6 shadow-card">
        <h3 className="font-serif text-lg font-semibold text-charcoal">Merge tags</h3>
        <p className="text-xs text-charcoal-600">Every article and resource tagged with the source tag will be re-tagged with the destination tag, then the source tag is deleted. This can't be undone.</p>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Merge this tag…</label>
          <select value={fromId} onChange={(e) => setFromId(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm" required>
            <option value="">— Select —</option>
            {tags.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.usageCount ?? 0} uses)
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">…into this tag</label>
          <select value={toId} onChange={(e) => setToId(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm" required>
            <option value="">— Select —</option>
            {tags.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.usageCount ?? 0} uses)
              </option>
            ))}
          </select>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn-secondary !px-4 !py-2 text-xs">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="!px-4 !py-2 text-xs font-semibold text-ivory bg-rose-600 hover:bg-rose-700 disabled:opacity-60">
            {saving ? 'Merging…' : 'Merge'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default function AdminTags() {
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(undefined)
  const [merging, setMerging] = useState(false)

  function load() {
    setError(null)
    fetchTags({ q: query, per_page: 200 })
      .then((res) => setRows(res.items))
      .catch(() => setError('Something went wrong loading tags. Please try again.'))
  }

  useEffect(load, [query])

  function handleSaved() {
    setEditing(undefined)
    load()
  }

  function handleMerged() {
    setMerging(false)
    load()
  }

  async function handleDelete(row) {
    if (!window.confirm(`Delete ${row.name}? This can't be undone.`)) return
    try {
      await deleteTag(row.id)
      toast.success('Tag deleted.')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || "This tag is referenced by content and can't be deleted. Merge it into another tag instead.")
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Tags"
        description="Lightweight secondary metadata for Articles and Resources."
        actions={
          <>
            <button type="button" onClick={() => setMerging(true)} className="btn-secondary !px-4 !py-2 text-xs">
              <Merge size={14} /> Merge tags
            </button>
            <button type="button" onClick={() => setEditing(null)} className="btn-primary !px-4 !py-2 text-xs">
              <Plus size={14} /> New tag
            </button>
          </>
        }
      />

      <div className="mb-4 flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
        <Search size={15} className="text-charcoal-600" />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search tags…" className="w-56 text-sm focus:outline-none" />
      </div>

      {error && <EmptyState title="Couldn't load tags" description={error} />}
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
                        <button type="button" onClick={() => setEditing(row)} aria-label="Rename" className="text-charcoal-600 hover:text-burgundy-600">
                          <Pencil size={15} />
                        </button>
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
          <EmptyState title="No tags match that search" description="Create a new tag to get started." />
        )
      )}

      {editing !== undefined && <TagFormModal initial={editing} onClose={() => setEditing(undefined)} onSaved={handleSaved} />}
      {merging && rows && <MergeModal tags={rows} onClose={() => setMerging(false)} onMerged={handleMerged} />}
    </div>
  )
}
