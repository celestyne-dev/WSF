import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { login as loginApi, logout as logoutApi, register as registerApi, fetchCurrentUser } from '../../api/auth'
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, clearStoredAuth } from '../../api/client'

const storedToken = typeof window !== 'undefined' ? localStorage.getItem(ACCESS_TOKEN_KEY) : null

export const loginUser = createAsyncThunk('auth/login', async (credentials, { rejectWithValue }) => {
  const res = await loginApi(credentials)
  if (!res.success) return rejectWithValue(res.message)
  localStorage.setItem(ACCESS_TOKEN_KEY, res.accessToken)
  if (res.refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, res.refreshToken)
  return res
})

// Same shape/convention as loginUser above — a successful public
// registration logs the new account straight in (self-chosen password, no
// forced change), so it persists tokens the identical way.
export const registerUser = createAsyncThunk('auth/register', async (payload, { rejectWithValue }) => {
  const res = await registerApi(payload)
  if (!res.success) return rejectWithValue(res)
  localStorage.setItem(ACCESS_TOKEN_KEY, res.accessToken)
  if (res.refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, res.refreshToken)
  return res
})

// Shared by the CMS header's logout button and /account's sign-out action.
// Always clears the local session (via the `logout` reducer below) even if
// the backend blocklist call fails — logoutApi() itself never throws (see
// api/auth.js), so this thunk can't leave a half-signed-out state.
export const logoutUser = createAsyncThunk('auth/logout', async (_, { dispatch }) => {
  await logoutApi()
  dispatch(logout())
})

export const restoreSession = createAsyncThunk('auth/restore', async (_, { rejectWithValue }) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (!token) return rejectWithValue('No session')
  // A 401 here is handled by apiClient's own refresh-or-clear interceptor
  // (see api/client.js) before fetchCurrentUser's catch ever sees it, so by
  // the time `user` comes back null, any invalid token has already been
  // cleared from storage — this rejection just needs to reset UI state.
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
      clearStoredAuth()
    },
    // After a successful POST /auth/change-password — replaces the
    // authenticated user in place (mustChangePassword now false) with no
    // token change, so the session continues uninterrupted; no logout/login
    // round trip needed.
    setUser(state, action) {
      state.user = action.payload
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
      .addCase(registerUser.pending, (state) => {
        state.status = 'loading'
        state.error = null
      })
      .addCase(registerUser.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.user = action.payload.user
        state.accessToken = action.payload.accessToken
      })
      .addCase(registerUser.rejected, (state, action) => {
        state.status = 'failed'
        state.error = action.payload?.message || 'Registration failed'
      })
      .addCase(restoreSession.fulfilled, (state, action) => {
        state.user = action.payload.user
        state.accessToken = action.payload.accessToken
      })
      .addCase(restoreSession.rejected, (state) => {
        state.user = null
        state.accessToken = null
        clearStoredAuth()
      })
  },
})

export const { logout, setUser } = authSlice.actions
export default authSlice.reducer
