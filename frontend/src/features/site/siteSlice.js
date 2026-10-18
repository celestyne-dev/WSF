import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { fetchNavigation, fetchHomepageModules, fetchSiteSettings } from '../../api/site'
import { fetchFooter } from '../../api/footer'
import { fetchCountries } from '../../api/geography'

export const loadNavigation = createAsyncThunk('site/loadNavigation', async () => fetchNavigation())
export const loadHomepageModules = createAsyncThunk('site/loadHomepageModules', async () => fetchHomepageModules())
export const loadCountries = createAsyncThunk('site/loadCountries', async () => fetchCountries())
export const loadSiteSettings = createAsyncThunk('site/loadSiteSettings', async () => fetchSiteSettings())
export const loadFooter = createAsyncThunk('site/loadFooter', async () => fetchFooter())

// Exported so store/index.js can seed a hard-loaded "/"'s preloadedState
// from the server's homepage bootstrap (see utils/bootstrap.js) without
// duplicating — and risking drifting from — this shape. `leadArticle` is
// WSF SEO Phase 2D's one addition: the hero module's already-resolved
// public lead Article, present only when the server bootstrap provided
// one — see HeroModule.jsx, which reads this before falling back to its
// own fetchArticleBySlug.
export const siteInitialState = {
  navigation: null,
  homepageModules: [],
  leadArticle: null,
  countries: [],
  settings: {},
  footer: null,
  navigationStatus: 'idle',
  homepageStatus: 'idle',
  countriesStatus: 'idle',
  settingsStatus: 'idle',
  footerStatus: 'idle',
}

const siteSlice = createSlice({
  name: 'site',
  initialState: siteInitialState,
  reducers: {
    // WSF SEO Phase 2D correction — `leadArticle` only ever means "the
    // server's homepage bootstrap already resolved this Article for the
    // CURRENT hard load" (see store/index.js's preloadedState). It must
    // never survive past that hard load's homepage visit: HomePage.jsx
    // dispatches this from its unmount cleanup so a later SPA navigation
    // back to "/" finds `leadArticle` already null and HeroModule falls
    // through to its normal fetchArticleBySlug path instead of reusing a
    // now-stale bootstrap Article. Deliberately narrow — only this one
    // field; homepageModules/homepageStatus (and everything else) keep
    // their existing "fetched once per session" caching behavior.
    clearHomepageBootstrapLead(state) {
      state.leadArticle = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadNavigation.pending, (state) => {
        state.navigationStatus = 'loading'
      })
      .addCase(loadNavigation.fulfilled, (state, action) => {
        state.navigationStatus = 'succeeded'
        state.navigation = action.payload
      })
      .addCase(loadHomepageModules.pending, (state) => {
        state.homepageStatus = 'loading'
      })
      .addCase(loadHomepageModules.fulfilled, (state, action) => {
        state.homepageStatus = 'succeeded'
        state.homepageModules = action.payload
        // A freshly fetched module list must never stay paired with an
        // older bootstrap-resolved (or now-stale) lead Article — see
        // HeroModule.jsx, which only trusts `leadArticle` when it
        // matches the CURRENT hero module's `leadArticleSlug`. This
        // thunk only ever runs for a real client-side fetch (the
        // preloadedState path in store/index.js never dispatches it),
        // so it's always correct to null this out here.
        state.leadArticle = null
      })
      .addCase(loadCountries.pending, (state) => {
        state.countriesStatus = 'loading'
      })
      .addCase(loadCountries.fulfilled, (state, action) => {
        state.countriesStatus = 'succeeded'
        state.countries = action.payload
      })
      .addCase(loadSiteSettings.pending, (state) => {
        state.settingsStatus = 'loading'
      })
      .addCase(loadSiteSettings.fulfilled, (state, action) => {
        state.settingsStatus = 'succeeded'
        state.settings = action.payload
      })
      .addCase(loadFooter.pending, (state) => {
        state.footerStatus = 'loading'
      })
      .addCase(loadFooter.fulfilled, (state, action) => {
        state.footerStatus = 'succeeded'
        state.footer = action.payload
      })
      .addCase(loadFooter.rejected, (state) => {
        state.footerStatus = 'failed'
      })
  },
})

export const { clearHomepageBootstrapLead } = siteSlice.actions

export default siteSlice.reducer
