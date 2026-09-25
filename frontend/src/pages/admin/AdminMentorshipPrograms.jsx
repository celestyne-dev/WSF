import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { fetchPrograms } from '../../api/mentorship'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

export default function AdminMentorshipPrograms() {
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchPrograms({ pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading programs. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  return (
    <div>
      <AdminPageHeader
        title="Mentorship Programs"
        description="Create and manage WSF's mentorship initiatives."
        actions={
          <Link to="/admin/mentorship/programs/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New program
          </Link>
        }
      />

      {error && <EmptyState title="Couldn't load programs" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Public</th>
                  <th className="px-4 py-3">Applications</th>
                  <th className="px-4 py-3">Capacity</th>
                  <th className="px-4 py-3">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/mentorship/programs/${row.id}`} className="hover:text-burgundy-600">
                        {row.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.publicVisible ? 'Yes' : 'No'}</td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {row.applicationOpensAt ? formatDate(row.applicationOpensAt) : '—'} &ndash;{' '}
                      {row.applicationClosesAt ? formatDate(row.applicationClosesAt) : '—'}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {row.mentorCapacity ?? '∞'} mentors / {row.menteeCapacity ?? '∞'} mentees
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.updatedAt ? formatDate(row.updatedAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No programs yet" description="Create your first mentorship program to get started." />
        )
      )}
    </div>
  )
}
