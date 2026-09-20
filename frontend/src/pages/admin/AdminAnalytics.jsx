import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import { pageViewsTrend, trafficBySource, subscriberGrowth } from '../../mock/admin'
import AdminPageHeader from '../../components/cms/AdminPageHeader'

const COLORS = ['#7A2438', '#5B3A4E', '#C98A85', '#9C8C79']

export default function AdminAnalytics() {
  return (
    <div>
      <AdminPageHeader
        title="Analytics"
        description="Internal analytics. Structured to connect to Google Analytics, Search Console, Meta Pixel, and LinkedIn Insight Tag via Settings > Integrations."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="border border-taupe-200 bg-white p-5">
          <p className="text-sm font-semibold text-charcoal">Page views by month</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={pageViewsTrend}>
                <CartesianGrid stroke="#EDE7DE" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v / 1000}k`} />
                <Tooltip formatter={(v) => new Intl.NumberFormat('en-US').format(v)} />
                <Bar dataKey="views" fill="#7A2438" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="border border-taupe-200 bg-white p-5">
          <p className="text-sm font-semibold text-charcoal">Traffic by source</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={trafficBySource} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                  {trafficBySource.map((entry, i) => (
                    <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => `${v}%`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="border border-taupe-200 bg-white p-5 lg:col-span-2">
          <p className="text-sm font-semibold text-charcoal">Newsletter subscriber growth</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={subscriberGrowth}>
                <CartesianGrid stroke="#EDE7DE" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#6B5D4C' }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v / 1000}k`} />
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
