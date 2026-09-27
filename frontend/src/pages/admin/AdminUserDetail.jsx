import { useEffect, useState } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { Save, KeyRound } from 'lucide-react'
import {
  fetchAdminUser,
  createAdminUser,
  updateAdminUser,
  setAdminUserStatus,
  assignAdminUserRoles,
  resetAdminUserPassword,
  fetchAdminRoles,
} from '../../api/admin'
import { hasRole } from '../../utils/permissions'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
        {label} {hint && <span className="normal-case text-charcoal-600/60">— {hint}</span>}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

// Shown exactly once, right after creation or a password reset — the
// plaintext value is never retrievable again afterward (see backend
// app/services/user_admin.py). No email-delivery flow exists in this
// app, so relaying this to the new/reset staff member is a manual,
// out-of-band step for whoever runs this action.
function TemporaryPasswordNotice({ password, onDismiss }) {
  return (
    <div className="mb-6 border border-burgundy-300 bg-blush-50 p-4">
      <p className="text-sm font-semibold text-charcoal">Temporary password — shown once</p>
      <p className="mt-1 text-xs text-charcoal-600">
        Relay this to the staff member yourself (there is no automated invitation email). It cannot be retrieved again after you leave this page —
        use "Reset password" below if it's lost.
      </p>
      <div className="mt-3 flex items-center gap-3">
        <code className="border border-taupe-300 bg-white px-3 py-2 text-sm">{password}</code>
        <button type="button" onClick={onDismiss} className="text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
          Dismiss
        </button>
      </div>
    </div>
  )
}

export default function AdminUserDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const isNew = id === undefined
  const currentUser = useSelector((s) => s.auth.user)
  const isSelf = !isNew && currentUser?.id === Number(id)
  const canGrantSuperAdmin = hasRole(currentUser, 'super_admin')

  const [user, setUser] = useState(isNew ? null : undefined)
  const [roles, setRoles] = useState([])
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', roleNames: [], isActive: true })
  const [saving, setSaving] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [temporaryPassword, setTemporaryPassword] = useState(location.state?.temporaryPassword || null)
  const [confirmAction, setConfirmAction] = useState(null)

  useEffect(() => {
    fetchAdminRoles().then(setRoles).catch(() => {})
  }, [])

  useEffect(() => {
    if (isNew) return
    let active = true
    fetchAdminUser(id)
      .then((u) => {
        if (!active) return
        setUser(u)
        setForm({ firstName: u.firstName, lastName: u.lastName, email: u.email, roleNames: u.roles, isActive: u.isActive })
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else if (err?.response?.status === 403) setLoadError("You don't have permission to view this user.")
        else setLoadError('Something went wrong loading this user. Please try again.')
      })
    return () => {
      active = false
    }
  }, [id, isNew])

  function toggleRole(key) {
    setForm((prev) => ({
      ...prev,
      roleNames: prev.roleNames.includes(key) ? prev.roleNames.filter((r) => r !== key) : [...prev.roleNames, key],
    }))
  }

  function errorMessage(err, fallback) {
    return err?.response?.data?.error?.message || fallback
  }

  async function handleCreate() {
    setSaving(true)
    try {
      const { user: created, temporaryPassword: pw } = await createAdminUser({
        email: form.email,
        firstName: form.firstName,
        lastName: form.lastName,
        roleNames: form.roleNames,
        isActive: form.isActive,
      })
      toast.success('Staff account created.')
      navigate(`/admin/users/${created.id}`, { state: { temporaryPassword: pw } })
    } catch (err) {
      toast.error(errorMessage(err, 'Something went wrong creating this user. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveIdentity() {
    setSaving(true)
    try {
      const updated = await updateAdminUser(id, { firstName: form.firstName, lastName: form.lastName, email: form.email })
      setUser((prev) => ({ ...prev, ...updated }))
      toast.success('Profile updated.')
    } catch (err) {
      toast.error(errorMessage(err, 'Something went wrong saving this user.'))
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveRoles() {
    setSaving(true)
    try {
      const updated = await assignAdminUserRoles(id, form.roleNames)
      setUser((prev) => ({ ...prev, ...updated }))
      toast.success('Roles updated.')
    } catch (err) {
      toast.error(errorMessage(err, 'Something went wrong updating roles.'))
    } finally {
      setSaving(false)
    }
  }

  async function handleToggleStatus() {
    try {
      const updated = await setAdminUserStatus(id, !user.isActive)
      setUser((prev) => ({ ...prev, ...updated }))
      setForm((prev) => ({ ...prev, isActive: updated.isActive }))
      toast.success(updated.isActive ? 'Account activated.' : 'Account deactivated.')
    } catch (err) {
      toast.error(errorMessage(err, 'Something went wrong changing this account.'))
    } finally {
      setConfirmAction(null)
    }
  }

  async function handleResetPassword() {
    try {
      const pw = await resetAdminUserPassword(id)
      setTemporaryPassword(pw)
      toast.success('Password reset.')
    } catch (err) {
      toast.error(errorMessage(err, 'Something went wrong resetting the password.'))
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this user" description={loadError} />
  if (notFound) return <EmptyState title="User not found" description="This account may have been removed or the URL is incorrect." />
  if (!isNew && user === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'Add user' : user.name}
        description={isNew ? 'Create an internal WSF CMS staff account — not a Community Member, Author, or Person profile.' : 'Internal CMS staff account.'}
        actions={!isNew && <StatusBadge status={user.isActive ? 'active' : 'inactive'} />}
      />

      {isSelf && (
        <p className="mb-4 border border-taupe-300 bg-taupe-100 px-4 py-2.5 text-sm text-charcoal-600">
          This is your own account — role and account-status changes must be made by another administrator.
        </p>
      )}

      {temporaryPassword && <TemporaryPasswordNotice password={temporaryPassword} onDismiss={() => setTemporaryPassword(null)} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          {/* Profile */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Profile</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="First name">
                <input value={form.firstName} onChange={(e) => setForm({ ...form, firstName: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Last name">
                <input value={form.lastName} onChange={(e) => setForm({ ...form, lastName: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Email">
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputClass} />
              </Field>
            </div>
            {isNew && (
              <div className="mt-4">
                <label className="flex items-center gap-2 text-sm text-charcoal-600">
                  <input type="checkbox" checked={form.isActive} onChange={(e) => setForm({ ...form, isActive: e.target.checked })} />
                  Active on creation
                </label>
              </div>
            )}
            <div className="mt-4">
              <button type="button" onClick={isNew ? handleCreate : handleSaveIdentity} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
                <Save size={13} /> {saving ? 'Saving…' : isNew ? 'Create account' : 'Save profile'}
              </button>
            </div>
          </div>

          {/* Access */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Access — roles</p>
            <p className="mb-3 text-xs text-charcoal-600/60">
              A role's own permissions are fixed system-wide — this only controls which roles this account holds.
            </p>
            <div className="flex flex-wrap gap-2">
              {roles
                .filter((r) => r.key !== 'super_admin' || canGrantSuperAdmin)
                .map((r) => (
                  <button
                    key={r.key}
                    type="button"
                    disabled={isSelf}
                    onClick={() => toggleRole(r.key)}
                    title={r.description}
                    className={`px-2.5 py-1 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50 ${
                      form.roleNames.includes(r.key) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
            </div>
            {!isNew && (
              <div className="mt-4">
                <button type="button" onClick={handleSaveRoles} disabled={saving || isSelf} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
                  Save roles
                </button>
              </div>
            )}
          </div>

          {!isNew && (
            <>
              {/* Account status */}
              <div className="border border-taupe-200 bg-white p-6">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Account status</p>
                <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-charcoal-600/70">Created</dt>
                    <dd className="text-charcoal">{user.createdAt ? formatDate(user.createdAt) : '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-charcoal-600/70">Last login</dt>
                    <dd className="text-charcoal">{user.lastLogin ? formatDate(user.lastLogin) : 'Never'}</dd>
                  </div>
                  <div>
                    <dt className="text-charcoal-600/70">Last updated</dt>
                    <dd className="text-charcoal">{user.updatedAt ? formatDate(user.updatedAt) : '—'}</dd>
                  </div>
                </dl>
              </div>

              {/* Security actions */}
              <div className="border border-taupe-200 bg-white p-6">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Security actions</p>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={isSelf}
                    onClick={() => setConfirmAction(user.isActive ? 'deactivate' : 'activate')}
                    className="btn-secondary !px-4 !py-2 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {user.isActive ? 'Deactivate account' : 'Activate account'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmAction('reset-password')}
                    className="btn-secondary !px-4 !py-2 text-xs"
                  >
                    <KeyRound size={13} /> Reset password
                  </button>
                </div>
                <p className="mt-2 text-xs text-charcoal-600/60">
                  Resetting generates a new temporary password shown once — there is no automated reset-email flow in this app.
                </p>
              </div>
            </>
          )}
        </div>

        <div className="space-y-4">
          <Link to="/admin/users" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all users
          </Link>
        </div>
      </div>

      {(confirmAction === 'deactivate' || confirmAction === 'activate') && (
        <ConfirmDialog
          title={confirmAction === 'deactivate' ? 'Deactivate this account?' : 'Activate this account?'}
          description={
            confirmAction === 'deactivate'
              ? 'This account will immediately lose access to the CMS, even with an existing valid session. This is blocked if it is the last active Super Admin.'
              : 'This account will regain access to the CMS.'
          }
          confirmLabel={confirmAction === 'deactivate' ? 'Deactivate' : 'Activate'}
          danger={confirmAction === 'deactivate'}
          onConfirm={handleToggleStatus}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction === 'reset-password' && (
        <ConfirmDialog
          title="Reset this account's password?"
          description="Generates a new temporary password, shown once on this page. The current password stops working immediately."
          confirmLabel="Reset password"
          onConfirm={handleResetPassword}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
