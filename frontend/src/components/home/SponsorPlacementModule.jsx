import SponsorPlacementStrip from '../sponsors/SponsorPlacementStrip'

/**
 * Homepage Builder only selects which approved Sponsors-CMS placement key
 * renders here and where in the module order — SponsorPlacementStrip
 * itself remains the single authority for active status, campaign dates,
 * disclosure, sponsor URL, and logo (see Sponsors CMS). This module never
 * copies sponsor data into homepage configuration.
 */
export default function SponsorPlacementModule({ module }) {
  const placementKey = module.placementKey || 'homepage_featured'
  return <SponsorPlacementStrip placementKey={placementKey} heading={module.heading || 'Our Sponsors'} />
}
