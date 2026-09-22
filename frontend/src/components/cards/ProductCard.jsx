import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'
import { formatProductPrice } from '../../utils/format'

export default function ProductCard({ product }) {
  if (!product) return null
  const onSale = product.salePrice != null && product.salePrice < product.price
  const unavailable = !product.isAvailable

  return (
    <Link to={`/shop/${product.slug}`} className="group block">
      <div className="relative overflow-hidden">
        <MediaImage
          media={product.coverMedia}
          variant="card"
          mediaPath={product.coverImage}
          alt={product.name}
          width={800}
          height={800}
          aspect={1}
          className="aspect-square w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
        {unavailable && (
          <span className="absolute right-3 top-3 inline-flex items-center bg-charcoal/85 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-ivory">
            Unavailable
          </span>
        )}
      </div>
      <div className="mt-3">
        {(product.category?.name || product.type) && <span className="eyebrow">{product.category?.name || product.type}</span>}
        <h3 className="mt-1 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {product.name}
        </h3>
        {product.shortDescription && <p className="mt-1 line-clamp-2 text-sm text-charcoal-600">{product.shortDescription}</p>}
        {product.priceVisible && (
          <p className="mt-1.5 flex items-center gap-2 text-sm font-medium text-charcoal-600">
            <span className={onSale ? 'text-burgundy-600' : ''}>{formatProductPrice(onSale ? product.salePrice : product.price, product.currency)}</span>
            {onSale && <span className="text-charcoal-600/50 line-through">{formatProductPrice(product.price, product.currency)}</span>}
          </p>
        )}
      </div>
    </Link>
  )
}
