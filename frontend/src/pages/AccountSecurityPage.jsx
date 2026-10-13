import { Link } from 'react-router-dom'
import useSeo from '../hooks/useSeo'

// A simple account section, not a replacement for ChangePasswordPage — the
// password form itself still lives only at /change-password (also reused
// for the forced-change flow), so this page never duplicates that logic.
export default function AccountSecurityPage() {
  useSeo({ title: 'Security | Women Shaping Futures', robots: 'noindex, nofollow' })

  return (
    <div className="max-w-[720px]">
      <h2 className="font-serif text-2xl font-semibold text-charcoal">Security</h2>
      <p className="mt-2 text-sm text-charcoal-600">
        You can change the password you use to sign in to your WSF account at any time.
      </p>
      <Link to="/change-password" className="btn-primary mt-6 inline-block">
        Change password
      </Link>
    </div>
  )
}
