import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { login as loginApi, logout as logoutApi, register as registerApi, resumeSession } from '../../api/auth'
import { USE_MOCK, setAccessToken, waitForSession } from '../../api/client'

// Session model: the access token is kept only in memory (here and in
// api/client.js); the refresh credential is an HttpOnly cookie that
// JavaScript never sees. On every page load restoreSession() asks the
// server for a new access token with that cookie (silent refresh).
// `sessionChecked` is false until that first answer arrives, so guards can
// wait instead of bouncing a signed-in member to /login.

export const loginUser = createAsyncThunk('auth/login', async (credentials, { rejectWithValue }) => {
  const res = await loginApi(credentials)
  if (!res.success) return rejectWithValue(res.message)
  if (res.twoFactor || res.deletionPending) return res // a second step is needed; no session yet
  setAccessToken(res.accessToken)
  return res
})

// Same shape/convention as loginUser above — a successful public
// registration logs the new account straight in (self-chosen password, no
// forced change): the server sets the refresh cookie the identical way.
export const registerUser = createAsyncThunk('auth/register', async (payload, { rejectWithValue }) => {
  const res = await registerApi(payload)
  if (!res.success) return rejectWithValue(res)
  setAccessToken(res.accessToken)
  return res
})

// Shared by the CMS header's logout button and /account's/MobileNav's
// sign-out actions. Clears the local session IMMEDIATELY (not after the
// request) so a slow or offline backend can never leave the browser looking
// signed in; logoutApi() captures the access token first, then revokes the
// refresh session server-side and clears the cookie (never throws).
export const logoutUser = createAsyncThunk('auth/logout', async (_, { dispatch }) => {
  const backendLogout = logoutApi()
  dispatch(logout())
  await backendLogout
})

// Silent refresh on page load (dispatched once by store.js).
export const restoreSession = createAsyncThunk('auth/restore', async (_, { rejectWithValue }) => {
  const pending = resumeSession()
  waitForSession(pending) // API calls made meanwhile wait for the answer
  const session = await pending
  if (!session) return rejectWithValue('No session')
  return session
})

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    accessToken: null,
    // Mock mode has no server session to restore.
    sessionChecked: USE_MOCK,
    status: 'idle',
    error: null,
  },
  reducers: {
    logout(state) {
      state.user = null
      state.accessToken = null
      setAccessToken(null)
    },
    // The API client recovered (or lost) the session on its own, e.g. a 401
    // answered by a silent refresh. Keeps this store in step with it.
    sessionTokenChanged(state, action) {
      state.accessToken = action.payload || null
      if (!state.accessToken) state.user = null
    },
    // Replaces the signed-in user in place (e.g. after a profile edit), with
    // no token change. (A password change instead ends the session: see
    // ChangePasswordPage.)
    setUser(state, action) {
      state.user = action.payload
    },
    // A two-factor sign-in step (challenge or set-up) completed: the server
    // has set the refresh cookie and returned the user + access token.
    signedIn(state, action) {
      state.user = action.payload.user
      state.accessToken = action.payload.accessToken
      state.status = 'succeeded'
      setAccessToken(action.payload.accessToken)
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loginUser.pending, (state) => {
        state.status = 'loading'
        state.error = null
      })
      .addCase(loginUser.fulfilled, (state, action) => {
        if (action.payload.twoFactor || action.payload.deletionPending) {
          state.status = 'idle' // the login page shows the two-factor step
          return
        }
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
        state.sessionChecked = true
      })
      .addCase(restoreSession.rejected, (state) => {
        // A sign-in that completed while the check was running wins.
        if (!state.user) state.accessToken = null
        state.sessionChecked = true
      })
  },
})

export const { logout, setUser, sessionTokenChanged, signedIn } = authSlice.actions
export default authSlice.reducer
