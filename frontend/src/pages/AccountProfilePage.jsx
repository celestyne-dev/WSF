import { useSelector } from 'react-redux'
import ProfileForm from '../components/account/ProfileForm'
import useSeo from '../hooks/useSeo'

// Routed only as a child of AccountLayout, which already guards on
// accessToken/user/mustChangePassword before rendering any child route —
// so `user` is guaranteed to exist here.
export default function AccountProfilePage() {
  const user = useSelector((s) => s.auth.user)

  useSeo({ title: 'Profile | Women Shaping Futures', robots: 'noindex, nofollow' })

  return (
    <div className="max-w-[720px]">
      <h2 className="font-serif text-2xl font-semibold text-charcoal">Profile</h2>
      <p className="mt-2 text-sm text-charcoal-600">
        Update the name and bio associated with your WSF account.
      </p>
      <ProfileForm user={user} />
    </div>
  )
}
