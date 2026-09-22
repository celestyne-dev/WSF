import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search, Star } from 'lucide-react'
import { fetchProducts, fetchProductCategories } from '../../api/products'
import { formatProductPrice } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const TYPES = ['digital', 'physical', 'downloadable', 'service', 'other']
const STATUSES = ['draft', 'active', 'unavailable', 'archived']

export default function AdminProducts() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [category, setCategory] = useState('')
  const [categories, setCategories] = useState([])
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchProductCategories().then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchProducts({ status, query, type, category, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading products. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query, type, category])

  return (
    <div>
      <AdminPageHeader
        title="Products"
        description="Digital, downloadable, and physical items sold through the WSF Shop."
        actions={
          <Link to="/admin/products/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New product
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search products…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load products" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[880px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Price</th>
                  <th className="px-4 py-3">Availability</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">
                      {row.name}
                      {row.featured && (
                        <span className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] font-semibold uppercase tracking-wide text-burgundy-600">
                          <Star size={10} /> Featured
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.type}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.category?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {row.priceVisible ? formatProductPrice(row.price, row.currency) : 'Hidden'}
                      {row.salePrice != null && row.priceVisible && (
                        <span className="ml-1 text-xs text-charcoal-600/60 line-through">{formatProductPrice(row.price, row.currency)}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.isAvailable ? 'Available' : 'Unavailable'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'active' && (
                          <a href={`/shop/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/products/${row.slug}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
                          <Pencil size={15} />
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No products match those filters yet" description="Create a new product or broaden your search." />
        )
      )}
    </div>
  )
}
