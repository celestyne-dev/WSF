import { createSlice } from '@reduxjs/toolkit'

const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    mobileNavOpen: false,
    searchOpen: false,
  },
  reducers: {
    toggleMobileNav(state, action) {
      state.mobileNavOpen = action.payload ?? !state.mobileNavOpen
    },
    toggleSearch(state, action) {
      state.searchOpen = action.payload ?? !state.searchOpen
    },
    closeOverlays(state) {
      state.mobileNavOpen = false
      state.searchOpen = false
    },
  },
})

export const { toggleMobileNav, toggleSearch, closeOverlays } = uiSlice.actions
export default uiSlice.reducer
