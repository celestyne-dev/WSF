import { adminUsers, roleDefinitions } from '../../mock/admin'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import { formatDate } from '../../utils/format'

export default function AdminUsers() {
  return (
    <div>
      <AdminPageHeader title="Users & Roles" description="Team members with CMS access, and the role-based permissions available on the platform." />

      <div className="overflow-x-auto border border-taupe-200 bg-white">
        <table className="w-full min-w-[600px] text-left text-sm">
          <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Last login</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-taupe-200">
            {adminUsers.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-3 font-medium text-charcoal">{u.name}</td>
                <td className="px-4 py-3 text-charcoal-600">{u.email}</td>
                <td className="px-4 py-3 text-charcoal-600">{roleDefinitions.find((r) => r.key === u.role)?.label}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={u.status} />
                </td>
                <td className="px-4 py-3 text-charcoal-600">{u.lastLogin ? formatDate(u.lastLogin) : 'Never'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-8">
        <p className="mb-3 text-sm font-semibold text-charcoal">Role permissions reference</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {roleDefinitions.map((r) => (
            <div key={r.key} className="border border-taupe-200 bg-white p-4">
              <p className="text-sm font-semibold text-charcoal">{r.label}</p>
              <p className="mt-1 text-xs text-charcoal-600">{r.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
