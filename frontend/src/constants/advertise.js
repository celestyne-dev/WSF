export const ADVERTISE_PAGE_STATUSES = ['draft', 'published']

export const ADVERTISE_OFFERING_STATUSES = ['active', 'unavailable', 'hidden']

// hidden: no pricing shown at all. contact: "Contact for pricing", no
// amount required. starting_from: price shown as a floor. fixed: price
// shown as the exact public price.
export const ADVERTISE_PRICING_MODES = ['hidden', 'contact', 'starting_from', 'fixed']

export const ADVERTISE_PRICING_MODE_LABELS = {
  hidden: 'Hidden — no pricing shown publicly',
  contact: 'Contact for pricing',
  starting_from: 'Starting from (floor price)',
  fixed: 'Fixed price',
}
