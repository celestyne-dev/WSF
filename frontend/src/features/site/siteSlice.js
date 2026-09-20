import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { fetchNavigation, fetchHomepageModules } from '../../api/site'

export const loadNavigation = createAsyncThunk('site/loadNavigation', async () => fetchNavigation())
export const loadHomepageModules = createAsyncThunk('site/loadHomepageModules', async () => fetchHomepageModules())

const siteSlice = createSlice({
  name: 'site',
  initialState: {
    navigation: null,
    homepageModules: [],
    navigationStatus: 'idle',
    homepageStatus: 'idle',
  },
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
  },
})

export default siteSlice.reducer
