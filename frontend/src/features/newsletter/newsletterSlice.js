import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { subscribeToNewsletter } from '../../api/newsletter'

export const subscribe = createAsyncThunk('newsletter/subscribe', async (payload) => subscribeToNewsletter(payload))

const newsletterSlice = createSlice({
  name: 'newsletter',
  initialState: { status: 'idle', message: null },
  reducers: {
    resetNewsletterStatus(state) {
      state.status = 'idle'
      state.message = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(subscribe.pending, (state) => {
        state.status = 'loading'
      })
      .addCase(subscribe.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.message = action.payload.message
      })
      .addCase(subscribe.rejected, (state) => {
        state.status = 'failed'
        state.message = 'Something went wrong. Please try again.'
      })
  },
})

export const { resetNewsletterStatus } = newsletterSlice.actions
export default newsletterSlice.reducer
