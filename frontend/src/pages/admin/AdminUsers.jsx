import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Search, Plus } from 'lucide-react'
import { fetchAdminUsers, fetchAdminRoles } from '../../api/admin'
import { hasPermission } from '../../utils/permissions'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import Pagination from '../../components/ui/Pagination'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

export default function AdminUsers() {
  const currentUser = useSelector((s) => s.auth.user)
  const canManage = hasPermission(currentUser, 'users.manage')

  const [query, setQuery] = useState('')
  const [role, setRole] = useState('')
  const [isActive, setIsActive] = useState('')
  const [page, setPage] = useState(1)
  const [roles, setRoles] = useState([])
  const [rows, setRows] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchAdminRoles().then(setRoles).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchAdminUsers({ query, role, isActive, page, pageSize: 20 })
      .then((res) => {
        if (!active) return
        setRows(res.items)
        setPagination(res.pagination)
      })
      .catch((err) => {
        if (!active) return
        setError(
          err?.response?.status === 403
            ? "You don't have permission to view the staff directory."
            : 'Something went wrong loading users. Please try again.',
        )
      })
    return () => {
      active = false
    }
  }, [query, role, isActive, page])

  function handleFilterChange(setter) {
    return (e) => {
      setPage(1)
      setter(e.target.value)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Users"
        description="Internal WSF CMS staff accounts — not community members, authors, or newsletter subscribers."
        actions={
          canManage && (
            <Link to="/admin/users/new" className="btn-primary !px-4 !py-2 text-xs">
              <Plus size={14} /> Add user
            </Link>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input
            value={query}
            onChange={handleFilterChange(setQuery)}
            placeholder="Search name or email…"
            className="w-64 text-sm focus:outline-none"
          />
        </div>
        <select value={role} onChange={handleFilterChange(setRole)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All roles</option>
          {roles.map((r) => (
            <option key={r.key} value={r.key}>
              {r.label}
            </option>
          ))}
        </select>
        <select value={isActive} onChange={handleFilterChange(setIsActive)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">Active &amp; inactive</option>
          <option value="true">Active only</option>
          <option value="false">Inactive only</option>
        </select>
      </div>

      {error && <EmptyState title="Couldn't load users" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Roles</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Last login</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((u) => (
                  <tr key={u.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/users/${u.id}`} className="hover:text-burgundy-600">
                        {u.name}
                      </Link>
                      {currentUser?.id === u.id && (
                        <span className="ml-2 text-[10px] font-semibold uppercase tracking-wide text-charcoal-600/50">(you)</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{u.email}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {u.roles.map((r) => (
                          <span key={r} className="bg-plum-100 px-2 py-0.5 text-[11px] font-semibold text-plum-700">
                            {roles.find((rd) => rd.key === r)?.label || r}
                          </span>
                        ))}
                        {u.roles.length === 0 && <span className="text-charcoal-600/50">No roles</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={u.isActive ? 'active' : 'inactive'} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{u.lastLogin ? formatDate(u.lastLogin) : 'Never'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{u.createdAt ? formatDate(u.createdAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No users match those filters" description="Try a different search term or clear your filters." />
        )
      )}
      {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}
    </div>
  )
}
