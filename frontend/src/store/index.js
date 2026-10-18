import { configureStore } from '@reduxjs/toolkit'
import authReducer from '../features/auth/authSlice'
import siteReducer, { siteInitialState } from '../features/site/siteSlice'
import uiReducer from '../features/navigation/uiSlice'
import newsletterReducer from '../features/newsletter/newsletterSlice'
import { mapHomepageModule } from '../api/site'
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
function buildPreloadedState() {
  const bootstrap = readBootstrap('homepage')
  if (!bootstrap) return undefined
  consumeBootstrap('homepage')
  return {
    site: {
      ...siteInitialState,
      homepageModules: (bootstrap.modules || []).map(mapHomepageModule),
      homepageStatus: 'succeeded',
      leadArticle: bootstrap.leadArticle ? mapArticle(bootstrap.leadArticle) : null,
    },
  }
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
