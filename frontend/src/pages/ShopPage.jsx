import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchProducts, fetchProductCategories } from '../api/products'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import ProductCard from '../components/cards/ProductCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

const TYPE_OPTIONS = [
  { value: 'digital', label: 'Digital' },
  { value: 'downloadable', label: 'Downloadable' },
  { value: 'physical', label: 'Physical' },
  { value: 'service', label: 'Service' },
  { value: 'other', label: 'Other' },
]

export default function ShopPage() {
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const [category, setCategory] = useState('')
  const [free, setFree] = useState('')
  const [categories, setCategories] = useState([])
  const [products, setProducts] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Shop | Women Shaping Futures',
    description: 'Digital products, guides, templates, and workbooks from Women Shaping Futures.',
    canonical: 'https://womenshapingfutures.org/shop',
  })

  useEffect(() => {
    fetchProductCategories().then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchProducts({ query, type, category, free: free || undefined, pageSize: 100 })
      .then((res) => active && setProducts(res.items))
      .catch(() => active && setError('Something went wrong loading the shop. Please try again.'))
    return () => {
      active = false
    }
  }, [query, type, category, free])

  return (
    <div>
      <PageHeader eyebrow="Shop" title="WSF Shop" description="Digital guides, templates, and workbooks from Women Shaping Futures." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
            <Search size={15} className="text-charcoal-600" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search products…" className="w-52 text-sm focus:outline-none" />
          </div>
          <FilterSelect label="Type" value={type} onChange={setType} options={TYPE_OPTIONS} />
          <FilterSelect label="Category" value={category} onChange={setCategory} options={categories.map((c) => ({ value: c.slug, label: c.name }))} />
          <FilterSelect label="Price" value={free} onChange={setFree} options={[{ value: 'true', label: 'Free only' }]} />
        </div>

        {error && (
          <div className="mt-8">
            <EmptyState title="Couldn't load the shop" description={error} />
          </div>
        )}
        {!error && products === null && <PageLoader />}
        {!error && products !== null && (
          products.length ? (
            <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {products.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState title="Nothing in the shop yet" description="Check back soon for new guides, templates, and workbooks." />
            </div>
          )
        )}
      </div>
    </div>
  )
}
