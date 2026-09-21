export * from './topics'
export * from './authors'
export * from './organizations'
export * from './series'
export * from './people'
export * from './articles'
export * from './jobs'
export * from './opportunities'
export * from './events'
export * from './resources'
export * from './navigation'
export * from './homepageModules'
export * from './newsletter'
export * from './admin'

// RESERVED_SLUGS lives in ../constants/routes.js — it's a static route
// constant, not mock content, and importing it from here would pull the
// entire mock dataset into any bundle that only needed the slug list.
