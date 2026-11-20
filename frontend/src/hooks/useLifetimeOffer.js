import { useEffect, useState } from 'react'
import { fetchCirclePlans } from '../api/circle'

// Whether a WSF Lifetime plan is actually on sale, fetched at most once per
// page load and shared by every caller — so "Included with WSF Lifetime"
// is only advertised while someone can really join.
let cache = null

export function loadLifetimeOffer() {
  if (!cache) {
    cache = fetchCirclePlans()
      .then((res) => {
        const plans = Array.isArray(res) ? res : res?.items || []
        return plans.filter((p) => p.isLifetime || p.billingInterval === 'lifetime')
      })
      .catch(() => {
        cache = null
        return []
      })
  }
  return cache
}

export default function useLifetimeOffer(enabled = true) {
  const [plans, setPlans] = useState(null)
  useEffect(() => {
    if (!enabled) return undefined
    let active = true
    loadLifetimeOffer().then((list) => active && setPlans(list))
    return () => {
      active = false
    }
  }, [enabled])
  return { plans: plans || [], available: !!plans && plans.length > 0, loaded: plans !== null }
}
