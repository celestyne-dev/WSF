import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { login as loginApi, fetchCurrentUser } from '../../api/auth'

const storedToken = typeof window !== 'undefined' ? localStorage.getItem('wsf_access_token') : null

export const loginUser = createAsyncThunk('auth/login', async (credentials, { rejectWithValue }) => {
  const res = await loginApi(credentials)
  if (!res.success) return rejectWithValue(res.message)
  localStorage.setItem('wsf_access_token', res.accessToken)
  return res
})

export const restoreSession = createAsyncThunk('auth/restore', async (_, { rejectWithValue }) => {
  const token = localStorage.getItem('wsf_access_token')
  if (!token) return rejectWithValue('No session')
  const user = await fetchCurrentUser(token)
  if (!user) return rejectWithValue('Session expired')
  return { user, accessToken: token }
})

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    accessToken: storedToken,
    status: 'idle',
    error: null,
  },
  reducers: {
    logout(state) {
      state.user = null
      state.accessToken = null
      localStorage.removeItem('wsf_access_token')
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loginUser.pending, (state) => {
        state.status = 'loading'
        state.error = null
      })
      .addCase(loginUser.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.user = action.payload.user
        state.accessToken = action.payload.accessToken
      })
      .addCase(loginUser.rejected, (state, action) => {
        state.status = 'failed'
        state.error = action.payload || 'Login failed'
      })
      .addCase(restoreSession.fulfilled, (state, action) => {
        state.user = action.payload.user
        state.accessToken = action.payload.accessToken
      })
      .addCase(restoreSession.rejected, (state) => {
        state.user = null
        state.accessToken = null
      })
  },
})

export const { logout } = authSlice.actions
export default authSlice.reducer
