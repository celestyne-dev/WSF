import { useEffect, useState } from 'react'
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import { fetchAdminDashboard, fetchTrafficSources, fetchSubscriberGrowth } from '../../api/admin'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const COLORS = ['#7A2438', '#5B3A4E', '#C98A85', '#9C8C79']

export default function AdminAnalytics() {
  const [pageViewsTrend, setPageViewsTrend] = useState(undefined)
  const [trafficBySource, setTrafficBySource] = useState([])
  const [subscriberGrowth, setSubscriberGrowth] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchAdminDashboard(), fetchTrafficSources(), fetchSubscriberGrowth()])
      .then(([dashboard, sources, growth]) => {
        if (!active) return
        setPageViewsTrend(dashboard.pageViewsTrend)
        setTrafficBySource(sources)
        setSubscriberGrowth(growth)
      })
      .catch(() => active && setError('Something went wrong loading analytics. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  if (error) return <EmptyState title="Couldn't load analytics" description={error} />
  if (pageViewsTrend === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title="Analytics"
        description="Internal analytics from real tracked events. Structured to connect to Google Analytics, Search Console, Meta Pixel, and LinkedIn Insight Tag via Settings > Integrations."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="border border-taupe-200 bg-white p-5">
          <p className="text-sm font-semibold text-charcoal">Article views by month</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={pageViewsTrend}>
                <CartesianGrid stroke="#EDE7DE" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => new Intl.NumberFormat('en-US').format(v)} />
                <Bar dataKey="views" fill="#7A2438" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="border border-taupe-200 bg-white p-5">
          <p className="text-sm font-semibold text-charcoal">Traffic by source</p>
          <div className="mt-4 h-64">
            {trafficBySource.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={trafficBySource} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                    {trafficBySource.map((entry, i) => (
                      <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="flex h-full items-center justify-center text-sm text-charcoal-600">No traffic-source events recorded yet.</p>
            )}
          </div>
        </div>

        <div className="border border-taupe-200 bg-white p-5 lg:col-span-2">
          <p className="text-sm font-semibold text-charcoal">Newsletter subscriber growth</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={subscriberGrowth}>
                <CartesianGrid stroke="#EDE7DE" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => new Intl.NumberFormat('en-US').format(v)} />
                <Bar dataKey="subscribers" fill="#5B3A4E" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
