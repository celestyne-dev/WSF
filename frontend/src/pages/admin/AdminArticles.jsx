import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search } from 'lucide-react'
import { articles } from '../../mock/articles'
import { adminPipelineArticles } from '../../mock/admin'
import { getAuthorBySlug } from '../../mock/authors'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'

const rows = [
  ...articles.map((a) => ({ id: a.id, slug: a.slug, title: a.title, authorSlug: a.authorSlug, status: a.status, date: a.publishDate, editable: true })),
  ...adminPipelineArticles.map((a) => ({ id: a.id, slug: null, title: a.title, authorSlug: a.authorSlug, status: a.status, date: a.updatedAt, editable: true })),
]

export default function AdminArticles() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')

  const filtered = rows.filter(
    (r) => r.title.toLowerCase().includes(query.toLowerCase()) && (!status || r.status === status),
  )

  return (
    <div>
      <AdminPageHeader
        title="Articles"
        description="Every story in the editorial pipeline, from draft to published."
        actions={
          <Link to="/admin/articles/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New article
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search articles…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {['draft', 'in_review', 'scheduled', 'published', 'archived'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto border border-taupe-200 bg-white">
        <table className="w-full min-w-[700px] text-left text-sm">
          <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            <tr>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Author</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-taupe-200">
            {filtered.map((row) => {
              const author = getAuthorBySlug(row.authorSlug)
              return (
                <tr key={row.id}>
                  <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">{row.title}</td>
                  <td className="px-4 py-3 text-charcoal-600">{author?.name}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="px-4 py-3 text-charcoal-600">{formatDate(row.date, { month: 'short', day: 'numeric', year: 'numeric' })}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3">
                      {row.slug && (
                        <a href={`/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                          <ExternalLink size={15} />
                        </a>
                      )}
                      <Link to={`/admin/articles/${row.id}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
                        <Pencil size={15} />
                      </Link>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
