import { configureStore } from '@reduxjs/toolkit'
import authReducer from '../features/auth/authSlice'
import siteReducer, { siteInitialState } from '../features/site/siteSlice'
import uiReducer from '../features/navigation/uiSlice'
import newsletterReducer from '../features/newsletter/newsletterSlice'
import { mapHomepageModule, mapNavigation, mapSiteSettings } from '../api/site'
import { mapPublicFooter } from '../api/footer'
import { mapArticle } from '../api/articles'
import { readBootstrap, consumeBootstrap } from '../utils/bootstrap'

// WSF SEO Phase 2D — a hard load of "/" already has its homepage modules
// (and, when the hero module has one, its resolved lead Article) embedded
// in the initial HTML by the server (see spa_shell.py's
// render_homepage_shell). Reading that HERE, once, at module-evaluation
// time — rather than inside a component effect — means the store itself
// starts already "loaded": HomePage.jsx's existing
// `if (homepageStatus === 'idle') dispatch(loadHomepageModules())` guard
// then naturally never fires (status is already 'succeeded'), so there's
// no PageLoader flash to avoid in the component at all. Module-evaluation
// code runs exactly once per real page load — unlike a component render,
// it is never double-invoked by React 18 StrictMode in development — so
// this is also where the bootstrap script tag actually gets consumed
// (see utils/bootstrap.js's own docstring for why that's deliberately
// NOT coupled to readBootstrap itself).
// Every server-rendered HTML page also carries a one-shot "shell"
// bootstrap (spa_shell._set_shell_bootstrap): the exact GET
// /public/navigation, /public/settings and /public/footer bodies. Seeding
// them here lets the header, footer and consent banner render their final
// content on React's first frame (matching the server's first-paint
// header, backend services/first_paint.py) and skips those three startup
// requests. Statuses are 'succeeded', so PublicLayout's idle guards never
// refetch them; in-app behavior after the hard load is unchanged.
function shellState() {
  const bootstrap = readBootstrap('shell', 'shell')
  if (!bootstrap?.data) return {}
  consumeBootstrap('shell')
  const { navigation, settings, footer } = bootstrap.data
  const state = {}
  if (navigation) Object.assign(state, { navigation: mapNavigation(navigation), navigationStatus: 'succeeded' })
  if (settings) Object.assign(state, { settings: mapSiteSettings(settings), settingsStatus: 'succeeded' })
  if (footer) Object.assign(state, { footer: mapPublicFooter(footer), footerStatus: 'succeeded' })
  return state
}

function homepageState() {
  const bootstrap = readBootstrap('homepage')
  if (!bootstrap) return {}
  consumeBootstrap('homepage')
  return {
    homepageModules: (bootstrap.modules || []).map(mapHomepageModule),
    homepageStatus: 'succeeded',
    leadArticle: bootstrap.leadArticle ? mapArticle(bootstrap.leadArticle) : null,
  }
}

export function buildPreloadedState() {
  const site = { ...shellState(), ...homepageState() }
  if (!Object.keys(site).length) return undefined
  return { site: { ...siteInitialState, ...site } }
}

export const store = configureStore({
  reducer: {
    auth: authReducer,
    site: siteReducer,
    ui: uiReducer,
    newsletter: newsletterReducer,
  },
  preloadedState: buildPreloadedState(),
})
