import { configureStore } from '@reduxjs/toolkit'
import authReducer from '../features/auth/authSlice'
import siteReducer from '../features/site/siteSlice'
import uiReducer from '../features/navigation/uiSlice'
import newsletterReducer from '../features/newsletter/newsletterSlice'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    site: siteReducer,
    ui: uiReducer,
    newsletter: newsletterReducer,
  },
})
