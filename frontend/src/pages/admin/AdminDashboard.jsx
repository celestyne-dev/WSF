import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { FileText, Users, Briefcase, Award, CalendarDays, Inbox, Star } from 'lucide-react'
import { fetchAdminDashboard } from '../../api/admin'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatCard from '../../components/cms/StatCard'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminDashboard() {
  const [stats, setStats] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchAdminDashboard()
      .then((data) => active && setStats(data))
      .catch(() => active && setError('Something went wrong loading the dashboard. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  if (error) return <EmptyState title="Couldn't load the dashboard" description={error} />
  if (stats === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader title="Dashboard" description="An overview of Women Shaping Futures — content, audience, and pipeline." />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Published articles" value={stats.publishedArticles} icon={FileText} hint={`${stats.drafts} drafts, ${stats.scheduled} scheduled`} />
        <StatCard label="Subscribers" value={new Intl.NumberFormat('en-US').format(stats.subscribers)} icon={Users} />
        <StatCard label="Active jobs" value={stats.activeJobs} icon={Briefcase} />
        <StatCard label="Active opportunities" value={stats.activeOpportunities} icon={Award} />
        <StatCard label="Upcoming events" value={stats.upcomingEvents} icon={CalendarDays} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="border border-taupe-200 bg-white p-5 lg:col-span-2">
          <p className="text-sm font-semibold text-charcoal">Article views by month</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={stats.pageViewsTrend}>
                <CartesianGrid stroke="#EDE7DE" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => new Intl.NumberFormat('en-US').format(v)} />
                <Line type="monotone" dataKey="views" stroke="#7A2438" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="border border-taupe-200 bg-white p-5">
          <p className="text-sm font-semibold text-charcoal">Pending review</p>
          <ul className="mt-4 space-y-3 text-sm">
            <li className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-charcoal-600">
                <Inbox size={15} /> Story submissions
              </span>
              <Link to="/admin/submissions" className="font-semibold text-burgundy-600 hover:underline">
                {stats.pendingSubmissions} new
              </Link>
            </li>
            <li className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-charcoal-600">
                <Star size={15} /> Nominations
              </span>
              <Link to="/admin/nominations" className="font-semibold text-burgundy-600 hover:underline">
                {stats.pendingNominations} new
              </Link>
            </li>
            <li className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-charcoal-600">
                <FileText size={15} /> Draft articles
              </span>
              <Link to="/admin/articles" className="font-semibold text-burgundy-600 hover:underline">
                {stats.drafts}
              </Link>
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-6 border border-taupe-200 bg-white p-5">
        <p className="text-sm font-semibold text-charcoal">Top articles this month</p>
        {stats.topArticlesThisMonth.length ? (
          <ul className="mt-4 divide-y divide-taupe-200">
            {stats.topArticlesThisMonth.map((a, i) => (
              <li key={a.title} className="flex items-center justify-between py-3">
                <span className="flex items-center gap-3 text-sm text-charcoal">
                  <span className="w-5 font-serif text-base font-semibold text-charcoal-600/50">{i + 1}</span>
                  {a.title}
                </span>
                <span className="text-sm font-semibold text-charcoal-600">{new Intl.NumberFormat('en-US').format(a.views)} views</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-charcoal-600">No article views recorded yet this month.</p>
        )}
      </div>
    </div>
  )
}
