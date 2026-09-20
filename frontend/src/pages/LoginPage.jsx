import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { loginUser } from '../features/auth/authSlice'
import useSeo from '../hooks/useSeo'

const ADMIN_ROLES = ['super_admin', 'admin', 'editor', 'author', 'moderator', 'partnerships_manager', 'opportunities_manager', 'events_manager', 'analyst']

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const status = useSelector((s) => s.auth.status)

  useSeo({ title: 'Login | Women Shaping Futures', description: 'Sign in to your Women Shaping Futures account.', robots: 'noindex, follow' })

  async function handleSubmit(e) {
    e.preventDefault()
    const result = await dispatch(loginUser({ email, password }))
    if (result.meta.requestStatus === 'fulfilled') {
      toast.success(`Welcome back, ${result.payload.user.name.split(' ')[0]}.`)
      navigate(ADMIN_ROLES.includes(result.payload.user.role) ? '/admin' : '/')
    } else {
      toast.error(result.payload || 'Login failed')
    }
  }

  return (
    <div className="container-editorial flex min-h-[70vh] items-center justify-center py-16">
      <div className="w-full max-w-sm">
        <p className="eyebrow text-center">Welcome back</p>
        <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-charcoal">Sign in to WSF</h1>
        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label htmlFor="email" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Email
            </label>
            <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <div>
            <label htmlFor="password" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Password
            </label>
            <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <button type="submit" disabled={status === 'loading'} className="btn-primary w-full disabled:opacity-60">
            {status === 'loading' ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-6 border border-dashed border-taupe-300 bg-cream p-4 text-xs leading-relaxed text-charcoal-600">
          Prototype demo: sign in as <strong>wanjiru@womenshapingfutures.org</strong> (Editor-in-Chief, super_admin) with any password of 4+ characters to view the CMS.
        </p>
      </div>
    </div>
  )
}
