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
  reducers: {},
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

export default siteSlice.reducer
