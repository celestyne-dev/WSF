import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, UserCheck, UserPlus, Users, UserX, Link2, CheckCircle2 } from 'lucide-react'
import { fetchMentorshipOverview } from '../../api/mentorship'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatCard from '../../components/cms/StatCard'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminMentorshipOverview() {
  const [stats, setStats] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchMentorshipOverview()
      .then((data) => active && setStats(data))
      .catch(() => active && setError('Something went wrong loading the mentorship overview. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  if (error) return <EmptyState title="Couldn't load the overview" description={error} />
  if (stats === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader title="Mentorship" description="Programs, applications, and matches — real counts from the database." />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <StatCard label="Open programs" value={stats.openPrograms} icon={Calendar} />
        <StatCard label="Mentor applications" value={stats.mentorApplications} icon={UserPlus} />
        <StatCard label="Mentee applications" value={stats.menteeApplications} icon={UserPlus} />
        <StatCard label="Approved mentors" value={stats.approvedMentors} icon={UserCheck} />
        <StatCard label="Unmatched mentees" value={stats.unmatchedMentees} icon={UserX} />
        <StatCard label="Active matches" value={stats.activeMatches} icon={Link2} />
        <StatCard label="Completed matches" value={stats.completedMatches} icon={CheckCircle2} />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Link to="/admin/mentorship/programs" className="border border-taupe-200 bg-white p-5 hover:border-burgundy-400">
          <Calendar size={18} className="text-burgundy-600" />
          <p className="mt-2 font-serif text-lg font-semibold text-charcoal">Programs</p>
          <p className="mt-1 text-sm text-charcoal-600">Create and manage mentorship programs.</p>
        </Link>
        <Link to="/admin/mentorship/applications" className="border border-taupe-200 bg-white p-5 hover:border-burgundy-400">
          <Users size={18} className="text-burgundy-600" />
          <p className="mt-2 font-serif text-lg font-semibold text-charcoal">Applications</p>
          <p className="mt-1 text-sm text-charcoal-600">Review mentor and mentee applications.</p>
        </Link>
        <Link to="/admin/mentorship/matches" className="border border-taupe-200 bg-white p-5 hover:border-burgundy-400">
          <Link2 size={18} className="text-burgundy-600" />
          <p className="mt-2 font-serif text-lg font-semibold text-charcoal">Matches</p>
          <p className="mt-1 text-sm text-charcoal-600">Pair approved mentors and mentees, and track active relationships.</p>
        </Link>
      </div>
    </div>
  )
}
