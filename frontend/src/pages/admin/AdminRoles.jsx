import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { fetchAdminRoles } from '../../api/admin'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

// Permission names follow a "<domain>.<action>" convention throughout the
// backend (articles.manage, users.view, settings.manage, ...) — grouped
// here purely by that prefix so a role's permission list reads as
// "Editorial: manage, publish" instead of one flat, unstructured list.
// Real permission names always win; this only supplies a friendlier
// group heading, the same convention constants/roles.js uses for role
// labels.
const GROUP_LABELS = {
  articles: 'Editorial', pages: 'Editorial', homepage: 'Editorial', taxonomy: 'Editorial',
  people: 'People', media: 'People',
  partnerships: 'Commercial', sponsors: 'Commercial', products: 'Commercial', orders: 'Commercial', advertise: 'Commercial',
  community: 'Community', mentorship: 'Community', submissions: 'Community', nominations: 'Community',
  opportunities: 'Opportunity', jobs: 'Opportunity', events: 'Opportunity', resources: 'Opportunity',
  navigation: 'Site', footer: 'Site', settings: 'Site',
  newsletter: 'Newsletter',
  analytics: 'Analytics',
  users: 'Administration', roles: 'Administration',
}

function groupPermissions(permissions) {
  const groups = {}
  for (const name of permissions) {
    const domain = name.split('.')[0]
    const label = GROUP_LABELS[domain] || domain
    groups[label] = groups[label] || []
    groups[label].push(name)
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
}

function RoleCard({ role }) {
  const [expanded, setExpanded] = useState(false)
  const isSuperAdmin = role.key === 'super_admin'
  const groups = groupPermissions(role.permissions)

  return (
    <div className="border border-taupe-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-charcoal">{role.label}</p>
          <p className="mt-1 text-sm text-charcoal-600">{role.description}</p>
        </div>
        <span className="whitespace-nowrap bg-taupe-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">
          {role.userCount} {role.userCount === 1 ? 'user' : 'users'}
        </span>
      </div>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mt-3 flex items-center gap-1 text-xs font-semibold text-burgundy-600 hover:underline"
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {expanded ? 'Hide permissions' : 'View permissions'}
      </button>

      {expanded && (
        <div className="mt-3 space-y-2 border-t border-taupe-200 pt-3">
          {isSuperAdmin ? (
            <p className="text-sm text-charcoal-600">Every permission in the system — Super Admin is never restricted.</p>
          ) : groups.length === 0 ? (
            <p className="text-sm text-charcoal-600/60">This role grants no permissions.</p>
          ) : (
            groups.map(([group, names]) => (
              <div key={group}>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/70">{group}</p>
                <p className="text-sm text-charcoal-600">{names.join(', ')}</p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default function AdminRoles() {
  const [roles, setRoles] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchAdminRoles()
      .then((r) => active && setRoles(r))
      .catch((err) => {
        if (!active) return
        setError(
          err?.response?.status === 403
            ? "You don't have permission to view roles and permissions."
            : 'Something went wrong loading roles. Please try again.',
        )
      })
    return () => {
      active = false
    }
  }, [])

  if (error) return <EmptyState title="Couldn't load roles" description={error} />
  if (roles === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title="Roles & Permissions"
        description="System-defined roles and what each one grants. Roles themselves aren't editable here — assign or remove a role from a specific person on their Users page."
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {roles.map((role) => (
          <RoleCard key={role.key} role={role} />
        ))}
      </div>
    </div>
  )
}
