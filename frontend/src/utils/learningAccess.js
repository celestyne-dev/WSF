// Launch access matrix for Learning programs (display side; the server's
// app/services/learning_access.py is the authority):
//   free        -> open to read; an account only adds tracked progress.
//   circle_only -> a qualifying WSF Circle member.
//   product     -> an eligible WSF Lifetime member ONLY (first-party digital
//                  WSF courses). A normal Product/Order purchase does NOT
//                  unlock the curriculum, so no price and no "Buy" action is
//                  ever shown for a course. Individual course purchase is a
//                  future phase.
//   external    -> enrollment happens with the external provider.

export function programAccessLabel(program) {
  switch (program?.accessType) {
    case 'free': return 'Free'
    case 'circle_only': return 'Included with WSF Circle'
    case 'product': return 'Premium course'
    case 'external': return 'External enrollment'
    default: return null
  }
}

export function programCardAccessLabel(program) {
  switch (program?.accessType) {
    case 'circle_only': return 'WSF Circle'
    case 'product': return 'Premium'
    case 'external': return 'External'
    default: return 'Free'
  }
}

// What a viewer WITHOUT access sees for a premium (product) course:
//   'lifetime' -> Get WSF Lifetime (eligible course, a Lifetime offer is on sale)
//   'info'     -> "Available with WSF Lifetime", no button (no offer on sale)
//   'unavailable' -> not open to enrollment (not Lifetime-eligible)
export function premiumCourseState(program, { lifetimeOnSale = false } = {}) {
  if (program?.accessType !== 'product' || program.viewerCanAccess === true) return null
  if (!program.lifetimeIncluded) return 'unavailable'
  return lifetimeOnSale ? 'lifetime' : 'info'
}
