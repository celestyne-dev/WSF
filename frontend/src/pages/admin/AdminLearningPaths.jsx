import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Star } from 'lucide-react'
import { fetchAdminLearningPaths } from '../../api/learningPaths'
import { CAREER_GOAL_OPTIONS } from '../../constants/careerMetadata'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const GOAL_LABEL = Object.fromEntries(CAREER_GOAL_OPTIONS.map((o) => [o.value, o.label]))

export default function AdminLearningPaths() {
  const [paths, setPaths] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchAdminLearningPaths()
      .then((items) => active && setPaths(items))
      .catch(() => active && setError('Something went wrong loading learning paths.'))
    return () => {
      active = false
    }
  }, [])

  return (
    <div>
      <AdminPageHeader
        title="Learning Paths"
        description="Guided career journeys: an ordered set of existing courses for one career goal. Duration and learner progress are derived from the courses."
        actions={
          <Link to="/admin/learning/paths/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New learning path
          </Link>
        }
      />
      {error && <EmptyState title="Couldn't load learning paths" description={error} />}
      {!error && paths === null && <PageLoader />}
      {!error && paths?.length === 0 && <EmptyState title="No learning paths yet" description="Create one to group existing courses into a guided journey." />}
      {!error && paths?.length > 0 && (
        <div className="relative overflow-x-auto border border-taupe-200 bg-white">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-taupe-200 bg-taupe-50 text-xs uppercase tracking-wide text-charcoal-600">
              <tr>
                <th scope="col" className="px-4 py-3">Title</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3">Courses</th>
                <th scope="col" className="px-4 py-3">Goal</th>
                <th scope="col" className="px-4 py-3">Featured</th>
                <th scope="col" className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-taupe-100">
              {paths.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-3">
                    <Link to={`/admin/learning/paths/${p.id}`} className="font-semibold text-charcoal hover:text-burgundy-600">{p.title}</Link>
                    <p className="text-xs text-charcoal-600">/learning/paths/{p.slug}</p>
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={p.status} /></td>
                  <td className="px-4 py-3">{p.courseCount}</td>
                  <td className="px-4 py-3">{GOAL_LABEL[p.careerGoal] || '—'}</td>
                  <td className="px-4 py-3">{p.featured ? <Star size={15} aria-label="Featured" className="text-burgundy-600" /> : <span className="sr-only">Not featured</span>}</td>
                  <td className="px-4 py-3 text-charcoal-600">{p.updatedAt ? formatDate(p.updatedAt) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
